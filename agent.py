import os
import warnings
import time
from dotenv import load_dotenv
from fpdf import FPDF 

# 1. BRAIN
from langchain_groq import ChatGroq

# 2. HANDS
from langchain_core.tools import tool
from playwright.sync_api import sync_playwright

# 3. MANAGER
from langgraph.prebuilt import create_react_agent

warnings.filterwarnings("ignore")
load_dotenv()

# --- TOOL 1: THE LOGIN TESTER ---
@tool
def check_saucedemo_login(username: str, password: str = "secret_sauce"):
    """
    Tests login on 'saucedemo.com'.
    Returns success/fail message.
    If failed, SAVES a screenshot and returns the filename.
    """
    try:
        print(f"  [TESTER] 🤖 Testing Login for: '{username}'...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) 
            page = browser.new_page()
            page.goto("https://www.saucedemo.com")
            
            page.fill('#user-name', username)
            page.fill('#password', password)
            page.click('#login-button')
            time.sleep(1)
            
            if page.locator('.title').is_visible():
                return f"PASS: User '{username}' logged in successfully."
            
            elif page.locator('[data-test="error"]').is_visible():
                error_msg = page.inner_text('[data-test="error"]')
                screenshot_name = f"evidence_{username}.png"
                page.screenshot(path=screenshot_name)
                
                return f"FAIL: Login failed. Error: '{error_msg}'. Evidence saved to: {screenshot_name}"
            
            else:
                return "FAIL: Unknown state."

    except Exception as e:
        return f"Tool Error: {e}"

# --- TOOL 2: THE REPORT GENERATOR ---
@tool
def generate_pdf_report(test_summary: str, screenshot_path: str = None):
    """
    Creates a PDF report.
    IMPORTANT: calling this tool finishes the mission.
    """
    try:
        print(f"  [REPORTER] 📝 Generating PDF Report...")
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Automated Test Report", ln=1, align='C')
        pdf.ln(10)
        
        # Summary
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=f"Test Findings:\n{test_summary}")
        pdf.ln(10)
        
        # Attach Image
        if screenshot_path and os.path.exists(screenshot_path):
            pdf.cell(200, 10, txt="Visual Evidence:", ln=1)
            pdf.image(screenshot_path, w=100)
            print(f"  [REPORTER] 📎 Attached evidence: {screenshot_path}")
            
        filename = "Final_Test_Report.pdf"
        pdf.output(filename)
        
        # --- THE FIX IS HERE ---
        # We shout "MISSION COMPLETE" to the AI so it stops looping.
        return f"FINAL ANSWER: The PDF report has been generated as '{filename}'. The testing mission is 100% complete. You must stop now."

    except Exception as e:
        return f"Report Failed: {e}"

def main():
    print("Connecting to Groq Brain (Llama 3.3)...")
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

    tools = [check_saucedemo_login, generate_pdf_report]
    llm_with_tools = llm.bind_tools(tools)
    agent_executor = create_react_agent(llm_with_tools, tools)

    print("\n--- AI TEST MANAGER STARTED ---")
    
    question = (
        "1. Test login for 'locked_out_user'."
        "2. If it fails, generate a PDF report."
        "3. Once the report is generated, stop immediately."
    )
    
    print(f"User Request: {question}")
    
    # --- THE PROMPT FIX ---
    system_instruction = (
        "You are a QA Automation Agent."
        "Execute the test. If you need to generate a report, do it ONCE."
        "After generating the report, output a final text summary and STOP."
        "Do not loop."
    )

    try:
        response = agent_executor.invoke(
            {
                "messages": [
                    ("system", system_instruction),
                    ("human", question)
                ]
            },
            # We also lower the limit so it can't loop forever even if it tries
            config={"recursion_limit": 5} 
        )
        print("\n--- MISSION COMPLETE ---")
        print(response["messages"][-1].content)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()