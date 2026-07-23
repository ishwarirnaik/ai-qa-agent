import json
import os
from langgraph.graph import END, START, StateGraph

from src.agent.agent import run_agent_mission
from src.agent.factory import build_planner_agent, build_recovery_agent, build_reviewer_agent
from src.core.events import emit_event
from src.graph.state import QAState

planner_agent = build_planner_agent()
reviewer_agent = build_reviewer_agent()
recovery_agent = build_recovery_agent()


RECOVERABLE_TERMS = (
    "selector",
    "locator",
    "timeout",
    "not found",
    "not visible",
    "navigation",
    "missing evidence",
    "assertion failed",
    "page readiness",
    "wait",
)

HUMAN_BLOCK_TERMS = (
    "captcha",
    "mfa",
    "2fa",
    "two-factor",
    "sso",
    "permission",
    "access denied",
    "rate limit",
    "blocked by site",
)


def extract_review_status(review: str | None) -> str:
    if not review:
        return "UNKNOWN"

    first_line = review.strip().splitlines()[0].upper()
    if first_line.startswith("PASS"):
        return "PASS"
    if first_line.startswith("FAIL"):
        return "FAIL"
    if first_line.startswith("BLOCKED"):
        return "BLOCKED"
    return "UNKNOWN"


def should_recover(state: QAState) -> str:
    if not state.get("recovery_enabled", True):
        return "end"
        
    review_status = state.get("review_status", "UNKNOWN")
    attempts = state.get("recovery_attempts", 0)
    review_text = state.get("assertion_summary", "").lower()

    if attempts >= 1 or review_status == "PASS":
        return "export_assets"

    if any(term in review_text for term in HUMAN_BLOCK_TERMS):
        return "export_assets"

    if review_status == "FAIL":
        return "recover"

    if review_status in ("BLOCKED", "UNKNOWN") and any(term in review_text for term in RECOVERABLE_TERMS):
        return "recover"

    return "export_assets"


async def plan_test(state: QAState) -> QAState:
    """Planner node: converts the user's objective into a real-app test plan."""
    await emit_event("planner", "Creating an execution-ready test plan.")
    response = await planner_agent.ainvoke(
        [
            (
                "system",
                "You are an autonomous QA test scenario generator for real web applications. "
                "Instead of just creating a single happy-path workflow, expand broad user objectives into multiple, concrete test scenarios (e.g., positive cases, negative cases like invalid inputs, and edge cases). "
                "Create concise, execution-ready plans covering these multiple scenarios. Avoid demo-site assumptions. "
                "Include observable success criteria and risks like CAPTCHA, MFA, SSO, "
                "permissions, unstable selectors, or rate limits when relevant. "
                "Do NOT include template placeholders, metadata sections, or environment "
                "parameters like browser/OS configurations.",
            ),
            (
                "human",
                f"Target URL: {state['target_url']}\n"
                f"User objective: {state['user_prompt']}\n\n"
                "Return a short numbered test plan that explicitly outlines multiple scenarios (valid, negative, edge cases) derived from the user objective, along with expected evidence and assertions for each.",
            ),
        ]
    )

    state["test_plan"] = response.content
    state["status"] = "running"
    
    scenarios = max(1, response.content.lower().count("scenario"))
    state["generated_scenarios"] = scenarios
    from src.core.stats import set_generated_scenarios
    set_generated_scenarios(scenarios)
    
    print(f"[PLANNER] -> {state['test_plan']}")
    await emit_event("planner", state["test_plan"])
    return state


async def execute_test(state: QAState) -> QAState:
    """Browser executor node: runs the current browser-capable agent."""
    from src.agent.browser import get_session
    get_session().memory_enabled = state.get("memory_enabled", True)

    attempt_number = state.get("recovery_attempts", 0) + 1
    await emit_event("executor", f"Starting browser execution attempt {attempt_number}.")
    recovery_guidance = state.get("recovery_guidance")
    recovery_block = ""
    if recovery_guidance:
        recovery_block = f"Recovery guidance for this retry:\n{recovery_guidance}\n\n"

    planned_objective = (
        f"Original user objective:\n{state['user_prompt']}\n\n"
        f"{recovery_block}"
        "Execute the objective against the live target application. Verify important outcomes "
        "with browser observations/assertions. If blocked by CAPTCHA, MFA, SSO, permissions, "
        "or site protection, stop safely and report the block honestly."
    )

    attempt_result, tool_transcript = await run_agent_mission(
        execution_id=state["execution_id"],
        target_url=state["target_url"],
        user_prompt=planned_objective,
        user_id=state.get("user_id", "demo_admin"),
        save_result=False,
    )

    history = state.get("execution_history", [])
    history.append(attempt_result or "")
    state["execution_history"] = history
    
    current_transcript = state.get("tool_transcript", [])
    current_transcript.extend(tool_transcript)
    state["tool_transcript"] = current_transcript
    
    state["final_response"] = "\n\n".join(
        f"Attempt {index + 1}:\n{summary}"
        for index, summary in enumerate(history)
        if summary
    )
    await emit_event("executor", f"Browser execution attempt {attempt_number} finished.")
    return state


