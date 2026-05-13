import asyncio
import json
import ast
import uuid
import os
import sys

from src.agent.browser import set_artifact_context
from src.core.config import DEFAULT_USER_ID
from src.core.events import event_sink
from src.core.models import TestRequest, TestRunResult
from src.graph.qa_workflow import run_qa_workflow
from src.graph.state import QAState
from src.repositories.run_repository import RunRepository
from src.services.artifact_service import ArtifactService


class RunService:
    def __init__(self, run_repository: RunRepository | None = None):
        self.run_repository = run_repository or RunRepository()

    async def execute_test(self, request: TestRequest, user_id: str = DEFAULT_USER_ID) -> TestRunResult:
        return await self._execute_test(request, request.user_id or user_id)

    async def _execute_test(
        self,
        request: TestRequest,
        user_id: str = DEFAULT_USER_ID,
    ) -> TestRunResult:
        execution_id = str(uuid.uuid4())[:8]
        artifacts = ArtifactService(execution_id)
        artifacts.prepare_run_directory()
        set_artifact_context(artifacts.run_dir, artifacts.report_path)

        state: QAState = {
            "execution_id": execution_id,
            "target_url": request.target_url,
            "user_prompt": request.prompt,
            "user_id": user_id,
            "status": "created",
            "recovery_attempts": 0,
            "execution_history": [],
            "final_response": None,
        }
        state = await run_qa_workflow(state)
        result = state.get("final_response")

        artifacts.migrate_legacy_report_if_needed()
        status = state.get("review_status", "UNKNOWN")
        if status == "UNKNOWN":
            status = "SUCCESS" if artifacts.report_exists() else "FAILED"
        if not artifacts.report_exists():
            status = "FAILED"

        try:
            self.run_repository.save_run(
                user_id=user_id,
                execution_id=execution_id,
                target_url=request.target_url,
                prompt=request.prompt,
                status=status,
                pdf_path=artifacts.report_path if artifacts.report_exists() else "NONE",
                report_url=artifacts.report_url(),
                result=result,
            )
        except Exception as exc:
            print(f"DB Error saving test run: {exc}")

        return TestRunResult(
            execution_id=execution_id,
            status="COMPLETED",
            result=result,
            report_url=artifacts.report_url(),
        )

    async def stream_execute_test(self, request: TestRequest, user_id: str = DEFAULT_USER_ID):
        active_user_id = request.user_id or user_id
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def publish(stage: str, message: str, **extra):
            await queue.put({"stage": stage, "message": message, **extra})

        async def run():
            execution_id = str(uuid.uuid4())[:8]
            artifacts = ArtifactService(execution_id)
            artifacts.prepare_run_directory()
            set_artifact_context(artifacts.run_dir, artifacts.report_path)
            await publish("system", "Run created.", execution_id=execution_id)

            state: QAState = {
                "execution_id": execution_id,
                "target_url": request.target_url,
                "user_prompt": request.prompt,
                "user_id": active_user_id,
                "status": "created",
                "recovery_attempts": 0,
                "execution_history": [],
                "final_response": None,
            }

            token = event_sink.set(publish)
            try:
                state = await run_qa_workflow(state)
            finally:
                event_sink.reset(token)

            artifacts.migrate_legacy_report_if_needed()
            status = state.get("review_status", "UNKNOWN")
            if status == "UNKNOWN":
                status = "SUCCESS" if artifacts.report_exists() else "FAILED"
            if not artifacts.report_exists():
                status = "FAILED"

            try:
                self.run_repository.save_run(
                    user_id=active_user_id,
                    execution_id=execution_id,
                    target_url=request.target_url,
                    prompt=request.prompt,
                    status=status,
                    pdf_path=artifacts.report_path if artifacts.report_exists() else "NONE",
                    report_url=artifacts.report_url(),
                    result=state.get("final_response"),
                )
            except Exception as exc:
                await publish("database", f"Could not save run history: {exc}")

            result = TestRunResult(
                execution_id=execution_id,
                status="COMPLETED",
                result=state.get("final_response"),
                report_url=artifacts.report_url(),
            )
            await publish(
                "complete",
                "Run completed.",
                execution_id=execution_id,
                review_status=status,
                report_url=result.report_url,
                result=result.model_dump(),
            )
            await queue.put({"stage": "__close__", "message": ""})

        task = asyncio.create_task(run())

        try:
            while True:
                event = await queue.get()
                if event["stage"] == "__close__":
                    break
                yield f"data: {json.dumps(event)}\n\n"
            await task
        except asyncio.CancelledError:
            task.cancel()
            raise

    def list_history(self, user_id: str = DEFAULT_USER_ID):
        try:
            return self.run_repository.list_runs(user_id)
        except Exception as exc:
            print(f"DB Error loading history: {exc}")
            return []

    def _is_script_safe(self, script_code: str) -> bool:
        try:
            tree = ast.parse(script_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in ["os", "subprocess", "sys", "shutil"]:
                            return False
                elif isinstance(node, ast.ImportFrom):
                    if node.module in ["os", "subprocess", "sys", "shutil"]:
                        return False
            return True
        except SyntaxError:
            return False

    async def stream_execute_script(self, request: ExecuteScriptRequest, user_id: str = DEFAULT_USER_ID):
        active_user_id = request.user_id or user_id
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def publish(stage: str, message: str, **extra):
            await queue.put({"stage": stage, "message": message, **extra})

        async def run():
            execution_id = str(uuid.uuid4())[:8]
            artifacts = ArtifactService(execution_id)
            artifacts.prepare_run_directory()
            
            await publish("system", "Run created. Preparing script execution.", execution_id=execution_id)
            
            if not self._is_script_safe(request.script_code):
                await publish("error", "Security violation: Script contains forbidden imports (os, subprocess, sys, shutil).")
                await queue.put({"stage": "__close__", "message": ""})
                return

            script_path = os.path.join(artifacts.run_dir, "test_script.py")
            with open(script_path, "w") as f:
                f.write(request.script_code)
                
            await publish("system", f"Script saved to {script_path}")
            
            # Start execution
            await publish("executor", "Starting Playwright script execution.")
            
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=artifacts.run_dir
            )
            
            # Read output
            async def read_output():
                if process.stdout:
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            break
                        decoded_line = line.decode('utf-8', errors='replace').strip()
                        if decoded_line:
                            await publish("tool_result", decoded_line)
                await process.wait()

            try:
                # 5 minutes maximum timeout
                await asyncio.wait_for(read_output(), timeout=300)
            except asyncio.TimeoutError:
                await publish("error", "Execution timed out after 5 minutes.")
                try:
                    process.terminate()
                except Exception:
                    pass
            
            if process.returncode == 0:
                await publish("executor", "Execution completed successfully.")
                status = "PASS"
            else:
                await publish("error", f"Execution failed with code {process.returncode}")
                status = "FAIL"
                
            # Assume it created evidence.png based on our generator instruction
            if os.path.exists(os.path.join(artifacts.run_dir, "evidence.png")):
                # In a real implementation we might generate PDF from evidence here
                # Let's just create a simple PDF
                from fpdf import FPDF
                try:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, txt="AI QA Agent - Script Execution Report", ln=True, align='C')
                    pdf.image(os.path.join(artifacts.run_dir, "evidence.png"), x=10, y=30, w=190)
                    pdf.output(artifacts.report_path)
                    await publish("system", "Report generated.")
                except Exception as e:
                    await publish("error", f"Failed to generate PDF: {e}")

            # Save run result to DB
            try:
                self.run_repository.save_run(
                    user_id=active_user_id,
                    execution_id=execution_id,
                    target_url=request.target_url,
                    prompt=request.prompt,
                    status=status,
                    pdf_path=artifacts.report_path if artifacts.report_exists() else "NONE",
                    report_url=artifacts.report_url(),
                    result=f"Script execution finished with return code {process.returncode if process.returncode is not None else 'TIMEOUT'}",
                    test_plan=request.test_plan,
                    script_code=request.script_code,
                )
            except Exception as exc:
                await publish("database", f"Could not save run history: {exc}")

            result = TestRunResult(
                execution_id=execution_id,
                status="COMPLETED",
                result=f"Return code: {process.returncode}",
                report_url=artifacts.report_url(),
            )
            
            await publish(
                "complete",
                "Run completed.",
                execution_id=execution_id,
                review_status=status,
                report_url=result.report_url,
                result=result.model_dump(),
            )
            await queue.put({"stage": "__close__", "message": ""})

        task = asyncio.create_task(run())

        try:
            while True:
                event = await queue.get()
                if event["stage"] == "__close__":
                    break
                yield f"data: {json.dumps(event)}\n\n"
            await task
        except asyncio.CancelledError:
            task.cancel()
            raise
