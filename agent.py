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
    """
    try:
        print(f"DEBUG: Launching browser for search: '{query}'...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) 
            page = browser.new_page()
            
            # Navigate
            print(f"DEBUG: Navigating to DuckDuckGo...")
            page.goto("https://duckduckgo.com")
            page.wait_for_load_state("domcontentloaded")
            
            # Type
            print(f"DEBUG: Typing query...")
            page.locator('input[name="q"]').click()
            page.fill('input[name="q"]', query)
            time.sleep(1) 
            page.press('input[name="q"]', 'Enter')
            
            # Wait
            print(f"DEBUG: Waiting for results...")
            page.wait_for_selector('.react-results--main', timeout=5000)
            
            # Read
            content = page.inner_text('.react-results--main')[:2000]
            print(f"DEBUG: Content retrieved.")
            
            return f"SEARCH RESULTS for '{query}':\n{content}..."
            
    except Exception as e:
        return f"Error during search: {e}"

def main():
    # --- SETUP BRAIN ---
    # We stick with the powerful model you wanted
    print("Connecting to Groq Brain (Llama 3.3)...")
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0
    )

    # --- SETUP MANAGER ---
    tools = [search_duckduckgo]
    
    # CODE FIX: We explicitly 'bind' the tools.
    # This forces the model to recognize them as executable functions, not text.
    llm_with_tools = llm.bind_tools(tools)
    
    # We pass the 'bound' model to the agent
    agent_executor = create_react_agent(llm_with_tools, tools)

    # --- RUN MISSION ---
    print("--- STARTING MISSION ---")
    question = "Is Ishwari Naik of KLE Tech University on LinkedIn?" 
    print(f"User Question: {question}")
    
    # CODE FIX: A forceful system prompt to stop the XML nonsense
    system_instruction = (
        "You are a researcher. "
        "You have access to a tool called 'search_duckduckgo'. "
        "You MUST call this tool to find the answer. "
        "Do not output JSON or XML as text. Just call the tool."
    )

    try:
        response = agent_executor.invoke(
            {
                "messages": [
                    ("system", system_instruction),
                    ("human", question)
                ]
            },
            config={"recursion_limit": 5}
        )
        
        print("\n--- FINAL RESULT ---")
        print(response["messages"][-1].content)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()