async def review_result(state: QAState) -> QAState:
    """Reviewer node: checks whether the execution result is credible."""
    if not state.get("reviewer_enabled", True):
        state["review_status"] = "PASS"
        state["assertion_summary"] = "Reviewer disabled by config."
        state["status"] = "completed"
        return state

    await emit_event("reviewer", "Reviewing execution evidence and outcome.")
    response = await reviewer_agent.ainvoke(
        [
            (
                "system",
                "You are a QA result reviewer. Judge only from the provided plan and "
                "execution summary. Do not invent browser facts. Mark uncertainty clearly. "
                "A PASS requires: (1) Concrete observed tool results or assertions, not just high-level claims. "
                "(2) Concrete visual/state evidence (confirming that take_evidence_screenshot was called). If no screenshot is present, return FAIL. "
                "(3) Validation of expected page transitions. "
                "Ensure there are no un-replaced empty input templates or placeholders (e.g., '[Insert Username]', 'TODO', '<fill-in>'). "
                "Do NOT fail or block for standard empty tool parameters like '{}' or xml-like tag names in the tool transcript.",
            ),
            (
                "human",
                f"Target URL: {state['target_url']}\n\n"
                f"Plan:\n{state.get('test_plan', '')}\n\n"
                f"Execution summary:\n{state.get('final_response', '')}\n\n"
                "Return: PASS, FAIL, or BLOCKED, followed by a concise reason and any missing evidence.",
            ),
        ]
    )

    state["assertion_summary"] = response.content
    state["review_status"] = extract_review_status(response.content)
    state["status"] = "completed"
    print(f"[REVIEWER] -> {state['assertion_summary']}")
    await emit_event("reviewer", state["assertion_summary"])

    if state.get("final_response"):
        state["final_response"] = (
            f"{state['final_response']}\n\n"
            f"Independent QA review:\n{state['assertion_summary']}"
        )

    return state


async def recover_test(state: QAState) -> QAState:
    """Recovery node: creates targeted retry guidance after a failed review."""
    await emit_event("recovery", "Preparing targeted retry guidance.")
    response = await recovery_agent.ainvoke(
        [
            (
                "system",
                "You are a QA automation recovery specialist for real web applications. "
                "Create one targeted retry strategy. Do not bypass CAPTCHA, MFA, SSO, "
                "permissions, paywalls, or site protections. Prefer safer waits, alternate "
                "stable selectors, clearer assertions, and better evidence capture.",
            ),
            (
                "human",
                f"Target URL: {state['target_url']}\n\n"
                f"Original objective:\n{state['user_prompt']}\n\n"
                f"Plan:\n{state.get('test_plan', '')}\n\n"
                f"Execution summary:\n{state.get('final_response', '')}\n\n"
                f"Reviewer result:\n{state.get('assertion_summary', '')}\n\n"
                "Return concise retry guidance for the browser executor. If the issue "
                "requires human authentication/security action, say that plainly.",
            ),
        ]
    )

    state["recovery_attempts"] = state.get("recovery_attempts", 0) + 1
    state["recovery_guidance"] = response.content
    state["status"] = "recovering"
    print(f"[RECOVERY] -> {state['recovery_guidance']}")
    await emit_event("recovery", state["recovery_guidance"])
    return state


