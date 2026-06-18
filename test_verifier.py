import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath("."))
from llm_provider import manager
import json



def run_test():
    user_query = "Show all Computer Science students"
    context_filters = {"department": "Computer Science"}
    test_sql = "SELECT s.student_name, s.roll_no FROM students s JOIN departments d ON s.department_id = d.department_id WHERE d.department_name LIKE '%Computer Science%'"
    
    prompt = f"""You are a strict SQL Verification guardrail.
The user asked: "{user_query}"
Active conversation filters: {json.dumps(context_filters, ensure_ascii=False) if context_filters else "{}"}
Generated SQL: {test_sql}

TASK:
1. Extract requested entities (department, city, year, semester) from the user query and active filters.
2. Check if the Generated SQL introduces ANY of these filters (department, city, year, semester) in its WHERE or JOIN clauses that were NOT requested.
3. If the SQL is safe and ONLY uses requested filters, respond with YES (PASS). If it hallucinates unrequested filters, respond with NO (FAIL).

Respond ONLY with YES or NO."""

    print("Prompt:")
    print(prompt)
    print("\n--- Sending to LLM ---")
    
    ans, provider, _, _ = manager.generate_with_retry(prompt, task_type="conversation")
    print("\nLLM Response:")
    print(ans)
    print("Provider:", provider)
    
if __name__ == "__main__":
    run_test()
