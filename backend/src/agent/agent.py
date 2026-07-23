import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.agent.browser import close_browser, start_browser
from src.agent.factory import build_qa_agent
from src.agent.prompts import SYSTEM_INSTRUCTION
from src.core.events import emit_event
from src.graph.state import QAState

agent_executor = build_qa_agent()

async def run_agent_mission(
    execution_id: str,
    target_url: str,
    user_prompt: str,
    user_id: str = "demo_admin",
    save_result: bool = True,
):
    from src.agent.browser import _active_execution_id
    _active_execution_id.set(execution_id)
    print(f"\n--- AI TEST MANAGER STARTED ---")
    state: QAState = {
        "execution_id": execution_id,
        "target_url": target_url,
        "user_prompt": user_prompt,
        "user_id": user_id,
        "status": "running",
        "final_response": None,
    }

    combined_instruction = (
        f"Execution ID: {execution_id}\n"
        f"Target URL: {target_url}\n"
        f"Test Objective: {user_prompt}\n"
        "Create a concise test plan internally, execute it, verify each major result, "
        "capture final evidence, and generate the final report."
    )
    
    try:
        await start_browser()
        final_response = None
        tool_transcript: list[str] = []
        
        async for chunk in agent_executor.astream(
            {"messages": [("system", SYSTEM_INSTRUCTION), ("human", combined_instruction)]},
            config={"recursion_limit": 40}
        ):
            if "agent" in chunk:
                msg = chunk["agent"]["messages"][0]
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        decision = f"Calling {tool_call['name']} with args: {tool_call['args']}"
                        print(f"[AI DECISION] -> {decision}")
                        tool_transcript.append(f"TOOL CALL: {decision}")
                        await emit_event("tool_call", decision)
                else:
                    print(f"[AI RESPONSE] -> {msg.content}")
                    if msg.content:
                        await emit_event("agent_response", msg.content)
                final_response = msg.content
            elif "tools" in chunk:
                messages = chunk["tools"].get("messages", [])
                if not messages:
                    print(f"[TOOL OUTPUT] -> Execution successful.")
                    await emit_event("tool_result", "Tool execution completed.")
                for tool_message in messages:
                    content = getattr(tool_message, "content", str(tool_message))
                    name = getattr(tool_message, "name", "tool")
                    output = f"{name}: {content}"
                    print(f"[TOOL OUTPUT] -> {output}")
                    tool_transcript.append(f"TOOL RESULT: {output}")
                    await emit_event("tool_result", output)

        state["status"] = "completed"
        if tool_transcript:
            final_response = (
                f"{final_response or ''}\n\n"
                "Observed execution transcript:\n"
                + "\n".join(tool_transcript[-30:])
            )
        state["final_response"] = final_response
        return final_response, tool_transcript
    except Exception as e:
        state["status"] = "failed"
        state["error"] = repr(e)
        return f"System Error: {repr(e)}", []
    finally:
        # Browser cleanup is managed by the parent graph workflow
        pass
