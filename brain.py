import os
from dotenv import load_dotenv
# FIX: We import Groq instead of Google
from langchain_groq import ChatGroq

load_dotenv()

# FIX: We use the free Llama model hosted by Groq
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)

print("Sending request to the Brain (Groq)...")
try:
    response = llm.invoke("Explain software testing in one sentence.")
    print("\n--- AI RESPONSE ---")
    print(response.content)
except Exception as e:
    print(f"\nERROR: {e}")
    print("\nTIP: Check if 'GROQ_API_KEY' is inside your .env file!")