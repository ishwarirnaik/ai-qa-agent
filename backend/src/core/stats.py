from contextvars import ContextVar
import contextlib

# Thread/Task-local tracker for LLM invocation statistics and healing count
llm_counts_var: ContextVar[dict | None] = ContextVar("llm_counts", default=None)

@contextlib.contextmanager
def track_llm_calls():
    token = llm_counts_var.set({
        "llama-3.1-8b-instant": 0,
        "llama-3.3-70b-versatile": 0,
        "heals": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "assertions_passed": 0,
        "generated_scenarios": 0
    })
    try:
        yield llm_counts_var.get()
    finally:
        llm_counts_var.reset(token)

def increment_llm_call(model_name: str):
    counts = llm_counts_var.get()
    if counts is not None:
        if "8b" in model_name:
            counts["llama-3.1-8b-instant"] = counts.get("llama-3.1-8b-instant", 0) + 1
        elif "70b" in model_name:
            counts["llama-3.3-70b-versatile"] = counts.get("llama-3.3-70b-versatile", 0) + 1
        else:
            counts[model_name] = counts.get(model_name, 0) + 1

def increment_heals():
    counts = llm_counts_var.get()
    if counts is not None:
        counts["heals"] = counts.get("heals", 0) + 1

def increment_cache_hit():
    counts = llm_counts_var.get()
    if counts is not None:
        counts["cache_hits"] = counts.get("cache_hits", 0) + 1

def increment_cache_miss():
    counts = llm_counts_var.get()
    if counts is not None:
        counts["cache_misses"] = counts.get("cache_misses", 0) + 1

def increment_assertions_passed():
    counts = llm_counts_var.get()
    if counts is not None:
        counts["assertions_passed"] = counts.get("assertions_passed", 0) + 1

def set_generated_scenarios(num: int):
    counts = llm_counts_var.get()
    if counts is not None:
        counts["generated_scenarios"] = num

def get_current_stats() -> dict:
    counts = llm_counts_var.get()
    if counts is not None:
        return counts.copy()
    return {
        "llama-3.1-8b-instant": 0, 
        "llama-3.3-70b-versatile": 0, 
        "heals": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "assertions_passed": 0,
        "generated_scenarios": 0
    }

def dump_benchmark_csv(state: dict):
    import os
    import csv
    
    file_path = os.path.join(os.path.dirname(__file__), '../../tests/benchmark_results.csv')
    file_exists = os.path.exists(file_path)
    
    with open(file_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "execution_id", "website", "task", "success", "execution_time",
                "llm_calls", "recovery_attempts", "cache_hits", "cache_misses",
                "generated_scenarios", "assertions_passed", "export_success"
            ])
            
        writer.writerow([
            state.get("execution_id", ""),
            state.get("target_url", ""),
            state.get("user_prompt", ""),
            state.get("review_status") == "PASS",
            f"{state.get('execution_time', 0):.2f}",
            state.get("llm_calls", 0),
            state.get("recovery_attempts", 0),
            state.get("cache_hits", 0),
            state.get("cache_misses", 0),
            state.get("generated_scenarios", 0),
            state.get("assertions_passed", 0),
            state.get("export_success", False)
        ])
