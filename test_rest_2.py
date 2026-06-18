import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent?key={api_key}"

payload = {
    "model": "models/embedding-001",
    "content": {
        "parts": [{"text": "hello world"}]
    }
}

response = requests.post(url, json=payload)
print(response.status_code)
print(response.json())
