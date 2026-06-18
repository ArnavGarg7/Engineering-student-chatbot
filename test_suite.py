import requests
import json
import time

API_URL = "http://127.0.0.1:8000/api/chat"

TESTS = [
    {"name": "Test 1: English Query", "message": "How many students are from Delhi?"},
    {"name": "Test 2: Hindi Query", "message": "दिल्ली से कितने छात्र हैं?"},
    {"name": "Test 3: Out of Scope", "message": "Tell me a joke about dogs."},
    {"name": "Test 4: RAG & DB", "message": "List all CS students."},
]

def run_tests():
    session_id = None
    
    for t in TESTS:
        print(f"\n================ {t['name']} ================")
        print(f"Query: {t['message']}")
        
        payload = {"message": t['message']}
        if session_id:
            payload["session_id"] = session_id
            
        try:
            start_time = time.time()
            resp = requests.post(API_URL, json=payload, timeout=30)
            elapsed = time.time() - start_time
            
            if resp.status_code == 200:
                data = resp.json()
                session_id = data.get("session_id")
                print(f"Response ({elapsed:.2f}s) [Source: {data.get('source')}]:\n{data.get('text')}")
                if data.get("data") and data["data"].get("context_used"):
                    ctx = data["data"]["context_used"]
                    print("\nDemo Mode Metrics:")
                    for k, v in ctx.items():
                        if "Retrieved" in k or "Provider" in k or "Fallback" in k:
                            print(f"  {k}: {v}")
            else:
                print(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"Request failed: {e}")
            
if __name__ == "__main__":
    run_tests()
