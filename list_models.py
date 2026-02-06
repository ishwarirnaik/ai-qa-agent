import os
from dotenv import load_dotenv
import google.generativeai as genai

# 1. Load your key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("ERROR: API Key not found in .env file")
else:
    genai.configure(api_key=api_key)
    print(f"Checking models for API Key: {api_key[:5]}...")

    print("\n--- AVAILABLE MODELS ---")
    try:
        # We list all models and filter for ones that can 'generateContent'
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Model Name: {m.name}")
    except Exception as e:
        print(f"Error connecting to Google: {e}")