import os
import sys
import time
import asyncio
import threading
import uvicorn
import csv
import json
from collections import defaultdict
from playwright.async_api import async_playwright

os.environ["PLANNER_MODEL"] = "llama-3.1-8b-instant"
os.environ["REVIEWER_MODEL"] = "llama-3.1-8b-instant"
os.environ["RECOVERY_MODEL"] = "llama-3.1-8b-instant"
os.environ["EXECUTOR_MODEL"] = "llama-3.1-8b-instant"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from tests.mock_site import app
from src.api.database import _in_memory_selector_cache
from src.graph.qa_workflow import run_qa_workflow
from src.graph.state import QAState
from src.core.stats import track_llm_calls
from src.services.artifact_service import ArtifactService

# Configuration
TRIALS_PER_CATEGORY = 5

CATEGORIES = [
    {
        "name": "Login Validation",
        "url": "http://127.0.0.1:8080/login?drift=extreme",
        "prompt": "Log in with username admin and password admin123, click Sign In, then assert that the welcome text is visible on the dashboard."
    },
    {
        "name": "Form Submission",
        "url": "http://127.0.0.1:8080/contact?drift=extreme",
        "prompt": "Fill out the contact form with name John Doe and select Technical Support from the topic dropdown. Click Send Message and assert that the success banner is visible."
    },
    {
        "name": "Search Interaction",
        "url": "http://127.0.0.1:8080/search?drift=extreme",
        "prompt": "Search for 'Smartphone' in the directory. Click Search and assert that the results for 'Smartphone' are displayed."
    },
    {
        "name": "Multi-step Navigation",
        "url": "http://127.0.0.1:8080/wizard/step1?drift=extreme",
        "prompt": "Navigate through the 3-step wizard by clicking the 'Go to Step X' links on each page. Once on step 3, assert that the 'Wizard Complete' text is visible."
    },
    {
        "name": "E-commerce Navigation",
        "url": "http://127.0.0.1:8080/products?drift=extreme",
        "prompt": "From the products page, click 'Add to Cart' for Smartphone X. On the cart page, click 'Proceed to Checkout'. On the checkout page, assert that the secure checkout form is visible."
    }
]

class ServerThread(threading.Thread):
    def __init__(self, app, host="127.0.0.1", port=8080):
        super().__init__()
        self.config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)
        self.daemon = True

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True

async def warmup():
    print("[Warmup] Spawning Chromium warmup context...")
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        c = await b.new_context()
        pg = await c.new_page()
        await pg.goto("http://127.0.0.1:8080/login")
        await b.close()

def identify_failure_cause(error_msg: str, execution_history: list) -> str:
    if not error_msg and not execution_history:
        return "None"
        
    full_text = str(error_msg).lower() + " ".join(execution_history).lower()
    
    if "timeout" in full_text or "waiting for selector" in full_text:
        return "invalid_selectors"
    elif "navigation" in full_text or "net::" in full_text:
        return "navigation_failures"
    elif "not visible" in full_text or "hidden" in full_text:
        return "hidden_elements"
    elif "detached" in full_text or "stale" in full_text:
        return "asynchronous_dom_updates"
    elif "load state" in full_text or "networkidle" in full_text:
        return "delayed_rendering"
        
    return "unknown"

async def run_scenario(category, mode_name, is_cold, trial):
    if is_cold:
        _in_memory_selector_cache.clear()

    start_time = time.time()
    execution_id = f"bench_{category['name'].replace(' ', '_')}_{mode_name.replace(' ', '_')}_{trial}"
    
    artifacts = ArtifactService(execution_id)
    artifacts.prepare_run_directory()
    
    state: QAState = {
        "execution_id": execution_id,
        "target_url": category["url"],
        "user_prompt": category["prompt"],
        "user_id": "eval_user",
        "status": "created",
        "recovery_attempts": 0,
        "execution_history": [],
        "final_response": None,
        "memory_enabled": True,
        "recovery_enabled": True,
        "reviewer_enabled": True,
        "llm_calls": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "generated_scenarios": 0,
        "assertions_passed": 0,
        "export_success": False
    }
    
    with track_llm_calls() as counts:
        final_state = await run_qa_workflow(state)
        total_llm_calls = sum(counts.values()) if isinstance(counts, dict) else final_state.get("llm_calls", 0)
        
    duration = time.time() - start_time
    success = final_state.get("review_status") == "PASS"
    
    # Check trace export success
    trace_path = os.path.join(artifacts.run_dir, "trace.json")
    trace_success = os.path.exists(trace_path)
    
    error_msg = final_state.get("error", "")
    history = final_state.get("execution_history", [])
    interruption_cause = identify_failure_cause(error_msg, history) if not success else "None"
    
    return {
        "workflow_name": category["name"],
        "mode": mode_name,
        "success": success,
        "execution_time": duration,
        "llm_calls": total_llm_calls,
        "recovery_attempts": final_state.get("recovery_attempts", 0),
        "cache_hits": final_state.get("cache_hits", 0),
        "cache_misses": final_state.get("cache_misses", 0),
        "generated_scenarios": final_state.get("generated_scenarios", 1), # default at least 1
        "assertions_passed": final_state.get("assertions_passed", 0),
        "exported_script_success": final_state.get("export_success", False),
        "json_trace_success": trace_success,
        "selector_regeneration_required": final_state.get("recovery_attempts", 0) > 0,
        "interruption_cause": interruption_cause
    }

