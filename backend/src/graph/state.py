from typing import Literal, TypedDict


class QAState(TypedDict, total=False):
    execution_id: str
    target_url: str
    user_prompt: str
    user_id: str
    status: Literal["created", "running", "recovering", "completed", "failed"]
    test_plan: str
    review_status: Literal["PASS", "FAIL", "BLOCKED", "UNKNOWN"]
    assertion_summary: str
    recovery_guidance: str
    recovery_attempts: int
    execution_history: list[str]
    final_response: str | None
    error: str | None
