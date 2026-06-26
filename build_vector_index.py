import os
import sys
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

BUSINESS_RULES = [
    {
        "id": "rule_passing",
        "type": "business_rule",
        "content": "Passing criteria: A student passes a subject if their marks are >= 40. Otherwise, the result is 'Fail'. Marks < 40 = Fail."
    },
    {
        "id": "rule_completed_semesters",
        "type": "business_rule",
        "content": "Completed semesters based on year: 1st year students have completed Sem 1 only. 2nd year completed Sem 1-3. 3rd year completed Sem 1-5. 4th year completed Sem 1-7."
    },
    {
        "id": "rule_current_semester",
        "type": "business_rule",
        "content": "Current semester constraint: The students table tracks current_semester (which is ongoing and has NO marks yet). The marks table only contains records for completed semesters."
    },
    {
        "id": "rule_toppers",
        "type": "business_rule",
        "content": "Toppers definition: A topper is the student with the highest average marks across all completed semesters in their department or overall."
    },
    {
        "id": "rule_failures",
        "type": "business_rule",
        "content": "Failures/Backlogs: Students who have result = 'Fail' in one or more subjects have backlogs or failures."
    },
    {
        "id": "rule_gender",
        "type": "business_rule",
        "content": "Gender queries: SQLite string matching is case-sensitive. ALWAYS use exact casing (e.g. `gender = 'Female'`, `gender = 'Male'`) or case-insensitive matching (`LOWER(gender) = 'female'`)."
    }
]

