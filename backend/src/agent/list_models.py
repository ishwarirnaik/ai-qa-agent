import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("CRITICAL ERROR: 'GROQ_API_KEY' not found in .env file.")
    exit()

url = "https://api.groq.com/openai/v1/models"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

print(f"Contacting Groq API to fetch active models...")

try:
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: API returned status code {response.status_code}")
        exit()
        
    data = response.json()
    models = data.get('data', [])
    
    print("\n--- CURRENTLY ACTIVE GROQ MODELS ---")
    print(f"{'MODEL ID':<40} | {'OWNER':<15}")
    print("-" * 60)
    
    for model in models:
        print(f"{model['id']:<40} | {model['owned_by']:<15}")
        
    print("-" * 60)
    print("Copy one of the 'MODEL ID' values to use in agent.py")

except Exception as e:
    print(f"Network Error: {e}")