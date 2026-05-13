import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)

print("Sending request to the Brain (Groq)...")
try:
    response = llm.invoke("Explain the concept of DOM-based web testing in one sentence.")
    print("\n--- AI RESPONSE ---")
    print(response.content)
except Exception as e:
    print(f"\nERROR: {e}")
    print("\nTIP: Check if 'GROQ_API_KEY' is inside your .env file!")