import warnings
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src.agent.browser import (
    analyze_page_elements,
    assert_text_visible,
    click_element,
    fill_input,
    generate_pdf_report,
    get_page_state,
    navigate_to_url,
    press_key,
    take_evidence_screenshot,
    wait_for_page_ready,
    scroll_page,
)

warnings.filterwarnings("ignore")
load_dotenv()


class TrackingChatGroq(ChatGroq):
    def _rotate_key(self):
        keys = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
        if not keys:
            # Fall back to single key
            key = os.getenv("GROQ_API_KEY")
            if key:
                keys = [key]
        if keys:
            # Cycle keys
            current_key = self.groq_api_key
            if current_key in keys:
                idx = (keys.index(current_key) + 1) % len(keys)
                next_key = keys[idx]
            else:
                next_key = keys[0]
            self.groq_api_key = next_key
            # Update client settings
            if hasattr(self, 'client') and self.client:
                self.client.api_key = next_key
            print(f"[Rate Limit] Swapped Groq API key to: ...{next_key[-6:]}")
            return True
        return False

    def invoke(self, *args, **kwargs):
        import time
        import re
        from src.core.stats import increment_llm_call
        increment_llm_call(self.model_name)
        
        max_retries = 6
        backoff = 2
        for attempt in range(max_retries):
            try:
                return super().invoke(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate_limit" in err_str or "rate limit" in err_str:
                    if self._rotate_key():
                        print("[Rate Limit] Key rotated. Retrying immediately...")
                        continue
                    
                    wait_time = 10.0
                    match = re.search(r"try again in (\d+m)?([\d\.]+)s", err_str)
                    if match:
                        minutes = match.group(1)
                        seconds = float(match.group(2))
                        wait_time = seconds
                        if minutes:
                            wait_time += float(minutes[:-1]) * 60
                        wait_time += 2.0
                    else:
                        wait_time = backoff ** attempt + 5
                        
                    print(f"[Rate Limit] Hit 429 rate limit. Waiting for {wait_time:.2f} seconds before retry (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise e
        return super().invoke(*args, **kwargs)
        
    async def ainvoke(self, *args, **kwargs):
        import asyncio
        import re
        from src.core.stats import increment_llm_call
        increment_llm_call(self.model_name)
        
        max_retries = 6
        backoff = 2
        for attempt in range(max_retries):
            try:
                return await super().ainvoke(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate_limit" in err_str or "rate limit" in err_str:
                    if self._rotate_key():
                        print("[Rate Limit] Key rotated. Retrying immediately...")
                        continue
                        
                    wait_time = 10.0
                    match = re.search(r"try again in (\d+m)?([\d\.]+)s", err_str)
                    if match:
                        minutes = match.group(1)
                        seconds = float(match.group(2))
                        wait_time = seconds
                        if minutes:
                            wait_time += float(minutes[:-1]) * 60
                        wait_time += 2.0
                    else:
                        wait_time = backoff ** attempt + 5
                        
                    print(f"[Rate Limit] Hit 429 rate limit. Waiting for {wait_time:.2f} seconds before retry (Attempt {attempt+1}/{max_retries})...")
                    await asyncio.sleep(wait_time)
                else:
                    raise e
        return await super().ainvoke(*args, **kwargs)
        
    def stream(self, *args, **kwargs):
        from src.core.stats import increment_llm_call
        increment_llm_call(self.model_name)
        return super().stream(*args, **kwargs)
        
    async def astream(self, *args, **kwargs):
        from src.core.stats import increment_llm_call
        increment_llm_call(self.model_name)
        async for chunk in super().astream(*args, **kwargs):
            yield chunk


def build_llm(model: str = "llama-3.1-8b-instant", temperature: float = 0):
    print(f"Connecting to Groq Brain ({model})...")
    return TrackingChatGroq(model=model, temperature=temperature)


def build_qa_agent():
    model = os.getenv("EXECUTOR_MODEL", "llama-3.1-8b-instant")
    llm = build_llm(model=model)

    tools = [
        navigate_to_url,
        wait_for_page_ready,
        get_page_state,
        analyze_page_elements,
        click_element,
        fill_input,
        press_key,
        assert_text_visible,
        take_evidence_screenshot,
        generate_pdf_report,
        scroll_page,
    ]

    llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)
    return create_react_agent(llm_with_tools, tools)


def build_planner_agent():
    model = os.getenv("PLANNER_MODEL", "llama-3.3-70b-versatile")
    return build_llm(model=model, temperature=0)


def build_reviewer_agent():
    model = os.getenv("REVIEWER_MODEL", "llama-3.3-70b-versatile")
    return build_llm(model=model, temperature=0)


def build_recovery_agent():
    model = os.getenv("RECOVERY_MODEL", "llama-3.3-70b-versatile")
    return build_llm(model=model, temperature=0)
