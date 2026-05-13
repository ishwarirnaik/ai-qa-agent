import os

from src.core.config import REPORT_DIR, REPORT_FILE_NAME, api_base_url


class ArtifactService:
    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self.run_dir = os.path.join(REPORT_DIR, execution_id)
        self.report_path = os.path.join(self.run_dir, REPORT_FILE_NAME)

    def prepare_run_directory(self) -> None:
        os.makedirs(self.run_dir, exist_ok=True)
        if os.path.exists(self.report_path):
            os.remove(self.report_path)
        legacy_path = os.path.join(REPORT_DIR, REPORT_FILE_NAME)
        if os.path.exists(legacy_path):
            os.remove(legacy_path)

    def report_exists(self) -> bool:
        return os.path.exists(self.report_path)

    def report_url(self) -> str | None:
        if not self.report_exists():
            return None
        return f"{api_base_url()}/report/{self.execution_id}/{REPORT_FILE_NAME}"

    def migrate_legacy_report_if_needed(self) -> None:
        """Legacy fallback intentionally disabled.

        A stale shared report can make a failed live-site run look successful.
        Reports must be generated inside the current execution directory.
        """
        return None
