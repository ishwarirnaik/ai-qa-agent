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

# --- TOOL 1: THE RESEARCHER ---
@tool
def search_duckduckgo(query: str):
    """
    Use this to find general information or expected behavior.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) 
            page = browser.new_page()
            page.goto("https://duckduckgo.com")
            page.fill('input[name="q"]', query)
            page.press('input[name="q"]', 'Enter')
            page.wait_for_selector('.react-results--main', timeout=5000)
            content = page.inner_text('.react-results--main')[:1000]
            return f"SEARCH DATA: {content}..."
    except Exception as e:
        return f"Search Error: {e}"

# --- TOOL 2: THE TESTER (NEW!) ---
@tool
def check_website_health(url: str):
    """
    Use this to TEST a specific website URL.
    It checks: Status Code (200 OK), Load Time, and Link Counts.
    """
    try:
        print(f"  [TESTER] 🩺 Starting Health Check for: {url}...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) # Headless=False so you can see it
            page = browser.new_page()
            
            # 1. Start Timer
            start_time = time.time()
            
            # 2. Navigate
            try:
                response = page.goto(url, timeout=10000) # 10s timeout
            except Exception as nav_err:
                return f"❌ CRITICAL: Could not reach {url}. Error: {nav_err}"
            
            # 3. Stop Timer
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            # 4. Gather Metrics
            status_code = response.status
            page_title = page.title()
            link_count = page.locator('a').count()
            image_count = page.locator('img').count()
            
            # 5. Analyze Results
            health_status = "✅ HEALTHY" if status_code == 200 else "⚠️ UNHEALTHY"
            
            report = (
                f"--- TEST REPORT FOR {url} ---\n"
                f"STATUS: {health_status} (Code: {status_code})\n"
                f"LOAD TIME: {duration} seconds\n"
                f"TITLE: '{page_title}'\n"
                f"ELEMENTS: {link_count} Links, {image_count} Images found.\n"
            )
            
            print(f"  [TESTER] 📄 Report generated.")
            return report

    except Exception as e:
        return f"Test Tool Failed: {e}"

def main():
    # --- SETUP BRAIN ---
    print("Connecting to Groq Brain (Llama 3.3)...")
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0
    )

    # --- SETUP MANAGER ---
    # We give it BOTH tools now
    tools = [search_duckduckgo, check_website_health]
    llm_with_tools = llm.bind_tools(tools)
    agent_executor = create_react_agent(llm_with_tools, tools)

    # --- RUN MISSION ---
    print("\n--- AI QA ENGINEER STARTED ---")
    
    # CASE 1: A working website
    # question = "Test the website 'https://example.com' and tell me if it is healthy."
    
    # CASE 2: A broken/non-existent website (Try this to see it fail!)
    question = "Test the website 'https://this-site-does-not-exist-12345.com' and report the error."
    
    print(f"User Request: {question}")
    
    system_instruction = (
        "You are a QA Automation Engineer. "
        "Your job is to run tests on websites using the 'check_website_health' tool. "
        "Analyze the report it gives you. "
        "If the Status Code is not 200, report it as a FAILURE. "
        "If Load Time is > 2 seconds, warn that it is SLOW."
    )

    try:
        response = agent_executor.invoke(
            {
                "messages": [
                    ("system", system_instruction),
                    ("human", question)
                ]
            }
        )
        
        print("\n--- FINAL TEST SUMMARY ---")
        print(response["messages"][-1].content)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()