async def export_assets(state: QAState) -> QAState:
    """Exports a Playwright python script and JSON trace from the execution history."""
    await emit_event("export", "Generating Playwright script and execution traces.")
    
    exec_id = state.get("execution_id", "unknown_execution")
    exports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../tests/exports'))
    os.makedirs(exports_dir, exist_ok=True)
    
    trace_path = os.path.join(exports_dir, f"{exec_id}_trace.json")
    trace_data = {
        "execution_id": exec_id,
        "target_url": state.get("target_url"),
        "user_prompt": state.get("user_prompt"),
        "test_plan": state.get("test_plan"),
        "status": state.get("status"),
        "review_status": state.get("review_status"),
        "tool_transcript": state.get("tool_transcript", [])
    }
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, indent=2)
        
    script_path = os.path.join(exports_dir, f"{exec_id}_script.py")
    transcript = "\n".join(state.get("tool_transcript", []))
    
    if transcript:
        response = await planner_agent.ainvoke([
            ("system", "You are an expert QA automation engineer. Convert the following sequence of browser tool interactions into a standalone Python Playwright script. The script should use `sync_playwright`, navigate to the target URL, perform the actions using Playwright locators, and include comments for assertions. Return ONLY the raw python code without markdown fences."),
            ("human", f"Target URL: {state.get('target_url')}\n\nTool Transcript:\n{transcript}")
        ])
        
        script_content = response.content.strip()
        if script_content.startswith("```python"):
            script_content = script_content[9:]
        if script_content.endswith("```"):
            script_content = script_content[:-3]
            
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content.strip())
            
        state["exported_script_path"] = script_path
        state["export_success"] = True
        print(f"[EXPORT] -> Generated Playwright script at {script_path}")
        await emit_event("export", f"Exported script to {script_path}")
    
    return state


def build_qa_workflow():
    workflow = StateGraph(QAState)
    workflow.add_node("planner", plan_test)
    workflow.add_node("executor", execute_test)
    workflow.add_node("reviewer", review_result)
    workflow.add_node("recovery", recover_test)
    workflow.add_node("export_assets", export_assets)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        should_recover,
        {
            "recover": "recovery",
            "export_assets": "export_assets",
        },
    )
    workflow.add_edge("recovery", "executor")
    workflow.add_edge("export_assets", END)

    return workflow.compile()


qa_workflow = build_qa_workflow()


async def run_qa_workflow(state: QAState) -> QAState:
    from src.agent.browser import _active_execution_id, close_browser_session
    from src.core.stats import get_current_stats, dump_benchmark_csv
    from src.api.database import DatabaseManager
    import time

    exec_id = state.get("execution_id", "default_execution")
    _active_execution_id.set(exec_id)
    
    start_time = time.time()
    state["start_time"] = start_time
    final_state = state
    
    try:
        final_state = await qa_workflow.ainvoke(state)
        return final_state
    except Exception as exc:
        final_state["status"] = "failed"
        final_state["error"] = repr(exc)
        final_state["final_response"] = f"System Error: {repr(exc)}"
        return final_state
    finally:
        end_time = time.time()
        execution_time = end_time - start_time
        final_state["execution_time"] = execution_time
        
        stats = get_current_stats()
        final_state["llm_calls"] = stats.get("llama-3.1-8b-instant", 0) + stats.get("llama-3.3-70b-versatile", 0)
        final_state["cache_hits"] = stats.get("cache_hits", 0)
        final_state["cache_misses"] = stats.get("cache_misses", 0)
        final_state["assertions_passed"] = stats.get("assertions_passed", 0)
        final_state["generated_scenarios"] = stats.get("generated_scenarios", 0)
        
        try:
            dump_benchmark_csv(final_state)
        except Exception as e:
            print(f"Failed to dump csv: {e}")
            
        try:
            DatabaseManager.save_test_run(
                user_id=final_state.get("user_id", "demo_admin"),
                execution_id=final_state.get("execution_id", exec_id),
                target_url=final_state.get("target_url", ""),
                prompt=final_state.get("user_prompt", ""),
                status=final_state.get("status", "unknown"),
                pdf_path="",
                result=final_state.get("review_status", "UNKNOWN"),
                test_plan=final_state.get("test_plan", ""),
                script_code=final_state.get("exported_script_path", ""),
                execution_time=execution_time,
                llm_calls=final_state["llm_calls"],
                cache_hits=final_state["cache_hits"],
                cache_misses=final_state["cache_misses"],
                generated_scenarios=final_state["generated_scenarios"],
                assertions_passed=final_state["assertions_passed"],
                export_success=final_state.get("export_success", False)
            )
        except Exception as e:
            print(f"Failed to log to db in run_qa_workflow: {e}")
            
        await close_browser_session(exec_id)
