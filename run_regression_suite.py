import os
import sys
import io
import asyncio
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath("."))
from app_server import app, ChatRequest

# We can test via calling the chat_endpoint directly or using FastAPI TestClient
from fastapi.testclient import TestClient

client = TestClient(app)

def run_tests():
    print("--- Running Regression Suite ---")
    session_id = "test_regression_session_1"
    
    tests = [
        {"msg": "Hi", "expected_cat": "greeting", "expected_text": "I'm SPEED AI"},
        {"msg": "Who are you?", "expected_cat": "identity", "expected_text": "SPEED AI"},
        {"msg": "How", "expected_cat": "clarification", "expected_text": "more details"},
        {"msg": "Show all Computer Science students", "expected_cat": "academic_query"},
        {"msg": "How many students from Delhi are there?", "expected_cat": "academic_query"},
        {"msg": "दिल्ली से कितने छात्र हैं?", "expected_cat": "academic_query"},
        {"msg": "¿Cuántos estudiantes de Delhi hay?", "expected_cat": "academic_query"},
        {"msg": "How many female students are there?", "expected_cat": "academic_query"},
        {"msg": "Show me the list of all departments", "expected_cat": "academic_query"}
    ]
    
    failures = 0
    for t in tests:
        print(f"Testing: '{t['msg']}'")
        resp = client.post("/api/chat", json={"session_id": session_id, "message": t['msg']})
        if resp.status_code != 200:
            print(f"FAIL: HTTP {resp.status_code}")
            failures += 1
            continue
            
        data = resp.json()
        
        # We can check text
        if "expected_text" in t:
            if t["expected_text"].lower() not in data["text"].lower():
                print(f"FAIL: Expected text '{t['expected_text']}' not found. Got: {data['text']}")
                failures += 1
                continue
        print(f"PASS: {t['msg']}")

    print("\n--- Testing Context-Memory Chain ---")
    session_id2 = "test_regression_session_2"
    chain = [
        "Show all Computer Science students",
        "How many of them are from Delhi?",
        "Only the third year ones"
    ]
    for msg in chain:
        print(f"Testing Chain: '{msg}'")
        resp = client.post("/api/chat", json={"session_id": session_id2, "message": msg})
        if resp.status_code != 200:
            print(f"FAIL: HTTP {resp.status_code}")
            failures += 1
            continue
        print(f"PASS: {msg}")

    if failures > 0:
        print(f"\nRegression Suite FAILED with {failures} errors.")
        sys.exit(1)
    else:
        print("\nAll regression tests PASSED!")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
