import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

os.environ["PLANNER_MODEL"] = "llama-3.3-70b-versatile"
os.environ["REVIEWER_MODEL"] = "llama-3.3-70b-versatile"
os.environ["RECOVERY_MODEL"] = "llama-3.3-70b-versatile"
os.environ["EXECUTOR_MODEL"] = "llama-3.3-70b-versatile"
os.environ["BROWSER_HEADLESS"] = "true"

from src.agent.agent import run_agent_mission
from src.agent.browser import close_browser_session
from src.graph.qa_workflow import run_qa_workflow

async def test():
    print("Starting test run...")
    exec_id = "test_run_123"
    objective = (
        "Navigate to the login page. Input 'admin' in the username field and 'admin123' in the password field. "
        "Fill the OTP code input field (labeled with MFA) with '123456'. Click Sign In, "
        "assert dashboard visibility, take a screenshot, and generate a PDF report."
    )
    
    # We will run uvicorn in a separate thread so we have the mock site up
    from tests.real_world_suite import ServerThread
    from tests.mock_site import app as mock_app
    server = ServerThread(mock_app, port=8088)
    server.start()
    await asyncio.sleep(2)
    
    state = {
        "execution_id": exec_id,
        "target_url": "http://127.0.0.1:8088/login?mfa=true",
        "user_prompt": objective,
        "user_id": "real_world_user",
        "status": "created",
        "recovery_attempts": 0,
        "execution_history": [],
        "final_response": None,
        "memory_enabled": True,
        "recovery_enabled": True,
        "reviewer_enabled": True
    }
    
    try:
        final_state = await run_qa_workflow(state)
        print("\n=== FINAL STATE ===")
        print(f"Status: {final_state.get('status')}")
        print(f"Review status: {final_state.get('review_status')}")
        print(f"Final Response length: {len(final_state.get('final_response', '') or '')}")
        print(final_state.get('final_response'))
        print("======================")
            
    finally:
        server.stop()

if __name__ == "__main__":
    asyncio.run(test())
