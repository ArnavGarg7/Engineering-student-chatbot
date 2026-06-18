import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

try:
    print("Testing text-embedding-004")
    res = client.models.embed_content(model="text-embedding-004", contents="hello")
    print("Success text-embedding-004:", res.embeddings[0].values[:3])
except Exception as e:
    print("Failed text-embedding-004:", e)