SQL_EXAMPLES = [
    {
        "id": "sql_avg_marks_dept",
        "type": "sql_example",
        "content": "Question: Which department has the highest average marks?\nSQL:\nSELECT d.department_name, AVG(m.marks) as average_marks\nFROM marks m\nJOIN students s ON m.roll_no = s.roll_no\nJOIN departments d ON s.department_id = d.department_id\nGROUP BY d.department_id\nORDER BY average_marks DESC\nLIMIT 1;"
    },
    {
        "id": "sql_city_toppers",
        "type": "sql_example",
        "content": "Question: Which city produces the most toppers? (Count of students with avg marks > 85 by city)\nSQL:\nSELECT home_city, COUNT(*) as topper_count\nFROM students\nWHERE roll_no IN (SELECT roll_no FROM marks GROUP BY roll_no HAVING AVG(marks) > 85)\nGROUP BY home_city\nORDER BY topper_count DESC;"
    },
    {
        "id": "sql_hardest_semester",
        "type": "sql_example",
        "content": "Question: Which semester is the hardest? (Lowest average marks)\nSQL:\nSELECT semester, AVG(marks) as average_marks\nFROM marks\nGROUP BY semester\nORDER BY average_marks ASC\nLIMIT 1;"
    },
    {
        "id": "sql_failure_rate_dept",
        "type": "sql_example",
        "content": "Question: Which department has the highest failure rate?\nSQL:\nSELECT d.department_name, SUM(CASE WHEN m.result = 'Fail' THEN 1 ELSE 0 END) * 100.0 / COUNT(m.mark_id) as failure_rate\nFROM marks m\nJOIN students s ON m.roll_no = s.roll_no\nJOIN departments d ON s.department_id = d.department_id\nGROUP BY d.department_id\nORDER BY failure_rate DESC\nLIMIT 1;"
    },
    {
        "id": "sql_percentage_delhi_cse",
        "type": "sql_example",
        "content": "Question: What percentage of students from Delhi are in CSE?\nSQL:\nSELECT (SUM(CASE WHEN d.department_code = 'CSE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as percentage_in_cse\nFROM students s\nJOIN departments d ON s.department_id = d.department_id\nWHERE s.home_city = 'Delhi';"
    },
    {
        "id": "sql_top_student_college",
        "type": "sql_example",
        "content": "Question: Who is the highest scoring student in the entire college?\nSQL:\nSELECT s.student_name, s.roll_no, AVG(m.marks) as average_marks\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nGROUP BY s.roll_no\nORDER BY average_marks DESC\nLIMIT 1;"
    },
    {
        "id": "sql_female_outperform_male",
        "type": "sql_example",
        "content": "Question: Are female students outperforming male students?\nSQL:\nSELECT s.gender, AVG(m.marks) as average_marks\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nGROUP BY s.gender;"
    },
    {
        "id": "sql_ex8",
        "type": "sql_example",
        "content": "Question: Show all Computer Science students from Delhi.\nSQL:\nSELECT s.student_name, s.roll_no\nFROM students s\nJOIN departments d ON s.department_id = d.department_id\nWHERE d.department_name LIKE '%Computer Science%' AND s.home_city = 'Delhi';"
    },
    {
        "id": "sql_ex9",
        "type": "sql_example",
        "content": "Question: Which city contributes the most students?\nSQL:\nSELECT home_city, COUNT(*) as student_count\nFROM students\nGROUP BY home_city\nORDER BY student_count DESC\nLIMIT 1;"
    },
    {
        "id": "sql_ex10",
        "type": "sql_example",
        "content": "Question: What is the average age of Biotechnology students?\nSQL:\nSELECT AVG(s.age) as average_age\nFROM students s\nJOIN departments d ON s.department_id = d.department_id\nWHERE d.department_name LIKE '%Biotechnology%';"
    },
    {
        "id": "sql_ex11",
        "type": "sql_example",
        "content": "Question: List the top 5 students in Mechanical Engineering.\nSQL:\nSELECT s.student_name, AVG(m.marks) as average_marks\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nJOIN departments d ON s.department_id = d.department_id\nWHERE d.department_code = 'ME' OR d.department_name LIKE '%Mechanical%'\nGROUP BY s.roll_no\nORDER BY average_marks DESC\nLIMIT 5;"
    },
    {
        "id": "sql_ex12",
        "type": "sql_example",
        "content": "Question: How many students have failed at least one subject?\nSQL:\nSELECT COUNT(DISTINCT roll_no) as failed_students_count\nFROM marks\nWHERE result = 'Fail';"
    },
    {
        "id": "sql_ex13",
        "type": "sql_example",
        "content": "Question: What is the pass percentage for each subject?\nSQL:\nSELECT sub.subject_name, SUM(CASE WHEN m.result = 'Pass' THEN 1 ELSE 0 END) * 100.0 / COUNT(m.mark_id) as pass_percentage\nFROM marks m\nJOIN subjects sub ON m.subject_id = sub.subject_id\nGROUP BY m.subject_id;"
    },
    {
        "id": "sql_ex14",
        "type": "sql_example",
        "content": "Question: Who are the 4th year students?\nSQL:\nSELECT student_name, roll_no\nFROM students\nWHERE current_year = 4;"
    },
    {
        "id": "sql_ex15",
        "type": "sql_example",
        "content": "Question: Which subject has the most failures?\nSQL:\nSELECT sub.subject_name, COUNT(m.mark_id) as failures\nFROM marks m\nJOIN subjects sub ON m.subject_id = sub.subject_id\nWHERE m.result = 'Fail'\nGROUP BY m.subject_id\nORDER BY failures DESC\nLIMIT 1;"
    },
    {
        "id": "sql_ex16",
        "type": "sql_example",
        "content": "Question: Show average marks for each year.\nSQL:\nSELECT s.current_year, AVG(m.marks) as avg_marks\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nGROUP BY s.current_year;"
    },
    {
        "id": "sql_ex17",
        "type": "sql_example",
        "content": "Question: How many female students are in each department?\nSQL:\nSELECT d.department_name, COUNT(s.roll_no) as female_count\nFROM students s\nJOIN departments d ON s.department_id = d.department_id\nWHERE s.gender = 'Female'\nGROUP BY d.department_id;"
    },
    {
        "id": "sql_ex18",
        "type": "sql_example",
        "content": "Question: Who is the youngest student in the college?\nSQL:\nSELECT student_name, age\nFROM students\nORDER BY age ASC\nLIMIT 1;"
    },
    {
        "id": "sql_ex19",
        "type": "sql_example",
        "content": "Question: Give a summary of student counts by year and semester.\nSQL:\nSELECT current_year, current_semester, COUNT(*) as student_count\nFROM students\nGROUP BY current_year, current_semester;"
    },
    {
        "id": "sql_ex20",
        "type": "sql_example",
        "content": "Question: Show students who scored exactly 100 in any subject.\nSQL:\nSELECT DISTINCT s.student_name, sub.subject_name\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nJOIN subjects sub ON m.subject_id = sub.subject_id\nWHERE m.marks = 100;"
    },
    {
        "id": "sql_ex21",
        "type": "sql_example",
        "content": "Question: What is the highest mark achieved in Data Structures?\nSQL:\nSELECT MAX(m.marks) as highest_mark\nFROM marks m\nJOIN subjects sub ON m.subject_id = sub.subject_id\nWHERE sub.subject_name LIKE '%Data Structures%';"
    },
    {
        "id": "sql_ex22",
        "type": "sql_example",
        "content": "Question: Find the top 3 cities with the best average marks.\nSQL:\nSELECT s.home_city, AVG(m.marks) as avg_marks\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nGROUP BY s.home_city\nORDER BY avg_marks DESC\nLIMIT 3;"
    },
    {
        "id": "sql_ex23",
        "type": "sql_example",
        "content": "Question: Which student has the highest number of backlogs?\nSQL:\nSELECT s.student_name, COUNT(*) as backlog_count\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nWHERE m.result = 'Fail'\nGROUP BY s.roll_no\nORDER BY backlog_count DESC\nLIMIT 1;"
    },
    {
        "id": "sql_ex24",
        "type": "sql_example",
        "content": "Question: How many students belong to the 2022 batch year?\nSQL:\nSELECT COUNT(*) as count_2022_batch\nFROM students\nWHERE batch_year = 2022;"
    },
    {
        "id": "sql_ex25",
        "type": "sql_example",
        "content": "Question: List the departments that have more than 500 students.\nSQL:\nSELECT d.department_name, COUNT(s.roll_no) as student_count\nFROM departments d\nJOIN students s ON d.department_id = s.department_id\nGROUP BY d.department_id\nHAVING student_count > 500;"
    },
    {
        "id": "sql_ex26",
        "type": "sql_example",
        "content": "Question: Show marks for student named 'Aarav Kumar' across all subjects.\nSQL:\nSELECT sub.subject_name, m.marks, m.semester, m.result\nFROM marks m\nJOIN subjects sub ON m.subject_id = sub.subject_id\nJOIN students s ON m.roll_no = s.roll_no\nWHERE s.student_name = 'Aarav Kumar';"
    },
    {
        "id": "sql_ex27",
        "type": "sql_example",
        "content": "Question: Compare the average marks of first year and fourth year students.\nSQL:\nSELECT current_year, AVG(m.marks) as avg_marks\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nWHERE current_year IN (1, 4)\nGROUP BY current_year;"
    },
    {
        "id": "sql_ex28",
        "type": "sql_example",
        "content": "Question: Show students who have scored >90 in more than 3 subjects.\nSQL:\nSELECT s.student_name, COUNT(m.mark_id) as high_scores\nFROM students s\nJOIN marks m ON s.roll_no = m.roll_no\nWHERE m.marks > 90\nGROUP BY s.roll_no\nHAVING high_scores > 3;"
    },
    {
        "id": "sql_ex29",
        "type": "sql_example",
        "content": "Question: What is the lowest passing mark recorded?\nSQL:\nSELECT MIN(marks) as lowest_pass\nFROM marks\nWHERE result = 'Pass';"
    },
    {
        "id": "sql_ex30",
        "type": "sql_example",
        "content": "Question: List the names of all CSE students along with their batch year.\nSQL:\nSELECT s.student_name, s.batch_year\nFROM students s\nJOIN departments d ON s.department_id = d.department_id\nWHERE d.department_code = 'CSE';"
    },
    {
        "id": "sql_ex31",
        "type": "sql_example",
        "content": "Question: What is the overall average mark across the entire college?\nSQL:\nSELECT AVG(marks) as overall_avg\nFROM marks;"
    },
    {
        "id": "sql_ex32",
        "type": "sql_example",
        "content": "Question: How many subjects does the Civil Engineering department offer in semester 3?\nSQL:\nSELECT COUNT(*) as subject_count\nFROM subjects sub\nJOIN departments d ON sub.department_id = d.department_id\nWHERE d.department_name LIKE '%Civil%' AND sub.semester = 3;"
    }
]

