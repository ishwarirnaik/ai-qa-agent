import warnings

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


def build_llm(model: str = "llama-3.1-8b-instant", temperature: float = 0):
    print(f"Connecting to Groq Brain ({model})...")
    return ChatGroq(model=model, temperature=temperature)


def build_qa_agent():
    llm = build_llm()

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
    return build_llm(model="llama-3.3-70b-versatile", temperature=0)


def build_reviewer_agent():
    return build_llm(model="llama-3.3-70b-versatile", temperature=0)


def build_recovery_agent():
    return build_llm(model="llama-3.3-70b-versatile", temperature=0)
