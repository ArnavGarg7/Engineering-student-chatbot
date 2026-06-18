import requests
import json
import time

API_URL = "http://127.0.0.1:8000/api/chat"

def print_result(name, query, resp_data):
    print(f"\n================ {name} ================")
    print(f"Query: {query}")
    print(f"Response: {resp_data.get('text')}")
    if resp_data.get('active_filters'):
        print(f"Filters: {resp_data.get('active_filters')}")
    else:
        print("Filters: None")

def run_tests():
    # 1. English
    r1 = requests.post(API_URL, json={"message": "How many students from Delhi?"}).json()
    print_result("Test 1: English", "How many students from Delhi?", r1)

    # 2. Hindi (Should normalize to Delhi and answer in Hindi)
    r2 = requests.post(API_URL, json={"message": "दिल्ली से कितने छात्र हैं?"}).json()
    print_result("Test 2: Hindi", "दिल्ली से कितने छात्र हैं?", r2)

    # 3. Spanish
    r3 = requests.post(API_URL, json={"message": "¿Cuántos estudiantes son de Delhi?"}).json()
    print_result("Test 3: Spanish", "¿Cuántos estudiantes son de Delhi?", r3)

    # 4. Context Follow-up (Session)
    print("\n--- Test 4: Follow-up Memory ---")
    s4 = requests.post(API_URL, json={"message": "Show all Computer Science students"}).json()
    session_id = s4.get("session_id")
    print_result("Turn 1", "Show all Computer Science students", s4)
    
    s4_2 = requests.post(API_URL, json={"session_id": session_id, "message": "Only from Delhi"}).json()
    print_result("Turn 2", "Only from Delhi", s4_2)
    
    s4_3 = requests.post(API_URL, json={"session_id": session_id, "message": "Only third year"}).json()
    print_result("Turn 3", "Only third year", s4_3)

    # 5. Language strictness
    r5 = requests.post(API_URL, json={"message": "Which semester is hardest?"}).json()
    print_result("Test 5: Short Question English Default", "Which semester is hardest?", r5)
    
    # 6. Normal mode leak test
    print("\n--- Test 6: Normal Mode Leak Test ---")
    if "Provider" in r1.get("text", "") or "Latency" in r1.get("text", "") or "Execution Time" in r1.get("text", ""):
        print("FAIL: Demo mode metadata leaked into response text.")
    else:
        print("PASS: No metadata leakage.")

if __name__ == "__main__":
    run_tests()
