import os
import warnings
import time
from dotenv import load_dotenv

# 1. BRAIN
from langchain_groq import ChatGroq

# 2. HANDS
from langchain_core.tools import tool
from playwright.sync_api import sync_playwright

# 3. MANAGER
from langgraph.prebuilt import create_react_agent

warnings.filterwarnings("ignore")
load_dotenv()

# --- THE TOOL ---
@tool
def search_duckduckgo(query: str):
    """
    Performs a web search on DuckDuckGo.
    Use this tool when you need to find facts, news, prices, or technical documentation.
    """
    try:
        print(f"  [TOOL] 🔍 Searching for: '{query}'...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) 
            page = browser.new_page()
            
            page.goto("https://duckduckgo.com")
            page.wait_for_load_state("domcontentloaded")
            
            page.locator('input[name="q"]').click()
            page.fill('input[name="q"]', query)
            time.sleep(1) 
            page.press('input[name="q"]', 'Enter')
            
            # Wait longer for complex results
            page.wait_for_selector('.react-results--main', timeout=6000)
            
            # Read more content (3000 chars) to get details
            content = page.inner_text('.react-results--main')[:3000]
            print(f"  [TOOL] ✅ Found data.")
            
            return f"SEARCH RESULTS for '{query}':\n{content}..."
            
    except Exception as e:
        return f"Error during search: {e}"

def main():
    # --- SETUP BRAIN ---
    print("Connecting to Groq Brain (Llama 3.3)...")
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.2 # Slight creativity allowed for planning
    )

    # --- SETUP MANAGER ---
    tools = [search_duckduckgo]
    llm_with_tools = llm.bind_tools(tools)
    agent_executor = create_react_agent(llm_with_tools, tools)

    # --- RUN MISSION ---
    print("\n--- DEEP RESEARCH AGENT STARTED ---")
    
    # A Multi-Step Question
    question = "Compare the battery life of the iPhone 15 Pro Max vs Samsung S24 Ultra. Then tell me which one is better for a 10-hour flight."
    
    print(f"User Question: {question}")
    
    # --- THE PLANNER PROMPT ---
    # We tell the AI to explicitly think in steps.
    system_instruction = (
        "You are a thorough Technical Researcher. "
        "When asked a comparison question, you must:"
        "1. Search for data on the first item."
        "2. Search for data on the second item."
        "3. Compare them based on the user's specific scenario."
        "Do NOT guess. Use the 'search_duckduckgo' tool multiple times if needed."
        "Output your final answer clearly."
    )

    try:
        # We increase recursion_limit to 10 to allow multiple search steps
        response = agent_executor.invoke(
            {
                "messages": [
                    ("system", system_instruction),
                    ("human", question)
                ]
            },
            config={"recursion_limit": 10} 
        )
        
        print("\n--- FINAL RESEARCH REPORT ---")
        print(response["messages"][-1].content)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()