async def main():
    os.makedirs(os.path.join(os.path.dirname(__file__), "exports"), exist_ok=True)
    
    print("[Server] Starting Local Mock Server Thread...")
    server = ServerThread(app, port=8080)
    server.start()
    await asyncio.sleep(2)
    
    await warmup()
    
    all_results = []
    
    for category in CATEGORIES:
        print(f"\n================ EVALUATING: {category['name']} ================")
        
        for trial in range(1, TRIALS_PER_CATEGORY + 1):
            print(f"\n--- {category['name']} (Trial {trial}) ---")
            
            # Cold Path
            print("[Cold Path] Executing...")
            cold_res = await run_scenario(category, "Cold Path", is_cold=True, trial=trial)
            all_results.append(cold_res)
            
            # Warm Path
            print("[Warm Path] Executing...")
            warm_res = await run_scenario(category, "Warm Path", is_cold=False, trial=trial)
            all_results.append(warm_res)

    print("\n[Exporting] Generating CSV report...")
    csv_path = os.path.join(os.path.dirname(__file__), "exports", "benchmark_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "workflow_name", "mode", "success", "execution_time", "llm_calls", 
            "recovery_attempts", "cache_hits", "cache_misses", "generated_scenarios",
            "assertions_passed", "exported_script_success", "json_trace_success",
            "selector_regeneration_required", "interruption_cause"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for res in all_results:
            writer.writerow(res)
            
    print("[Aggregating] Generating summaries...")
    summary = defaultdict(lambda: defaultdict(list))
    failure_counts = defaultdict(int)
    
    for res in all_results:
        wf = res["workflow_name"]
        mode = res["mode"]
        summary[wf][mode].append(res)
        
        if not res["success"]:
            failure_counts[res["interruption_cause"]] += 1
            
    aggregated_summary = {}
    
    for wf, modes in summary.items():
        aggregated_summary[wf] = {}
        for mode, runs in modes.items():
            n = len(runs)
            aggregated_summary[wf][mode] = {
                "average_execution_time": sum(r["execution_time"] for r in runs) / n,
                "average_recovery_attempts": sum(r["recovery_attempts"] for r in runs) / n,
                "average_cache_hits": sum(r["cache_hits"] for r in runs) / n,
                "average_cache_misses": sum(r["cache_misses"] for r in runs) / n,
                "assertion_success_rate": sum(r["assertions_passed"] for r in runs) / (sum(r["generated_scenarios"] for r in runs) or 1),
                "export_success_rate": sum(1 for r in runs if r["exported_script_success"]) / n,
                "success_rate": sum(1 for r in runs if r["success"]) / n
            }
            
    json_path = os.path.join(os.path.dirname(__file__), "exports", "benchmark_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(aggregated_summary, f, indent=4)
        
    print("[Report] Generating TXT report...")
    txt_path = os.path.join(os.path.dirname(__file__), "exports", "execution_analysis.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=== BENCHMARK EXECUTION ANALYSIS ===\n\n")
        f.write("1. WARM-PATH VS COLD-PATH PERFORMANCE COMPARISON\n")
        f.write("-" * 50 + "\n")
        for wf, modes in aggregated_summary.items():
            f.write(f"Workflow: {wf}\n")
            c = modes.get("Cold Path", {})
            w = modes.get("Warm Path", {})
            f.write(f"  Cold Path -> Time: {c.get('average_execution_time', 0):.2f}s, Success: {c.get('success_rate', 0)*100:.1f}%, Recs: {c.get('average_recovery_attempts', 0):.1f}\n")
            f.write(f"  Warm Path -> Time: {w.get('average_execution_time', 0):.2f}s, Success: {w.get('success_rate', 0)*100:.1f}%, Recs: {w.get('average_recovery_attempts', 0):.1f}\n")
            f.write("\n")
            
        f.write("\n2. MOST COMMON FAILURE CAUSES\n")
        f.write("-" * 50 + "\n")
        if not failure_counts:
            f.write("No failures encountered during execution.\n")
        else:
            sorted_fails = sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)
            for cause, count in sorted_fails:
                f.write(f"  {cause}: {count} occurrences\n")
                
    print("[Done] All exports generated successfully in tests/exports/")
    server.stop()
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
