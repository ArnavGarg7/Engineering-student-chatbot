import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath("."))
from text_to_sql import verify_sql_matches_entities

def test_verifier_pass():
    query = "Show all Computer Science students"
    filters = {"department": "Computer Science"}
    sql = "SELECT * FROM students s JOIN departments d ON s.department_id = d.department_id WHERE d.department_name LIKE '%Computer Science%'"
    
    result = verify_sql_matches_entities(sql, filters, query)
    assert result is True, "Verifier should PASS for valid SQL"
    print("test_verifier_pass passed.")

def test_verifier_fail():
    query = "Show all departments"
    filters = {}
    sql = "SELECT * FROM departments WHERE department_name LIKE '%Mechanical%'"
    
    result = verify_sql_matches_entities(sql, filters, query)
    assert result is False, "Verifier should FAIL for hallucinated SQL"
    print("test_verifier_fail passed.")

if __name__ == "__main__":
    test_verifier_pass()
    test_verifier_fail()
    print("All verifier tests passed!")
