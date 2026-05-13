import sys
import os
import asyncio

# --- THE WINDOWS FIX ---
# This allows Streamlit to open external programs (like Chrome) on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import streamlit as st
from src.agent.agent import run_test_mission

# ... rest of your code remains exactly the same ...

# Page Config
st.set_page_config(page_title="AI QA Agent", layout="centered")

st.title("Autonomous QA Agent")
st.markdown("### The 'Glass Box' Execution Dashboard")
st.write("Enter a natural language mission below. The agent will autonomously reason, execute browser actions, and generate forensic reports.")

# User Input
prompt = st.text_area(
    "Mission Parameters:", 
    "Test the login for 'locked_out_user'. If it fails, generate a PDF report AND you MUST include the screenshot evidence in the report. Then stop."
)

if st.button("Execute Mission"):
    with st.spinner("Agent is thinking and executing... (Watch your VS Code terminal for real-time logic)"):
        # This calls your LangGraph Brain!
        final_summary = run_test_mission(prompt)
        
    st.success("Mission Complete!")
    
    st.markdown("### Agent's Final Report")
    st.info(final_summary)
    
    # Provide the PDF Download Button
    pdf_path = "Final_Test_Report.pdf"
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as pdf_file:
            st.download_button(
                label="Download Forensic PDF Report",
                data=pdf_file,
                file_name="QA_Test_Report.pdf",
                mime="application/pdf"
            )