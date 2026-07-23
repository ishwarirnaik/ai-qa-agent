import os
import sys
import time
import math
import asyncio
import threading
import httpx
import uvicorn
from playwright.async_api import async_playwright

# Setup paths to ensure we can import 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# Force all agents to run on the 8b model to prevent token limit errors, except the Executor which runs on Gemma 2
os.environ["PLANNER_MODEL"] = "llama-3.1-8b-instant"
os.environ["REVIEWER_MODEL"] = "llama-3.1-8b-instant"
os.environ["RECOVERY_MODEL"] = "llama-3.1-8b-instant"
os.environ["EXECUTOR_MODEL"] = "llama-3.3-70b-versatile"
os.environ["BROWSER_HEADLESS"] = "true"

from tests.mock_site import app as mock_site_app
from src.api.main import app as api_app
from src.api.database import _in_memory_selector_cache
from src.graph.qa_workflow import run_qa_workflow
from src.graph.state import QAState
from src.core.stats import track_llm_calls

# Thread-safe server control for running uvicorn in background
class ServerThread(threading.Thread):
    def __init__(self, app, host="127.0.0.1", port=8088):
        super().__init__()
        self.config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)
        self.daemon = True

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


async def run_scenario(url, prompt, mode_name, memory_enabled=True, execution_id=None):
    if not execution_id:
        execution_id = f"real_{mode_name.replace(' ', '_').lower()}_{int(time.time())}"
    
    state: QAState = {
        "execution_id": execution_id,
        "target_url": url,
        "user_prompt": prompt,
        "user_id": "real_world_user",
        "status": "created",
        "recovery_attempts": 0,
        "execution_history": [],
        "final_response": None,
        "memory_enabled": memory_enabled,
        "recovery_enabled": True,
        "reviewer_enabled": True
    }
    
    start_time = time.time()
    
    with track_llm_calls() as counts:
        final_state = await run_qa_workflow(state)
        llm_8b = counts.get("llama-3.1-8b-instant", 0)
        llm_70b = counts.get("llama-3.3-70b-versatile", 0)
        heals = counts.get("heals", 0)
        
    duration = time.time() - start_time
    success = final_state.get("review_status") == "PASS"
    
    return {
        "success": success,
        "time": duration,
        "heals": heals,
        "llm_8b": llm_8b,
        "llm_70b": llm_70b,
        "error": final_state.get("error", ""),
        "review_status": final_state.get("review_status"),
        "final_response": final_state.get("final_response")
    }

async def auto_resume_mfa(execution_id: str, delay_sec: float = 8.0):
    """Simulates a human filling the OTP and hitting the API endpoint to resume."""
    await asyncio.sleep(delay_sec)
    resume_url = f"http://127.0.0.1:8008/api/v1/execute/{execution_id}/resume"
    print(f"\n[Auto-Resume Background task] Active. Will poll POST resume API: {resume_url}...")
    
    start_time = time.time()
    while time.time() - start_time < 90:  # 90 seconds timeout
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(resume_url, json={}, timeout=10.0)
                if resp.status_code == 200:
                    print(f"[Auto-Resume Status] Resumed successfully: {resp.status_code} - {resp.json()}")
                    return
                elif resp.status_code == 404:
                    # Not paused yet, wait and retry
                    await asyncio.sleep(2.0)
                else:
                    print(f"[Auto-Resume Status] Unexpected status code: {resp.status_code} - {resp.json()}")
                    await asyncio.sleep(2.0)
        except Exception as e:
            print(f"[Auto-Resume Error] Failed to contact resume endpoint: {e}")
            await asyncio.sleep(2.0)
    print("[Auto-Resume Status] Failed to resume execution within timeout.")

