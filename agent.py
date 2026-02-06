import os
import warnings
import time
# We don't need dotenv for the key if we paste it directly, 
# but keeping it is good practice if you put GROQ_API_KEY in your .env file.
from dotenv import load_dotenv

# 1. BRAIN (We swapped Google for Groq)
from langchain_groq import ChatGroq

# 2. HANDS
from langchain_core.tools import tool
from playwright.sync_api import sync_playwright

# 3. MANAGER
from langgraph.prebuilt import create_react_agent

warnings.filterwarnings("ignore")
load_dotenv()

# --- CONFIGURATION ---
# PASTE YOUR KEY HERE if you don't want to use the .env file yet
# os.environ["GROQ_API_KEY"] = "gsk_..." 

# --- THE TOOL ---
@tool
def search_duckduckgo(query: str):
    """
    Performs a web search on DuckDuckGo to find facts.
    """
    try:
        print(f"DEBUG: Launching browser for search: '{query}'...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) 
            page = browser.new_page()
            
            print("DEBUG: Navigating to DuckDuckGo...")
            page.goto("https://duckduckgo.com")
            page.wait_for_load_state("domcontentloaded")
            
            print(f"DEBUG: Typing '{query}'...")
            page.locator('input[name="q"]').click()
            page.fill('input[name="q"]', query)
            time.sleep(1) 
            
            print("DEBUG: Hitting Enter...")
            page.press('input[name="q"]', 'Enter')
            
            print("DEBUG: Waiting for results...")
            page.wait_for_selector('.react-results--main', timeout=5000)
            
            content = page.inner_text('.react-results--main')[:1000]
            print("DEBUG: Got content.")
            
            return f"SEARCH RESULTS for '{query}':\n{content}..."
            
    except Exception as e:
        return f"Error during search: {e}"

def main():
    # --- SETUP BRAIN ---
    # We use Groq's Llama 3.3 model. It is fast and free.
    print("Connecting to Groq Brain...")
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0
    )

    # --- SETUP MANAGER ---
    tools = [search_duckduckgo]
    agent_executor = create_react_agent(llm, tools)

    # --- RUN MISSION ---
    print("--- STARTING MISSION ---")
    question = "Check who won the ao open 2026"
    print(f"User Question: {question}")
    
    try:
        response = agent_executor.invoke(
            {"messages": [("human", question)]}
        )
        
        print("\n--- FINAL RESULT ---")
        print(response["messages"][-1].content)
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nTIP: Did you set your GROQ_API_KEY?")

if __name__ == "__main__":
    main()