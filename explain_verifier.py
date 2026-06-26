import os, sys, json
sys.path.append(os.path.abspath("."))
from llm_provider import manager

prompt = """You are a strict SQL Verification guardrail.
The user asked: "Show all Computer Science students."
Active conversation filters: {"department": "Computer Science"}
Generated SQL: SELECT s.student_name, s.roll_no
FROM students s
JOIN departments d ON s.department_id = d.department_id
WHERE d.department_name LIKE '%Computer Science%'
LIMIT 200

TASK:
1. Extract requested entities (department, city, year, semester) from the user query and active filters.
2. Check if the Generated SQL introduces ANY of these filters (department, city, year, semester) in its WHERE or JOIN clauses that were NOT requested.
3. If the SQL is safe and ONLY uses requested filters, respond with YES (PASS). If it hallucinates unrequested filters, respond with NO (FAIL).

Explain your reasoning, then output YES or NO."""

ans, _, _, _ = manager.generate_with_retry(prompt, task_type="conversation")
print("Response:", ans)
