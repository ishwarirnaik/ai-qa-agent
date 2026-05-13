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
    review_status = state.get("review_status", "UNKNOWN")
    attempts = state.get("recovery_attempts", 0)
    review_text = state.get("assertion_summary", "").lower()

    if attempts >= 1 or review_status == "PASS":
        return "end"

    if any(term in review_text for term in HUMAN_BLOCK_TERMS):
        return "end"

    if review_status == "FAIL":
        return "recover"

    if review_status in ("BLOCKED", "UNKNOWN") and any(term in review_text for term in RECOVERABLE_TERMS):
        return "recover"

    return "end"


async def plan_test(state: QAState) -> QAState:
    """Planner node: converts the user's objective into a real-app test plan."""
    await emit_event("planner", "Creating an execution-ready test plan.")
    response = await planner_agent.ainvoke(
        [
            (
                "system",
                "You are a senior QA test planner for real web applications. "
                "Create concise, execution-ready plans. Avoid demo-site assumptions. "
                "Include observable success criteria and risks like CAPTCHA, MFA, SSO, "
                "permissions, unstable selectors, or rate limits when relevant.",
            ),
            (
                "human",
                f"Target URL: {state['target_url']}\n"
                f"User objective: {state['user_prompt']}\n\n"
                "Return a short numbered test plan with expected evidence and assertions.",
            ),
        ]
    )

    state["test_plan"] = response.content
    state["status"] = "running"
    print(f"[PLANNER] -> {state['test_plan']}")
    await emit_event("planner", state["test_plan"])
    return state


async def execute_test(state: QAState) -> QAState:
    """Browser executor node: runs the current browser-capable agent."""
    attempt_number = state.get("recovery_attempts", 0) + 1
    await emit_event("executor", f"Starting browser execution attempt {attempt_number}.")
    recovery_guidance = state.get("recovery_guidance")
    recovery_block = ""
    if recovery_guidance:
        recovery_block = f"Recovery guidance for this retry:\n{recovery_guidance}\n\n"

    planned_objective = (
        f"Original user objective:\n{state['user_prompt']}\n\n"
        f"Planner test plan:\n{state.get('test_plan', 'No plan produced.')}\n\n"
        f"{recovery_block}"
        "Execute the plan against the live target application. Verify important outcomes "
        "with browser observations/assertions. If blocked by CAPTCHA, MFA, SSO, permissions, "
        "or site protection, stop safely and report the block honestly."
    )

    attempt_result = await run_agent_mission(
        execution_id=state["execution_id"],
        target_url=state["target_url"],
        user_prompt=planned_objective,
        user_id=state.get("user_id", "demo_admin"),
        save_result=False,
    )

    history = state.get("execution_history", [])
    history.append(attempt_result or "")
    state["execution_history"] = history
    state["final_response"] = "\n\n".join(
        f"Attempt {index + 1}:\n{summary}"
        for index, summary in enumerate(history)
        if summary
    )
    await emit_event("executor", f"Browser execution attempt {attempt_number} finished.")
    return state


async def review_result(state: QAState) -> QAState:
    """Reviewer node: checks whether the execution result is credible."""
    await emit_event("reviewer", "Reviewing execution evidence and outcome.")
    response = await reviewer_agent.ainvoke(
        [
            (
                "system",
                "You are a QA result reviewer. Judge only from the provided plan and "
                "execution summary. Do not invent browser facts. Mark uncertainty clearly. "
                "A PASS requires concrete observed tool results or assertions, not just a "
                "high-level agent claim. If evidence is missing or stale, return FAIL or BLOCKED.",
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


def build_qa_workflow():
    workflow = StateGraph(QAState)
    workflow.add_node("planner", plan_test)
    workflow.add_node("executor", execute_test)
    workflow.add_node("reviewer", review_result)
    workflow.add_node("recovery", recover_test)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        should_recover,
        {
            "recover": "recovery",
            "end": END,
        },
    )
    workflow.add_edge("recovery", "executor")

    return workflow.compile()


qa_workflow = build_qa_workflow()


async def run_qa_workflow(state: QAState) -> QAState:
    try:
        return await qa_workflow.ainvoke(state)
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = repr(exc)
        state["final_response"] = f"System Error: {repr(exc)}"
        return state
