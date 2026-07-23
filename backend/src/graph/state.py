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
    tool_transcript: list[str]
    final_response: str | None
    error: str | None
    exported_script_path: str | None
    
    # Benchmarking and Evaluation metrics
    start_time: float
    execution_time: float
    llm_calls: int
    cache_hits: int
    cache_misses: int
    generated_scenarios: int
    assertions_passed: int
    export_success: bool
    
    # Configuration flags for baseline execution & evaluation
    memory_enabled: bool
    recovery_enabled: bool
    reviewer_enabled: bool