def build_index():
    print("Initializing ChromaDB for RAG Text-to-SQL...")
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    ef = DefaultEmbeddingFunction()
    
    # 1. Schema Collection
    try:
        chroma_client.delete_collection(name="schema_collection")
    except Exception: pass
    schema_coll = chroma_client.create_collection(name="schema_collection", embedding_function=ef, metadata={"hnsw:space": "cosine"})
    
    import database_introspection
    full_schema = database_introspection.get_full_schema()
    schema_chunks = full_schema.split("CREATE TABLE")
    valid_chunks = [f"CREATE TABLE{chunk}" for chunk in schema_chunks if chunk.strip()]
    
    if valid_chunks:
        schema_coll.add(
            ids=[f"schema_{i}" for i in range(len(valid_chunks))],
            documents=valid_chunks,
            metadatas=[{"type": "schema"} for _ in valid_chunks]
        )
        print(f"Inserted {len(valid_chunks)} schema chunks.")
    
    # 2. Business Rules Collection
    try:
        chroma_client.delete_collection(name="business_rules_collection")
    except Exception: pass
    rules_coll = chroma_client.create_collection(name="business_rules_collection", embedding_function=ef, metadata={"hnsw:space": "cosine"})
    rules_coll.add(
        ids=[c["id"] for c in BUSINESS_RULES],
        documents=[c["content"] for c in BUSINESS_RULES],
        metadatas=[{"type": c["type"]} for c in BUSINESS_RULES]
    )
    print(f"Inserted {len(BUSINESS_RULES)} business rules.")
    
    # 3. SQL Examples Collection
    try:
        chroma_client.delete_collection(name="sql_examples_collection")
    except Exception: pass
    sql_coll = chroma_client.create_collection(name="sql_examples_collection", embedding_function=ef, metadata={"hnsw:space": "cosine"})
    sql_coll.add(
        ids=[c["id"] for c in SQL_EXAMPLES],
        documents=[c["content"] for c in SQL_EXAMPLES],
        metadatas=[{"type": c["type"]} for c in SQL_EXAMPLES]
    )
    print(f"Inserted {len(SQL_EXAMPLES)} SQL examples.")

    print("Vector database built successfully at ./chroma_db")

if __name__ == "__main__":
    build_index()
