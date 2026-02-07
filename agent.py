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

# --- TOOL: THE ADVANCED LOGIN TESTER ---
@tool
def check_saucedemo_login(username: str, password: str = "secret_sauce"):
    """
    Tests the login on 'saucedemo.com' with a SPECIFIC username.
    Returns the success message or the specific error message found on screen.
    Also saves a screenshot if login fails.
    """
    try:
        print(f"  [TESTER] 🤖 Testing Login for User: '{username}'...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) 
            page = browser.new_page()
            
            # 1. Navigate
            page.goto("https://www.saucedemo.com")
            
            # 2. Type Credentials (Dynamic!)
            page.fill('input[id="user-name"]', username)
            page.fill('input[id="password"]', password)
            
            # 3. Click
            page.click('input[id="login-button"]')
            time.sleep(1) # Wait for animation
            
            # 4. INTELLIGENT CHECK
            # We look for TWO things: Success (Products) OR Failure (Error Box)
            
            if page.locator('.title').is_visible():
                # SUCCESS PATH
                return f"✅ SUCCESS: User '{username}' logged in successfully."
            
            elif page.locator('[data-test="error"]').is_visible():
                # FAILURE PATH
                error_msg = page.inner_text('[data-test="error"]')
                
                # TAKE EVIDENCE
                screenshot_name = f"evidence_failure_{username}.png"
                page.screenshot(path=screenshot_name)
                
                return f"❌ FAILED: Login failed with error: '{error_msg}'. (Screenshot saved to {screenshot_name})"
            
            else:
                return "⚠️ UNKNOWN STATE: Neither success nor error message found."

    except Exception as e:
        return f"Tool Crash: {e}"

def main():
    # --- SETUP BRAIN ---
    print("Connecting to Groq Brain (Llama 3.3)...")
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0
    )

    # --- SETUP MANAGER ---
    tools = [check_saucedemo_login]
    llm_with_tools = llm.bind_tools(tools)
    agent_executor = create_react_agent(llm_with_tools, tools)

    # --- RUN MISSION ---
    print("\n--- AI SENIOR QA ENGINEER STARTED ---")
    
    # COMPLEX REQUEST:
    # We ask the agent to run TWO tests and compare them.
    question = (
        "I need you to test the login scenarios for Saucedemo."
        "First, test with 'standard_user'."
        "Then, test with 'locked_out_user'."
        "Finally, summarize the difference in behavior between them."
    )
    
    print(f"User Request: {question}")
    
    system_instruction = (
        "You are a Senior QA Engineer."
        "You must execute every test requested."
        "If a test fails, report the specific error message returned by the tool."
    )

    try:
        response = agent_executor.invoke(
            {
                "messages": [
                    ("system", system_instruction),
                    ("human", question)
                ]
            },
            config={"recursion_limit": 10} # Allow enough steps for multiple tests
        )
        
        print("\n--- FINAL TEST REPORT ---")
        print(response["messages"][-1].content)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()