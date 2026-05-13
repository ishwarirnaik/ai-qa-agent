import os


API_HOST = os.getenv("API_HOST", "localhost")
API_PORT = int(os.getenv("API_PORT", "8000"))

REPORT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../report"))
REPORT_FILE_NAME = "Final_Test_Report.pdf"
DEFAULT_USER_ID = "demo_admin"
AUTH_BYPASS = os.getenv("AUTH_BYPASS", "true").lower() == "true"


def api_base_url() -> str:
    return f"http://{API_HOST}:{API_PORT}"
