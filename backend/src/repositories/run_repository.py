from src.api.database import DatabaseManager


class RunRepository:
    def save_run(
        self,
        user_id: str,
        execution_id: str,
        target_url: str,
        prompt: str,
        status: str,
        pdf_path: str,
        report_url: str | None = None,
        result: str | None = None,
        test_plan: str | None = None,
        script_code: str | None = None,
    ):
        return DatabaseManager.save_test_run(
            user_id=user_id,
            execution_id=execution_id,
            target_url=target_url,
            prompt=prompt,
            status=status,
            pdf_path=pdf_path,
            report_url=report_url,
            result=result,
            test_plan=test_plan,
            script_code=script_code,
        )

    def list_runs(self, user_id: str):
        return DatabaseManager.get_history(user_id)