async def main():
    print("[Uvicorn] Booting Target Mock Site (Port 8088) and API Backend (Port 8008)...")
    mock_server = ServerThread(mock_site_app, port=8088)
    api_server = ServerThread(api_app, port=8008)
    
    mock_server.start()
    api_server.start()
    
    await asyncio.sleep(2) # Wait for boots
    
    results = {}
    
    # ==========================================================================
    # TEST 1: E-COMMERCE WORKFLOW (SauceDemo Checkout Flow)
    # Classifications: DOM Complexity: Medium | Selector Volatility: Low | Auth Difficulty: Low | JS Dynamism: Med
    # ==========================================================================
    print("\n" + "="*80)
    print("TEST 1: SAUCEDEMO E-COMMERCE CHECKOUT FLOW")
    print("="*80)
    
    sauce_prompt = (
        "Login with username 'standard_user' and password 'secret_sauce'. "
        "On the products page, click 'Add to cart' for the Sauce Labs Backpack. "
        "Navigate to the shopping cart, click Checkout, fill in First Name 'Alice', "
        "Last Name 'Smith', and Postal Code '90210', click Continue, click Finish, "
        "assert that the page contains 'Thank you for your order!', take a screenshot, "
        "and generate the final PDF report."
    )
    
    res_sauce = await run_scenario(
        url="https://www.saucedemo.com/",
        prompt=sauce_prompt,
        mode_name="SauceDemo Checkout"
    )
    results["SauceDemo Checkout"] = res_sauce
    print(f"Outcome: {'PASS' if res_sauce['success'] else 'FAIL'} | Time: {res_sauce['time']:.2f}s | LLM Calls: {res_sauce['llm_8b']}")
    
    # ==========================================================================
    # TEST 2: PUBLIC DOCUMENTATION FLOW (Python Docs Search)
    # Classifications: DOM Complexity: Medium | Selector Volatility: Low | Auth Difficulty: None | JS Dynamism: Low
    # ==========================================================================
    print("\n" + "="*80)
    print("TEST 2: PYTHON DOCS SEARCH & NAVIGATION")
    print("="*80)
    
    docs_prompt = (
        "Search for 'dataclasses' in the search input box. Click the first documentation link. "
        "Assert that the page contains the text 'dataclasses — Data Classes', take a screenshot, "
        "and generate the final PDF report."
    )
    
    res_docs = await run_scenario(
        url="https://docs.python.org/3/",
        prompt=docs_prompt,
        mode_name="Python Docs Search"
    )
    results["Python Docs Search"] = res_docs
    print(f"Outcome: {'PASS' if res_docs['success'] else 'FAIL'} | Time: {res_docs['time']:.2f}s | LLM Calls: {res_docs['llm_8b']}")
    
    # ==========================================================================
    # TEST 3: EXTREME DRIFT SIMULATION & MEMORY VALIDATION (Mock Site Extreme Drift)
    # Runs Cold cache then Warm cache to measure selector caching and learning
    # Classifications: DOM Complexity: Low-Med | Selector Volatility: High | Auth Difficulty: Low | JS Dynamism: Low
    # ==========================================================================
    print("\n" + "="*80)
    print("TEST 3 (COLD RUN): EXTREME SELECTOR DRIFT SIMULATION")
    print("="*80)
    
    drift_url = "http://127.0.0.1:8088/login?drift=extreme"
    login_prompt = "Log in with username admin and password admin123, click Sign In, then assert that the welcome text is visible on the dashboard."
    
    # Clear cache before cold run
    _in_memory_selector_cache.clear()
    
    res_drift_cold = await run_scenario(
        url=drift_url,
        prompt=login_prompt,
        mode_name="Mock Site Extreme Drift (Cold Run)"
    )
    results["Mock Site Extreme Drift (Cold Run)"] = res_drift_cold
    print(f"Outcome: {'PASS' if res_drift_cold['success'] else 'FAIL'} | Time: {res_drift_cold['time']:.2f}s | LLM Calls: {res_drift_cold['llm_8b']}")
    
    print("\n" + "="*80)
    print("TEST 3 (WARM RUN): EXTREME SELECTOR DRIFT WITH DEEM CACHE WARMED")
    print("="*80)
    
    res_drift_warm = await run_scenario(
        url=drift_url,
        prompt=login_prompt,
        mode_name="Mock Site Extreme Drift (Warm Run)"
    )
    results["Mock Site Extreme Drift (Warm Run)"] = res_drift_warm
    print(f"Outcome: {'PASS' if res_drift_warm['success'] else 'FAIL'} | Time: {res_drift_warm['time']:.2f}s | LLM Calls: {res_drift_warm['llm_8b']}")
    
    # ==========================================================================
    # TEST 4: HUMAN-IN-THE-LOOP (HIL) PAUSE-RESUME WORKFLOW
    # Classifications: DOM Complexity: Medium | Selector Volatility: Medium | Auth Difficulty: High (Simulated hCaptcha/OTP) | JS Dynamism: Med
    # ==========================================================================
    print("\n" + "="*80)
    print("TEST 4: HUMAN-IN-THE-LOOP OTP/CAPTCHA PAUSE & RESUME")
    print("="*80)
    
    mfa_url = "http://127.0.0.1:8088/login?mfa=true"
    mfa_prompt = (
        "Navigate to the login page. Input 'admin' in the username field and 'admin123' in the password field. "
        "Fill the OTP code input field (labeled with MFA) with '123456'. Click Sign In, "
        "assert dashboard visibility, take a screenshot, and generate a PDF report."
    )
    
    exec_id = f"hil_pause_test_{int(time.time())}"
    # Schedule the auto-resume endpoint trigger in 8 seconds
    asyncio.create_task(auto_resume_mfa(exec_id, delay_sec=8.0))
    
    res_mfa = await run_scenario(
        url=mfa_url,
        prompt=mfa_prompt,
        mode_name="MFA Human-in-the-Loop",
        execution_id=exec_id
    )
    results["MFA Human-in-the-Loop"] = res_mfa
    print(f"Outcome: {'PASS' if res_mfa['success'] else 'FAIL'} | Time: {res_mfa['time']:.2f}s | LLM Calls: {res_mfa['llm_8b']}")
    
    # ==========================================================================
    # PRINT SUMMARY REPORT
    # ==========================================================================
    print("\n\n" + "="*50)
    print("               SUMMARY TEST RUN REPORT")
    print("="*50)
    for name, res in results.items():
        print(f"{name:35} | Status: {res['review_status']:8} | Time: {res['time']:6.2f}s | LLM: {res['llm_8b']:2}")
    print("="*50)
    
    print("[Uvicorn] Stopping background mock and API servers...")
    mock_server.stop()
    api_server.stop()
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
