import sqlite3

def run_sql_validation():
    db_path = "engineering_college.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    queries = [
        "SELECT DISTINCT gender FROM students;",
        "SELECT COUNT(*) FROM students WHERE gender='Female';",
        "SELECT COUNT(*) FROM students WHERE LOWER(gender)='female';",
        "SELECT COUNT(*) FROM students WHERE gender='female';"
    ]

    print("--- SQL Validation Results ---")
    for q in queries:
        try:
            cursor.execute(q)
            results = cursor.fetchall()
            print(f"Query: {q}")
            print(f"Result: {results}\n")
        except Exception as e:
            print(f"Query: {q}")
            print(f"Error: {e}\n")

    conn.close()

if __name__ == "__main__":
    run_sql_validation()
