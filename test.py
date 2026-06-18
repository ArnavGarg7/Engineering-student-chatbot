import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
models = [m.name for m in client.models.list() if 'flash' in m.name]
for m in models:
    try:
        res = client.models.generate_content(model=m, contents='hi')
        print(f"SUCCESS: {m}")
    except Exception as e:
        print(f"FAIL: {m} - {e}")
