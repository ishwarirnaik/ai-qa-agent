import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("CRITICAL ERROR: 'GROQ_API_KEY' not found in .env file.")
    print("Please check your .env file and try again.")
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
        print(response.text)
        exit()
        
    data = response.json()
    models = data.get('data', [])
    
    print("\n--- CURRENTLY ACTIVE GROQ MODELS ---")
    print(f"{'MODEL ID':<40} | {'OWNER':<15}")
    print("-" * 60)
    
    for model in models:
        model_id = model['id']
        owner = model['owned_by']
        print(f"{model_id:<40} | {owner:<15}")
        
    print("\n------------------------------------")
    print("Copy one of the 'MODEL ID' values above to use in agent.py")

except Exception as e:
    print(f"Network Error: {e}")