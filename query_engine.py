from __future__ import annotations

import logging
from dataclasses import dataclass
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "engineering_college.db"

logger = logging.getLogger("query_engine")


@dataclass
class QueryResult:
    title: str
    summary: str
    columns: list[str]
    rows: list[tuple[Any, ...]]
    note: str | None = None
    source: str = "rule-based"       # "ai", "semantic", "text-to-sql", "rule-based"
    generated_sql: str | None = None  # set by text_to_sql layer, shown in UI


DEPARTMENT_ALIASES: dict[str, str] = {
    # ── Computer Science ────────────────────────────────────────────────────
    "computer science engineering":       "Computer Science",
    "computer science and engineering":   "Computer Science",
    "computer science":                   "Computer Science",
    "computer engineering":               "Computer Science",
    "cse":                                "Computer Science",
    "cs":                                 "Computer Science",

    # ── Mechanical Engineering ───────────────────────────────────────────────
    "mechanical engineering":             "Mechanical Engineering",
    "mechanical":                         "Mechanical Engineering",
    "mech engineering":                   "Mechanical Engineering",
    "mech":                               "Mechanical Engineering",
    "me":                                 "Mechanical Engineering",

    # ── Civil Engineering ────────────────────────────────────────────────────
    "civil engineering":                  "Civil Engineering",
    "civil":                              "Civil Engineering",
    "ce":                                 "Civil Engineering",

    # ── Electrical Engineering ───────────────────────────────────────────────
    "electrical engineering":             "Electrical Engineering",
    "electrical":                         "Electrical Engineering",
    "eee":                                "Electrical Engineering",
    "ee":                                 "Electrical Engineering",

    # ── Electronics & Communication Engineering ──────────────────────────────
    "electronics and communication engineering": "Electronics & Communication Engineering",
    "electronics & communication engineering":   "Electronics & Communication Engineering",
    "electronics communication engineering":     "Electronics & Communication Engineering",
    "electronics and communication":             "Electronics & Communication Engineering",
    "electronics communication":                 "Electronics & Communication Engineering",
    "electronics":                               "Electronics & Communication Engineering",
    "ece":                                       "Electronics & Communication Engineering",
    "e and c":                                   "Electronics & Communication Engineering",
    "ec":                                        "Electronics & Communication Engineering",

    # ── Chemical Engineering ─────────────────────────────────────────────────
    "chemical engineering":               "Chemical Engineering",
    "chemical":                           "Chemical Engineering",
    "chem engineering":                   "Chemical Engineering",
    "chem":                               "Chemical Engineering",
    "che":                                "Chemical Engineering",

    # ── Biotechnology ────────────────────────────────────────────────────────
    "biotechnology":                      "Biotechnology",
    "bio technology":                     "Biotechnology",
    "bio tech":                           "Biotechnology",
    "biotech":                            "Biotechnology",
    "bt":                                 "Biotechnology",

    # ── Information Technology ───────────────────────────────────────────────
    "information technology":             "Information Technology",
    "information tech":                   "Information Technology",
    "info technology":                    "Information Technology",
    "info tech":                          "Information Technology",
    "it":                                 "Information Technology",

    # ── Automobile Engineering ───────────────────────────────────────────────
    "automobile engineering":             "Automobile Engineering",
    "automobile":                         "Automobile Engineering",
    "auto engineering":                   "Automobile Engineering",
    "auto":                               "Automobile Engineering",
    "ae":                                 "Automobile Engineering",

    # ── Aerospace Engineering ────────────────────────────────────────────────
    "aerospace engineering":              "Aerospace Engineering",
    "aerospace":                          "Aerospace Engineering",
    "aero engineering":                   "Aerospace Engineering",
    "aero":                               "Aerospace Engineering",
    "ase":                                "Aerospace Engineering",
}


# Queries that list all departments
DEPT_LIST_PHRASES: tuple[str, ...] = (
    "list all engineering departments",
    "all engineering departments",
    "departments available",
    "list all departments",
    "list departments",
    "show departments",
    "show all departments",
    "available departments",
    "engineering branches",
    "what branches",
    "available streams",
    "all departments",
    "what departments",
    "engineering streams",
    "branches available",
    "which departments",
    "department list",
)

# Queries about academic years
YEAR_LIST_PHRASES: tuple[str, ...] = (
    "list all years available",
    "years available",
    "show all years",
    "list all years",
    "available years",
    "all years",
    "which years",
    "year list",
)

# Queries about academic history / transcript for a roll number
HISTORY_PHRASES: tuple[str, ...] = (
    "full academic history",
    "academic history",
    "academic record",
    "marks history",
    "student report",
    "complete performance",
    "transcript",
    "full history",
    "complete record",
    "all marks",
    "entire history",
)
SUBJECT_MARKS_PHRASES: tuple[str, ...] = (
    "subject wise marks",
    "subject-wise marks",
    "subject marks",
    "subject scores",
    "marks per subject",
    "marks of each subject",
    "subject-level marks",
    "marks for each subject",
)

# Queries about semester performance for a roll number
SEMESTER_PHRASES: tuple[str, ...] = (
    "semester wise performance",
    "semester-wise performance",
    "semester performance",
    "sem-wise performance",
    "semwise performance",
    "semester report",
    "semester marks",
    "semester results",
    "sem wise marks",
    "performance by semester",
    "semester averages",
)

# Queries counting passed students (department + year required)
PASS_PHRASES: tuple[str, ...] = (
    "how many students passed",
    "passed in",
    "passed students",
    "number of students passed",
    "students who passed",
    "pass count",
)

# Queries counting failed students (department + year required)
FAIL_PHRASES: tuple[str, ...] = (
    "how many students failed",
    "failed in",
    "failed students",
    "number of students failed",
    "students who failed",
    "fail count",
)

# Queries for department toppers
TOPPER_PHRASES: tuple[str, ...] = (
    "show toppers in",
    "toppers in",
    "top performers in",
    "top students in",
    "best students in",
    "highest scorers in",
    "rank holders in",
    "topper",
    "top student",
    "best student",
    "highest scorer",
    "rank holder",
    "top performer",
    "best performer",
    "highest marks",
    "best academic",
    "highest average",
)

# Queries for students failing more than 2 subjects (global)
FAIL_MANY_PHRASES: tuple[str, ...] = (
    "failed in more than 2 subjects",
    "failed more than 2 subjects",
    "students who failed in more than 2 subjects",
    "failed in more than two subjects",
    "more than two subjects failed",
    "backlog students",
    "students with backlogs",
    "academic failures",
    "students with multiple failures",
    "multiple backlogs",
    "failed multiple subjects",
    "more than 2 subjects",
    "more than two subjects",
)

# Queries for average marks by department (global)
DEPT_AVG_PHRASES: tuple[str, ...] = (
    "average marks by department",
    "department average marks",
    "average by department",
    "dept average",
    "department average",
    "average marks department",
    "department performance",
    "academic performance",
    "mean score by department",
    "which department has the best",
    "best performing department",
    "department ranking",
    "performance ranking",
)

# Queries for average marks by subject (global)
SUBJECT_AVG_PHRASES: tuple[str, ...] = (
    "average marks by subject",
    "subject average marks",
    "average by subject",
    "subject average",
    "mean score by subject",
    "subject performance",
    "marks per subject on average",
    "average result by subject",
)

# Phrases that suggest the user wants roll numbers listed
ROLL_LIST_PHRASES: tuple[str, ...] = (
    "roll numbers in",
    "list the students with roll numbers",
    "show the list of students with roll numbers",
    "roll number list",
    "student roll numbers",
    "list roll numbers",
    "roll nos",
)

# Phrases that suggest listing all students in a department (no year)
STUDENT_LIST_PHRASES: tuple[str, ...] = (
    "show students",
    "student list",
    "department roster",
    "enrolled students",
    "who studies in",
    "all students in",
    "list all students",
    "list students",
    "students in",
    "students enrolled in",
)

def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path or DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def normalize_text(text: str) -> str:
    """
    Normalise a question string for phrase-matching.
    Converts to lowercase, replaces '&' with 'and', strips punctuation,
    and collapses whitespace.
    """
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def resolve_department(question: str) -> str | None:
    """
    Resolve a free-form question string to a canonical department name.
    Aliases are matched longest-first so multi-word aliases take priority
    over shorter abbreviations.
    """
    normalized = normalize_text(question)
    for alias, canonical in sorted(DEPARTMENT_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if f" {alias} " in f" {normalized} ":
            return canonical
    return None


def resolve_year(question: str) -> int | None:
    """Extract a year (1–4) from ordinal expressions like '3rd year'."""
    match = re.search(r"\b([1-4])(?:st|nd|rd|th)?\s+year\b", question.lower())
    if match:
        return int(match.group(1))
    return None


def resolve_roll_no(question: str) -> str | None:
    """Extract a roll number in the format YYYY-DEPT-NNN."""
    match = re.search(r"\b\d{4}-[A-Z]{2,5}-\d{3}\b", question.upper())
    if match:
        return match.group(0)
    return None


def execute_query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with get_connection() as connection:
        cursor = connection.execute(sql, tuple(params))
        return cursor.fetchall()


def scalar_query(sql: str, params: Iterable[Any] = ()) -> Any:
    with get_connection() as connection:
        cursor = connection.execute(sql, tuple(params))
        row = cursor.fetchone()
        return row[0] if row else None


# ---------------------------------------------------------------------------
# SQL query functions
# Each function corresponds to one intent.  They contain only hand-written,
# parameterised SQL — no user input is ever interpolated directly.
# ---------------------------------------------------------------------------

def list_departments() -> QueryResult:
    rows = execute_query(
        """
        SELECT department_name, department_code
        FROM departments
        ORDER BY department_name
        """
    )
    return QueryResult(
        title="Engineering Departments",
        summary=f"{len(rows)} departments available.",
        columns=["Department", "Code"],
        rows=[(row[0], row[1]) for row in rows],
    )


def list_years() -> QueryResult:
    rows = [(1, 2, 1), (2, 4, 3), (3, 6, 5), (4, 8, 7)]
    return QueryResult(
        title="Academic Years",
        summary="Years available in the database.",
        columns=["Year", "Current Semester", "Completed Semesters"],
        rows=rows,
    )


def students_by_department(department: str) -> QueryResult:
    rows = execute_query(
        """
        SELECT s.roll_no, s.student_name, s.age, s.gender, s.home_city, d.department_name,
               s.current_year, s.current_semester, s.batch_year
        FROM students s
        JOIN departments d ON d.department_id = s.department_id
        WHERE d.department_name = ?
        ORDER BY s.current_year, s.roll_no
        """,
        (department,),
    )
    return QueryResult(
        title=f"Students in {department}",
        summary=f"{len(rows)} students found.",
        columns=["Roll No", "Name", "Age", "Gender", "Home City", "Department", "Year", "Current Sem", "Batch"],
        rows=[tuple(row) for row in rows],
    )


def students_by_department_and_year(department: str, year: int) -> QueryResult:
    rows = execute_query(
        """
        SELECT s.roll_no, s.student_name, s.age, s.gender, s.home_city, d.department_name,
               s.current_year, s.current_semester, s.batch_year
        FROM students s
        JOIN departments d ON d.department_id = s.department_id
        WHERE d.department_name = ? AND s.current_year = ?
        ORDER BY s.roll_no
        """,
        (department, year),
    )
    return QueryResult(
        title=f"{year} Year Students in {department}",
        summary=f"{len(rows)} students found.",
        columns=["Roll No", "Name", "Age", "Gender", "Home City", "Department", "Year", "Current Sem", "Batch"],
        rows=[tuple(row) for row in rows],
    )


def students_with_roll_numbers(department: str) -> QueryResult:
    rows = execute_query(
        """
        SELECT s.roll_no, s.student_name, s.current_year, s.current_semester
        FROM students s
        JOIN departments d ON d.department_id = s.department_id
        WHERE d.department_name = ?
        ORDER BY s.roll_no
        """,
        (department,),
    )
    return QueryResult(
        title=f"Roll Numbers for {department}",
        summary=f"{len(rows)} student records found.",
        columns=["Roll No", "Name", "Year", "Current Sem"],
        rows=[tuple(row) for row in rows],
    )


def academic_history(roll_no: str) -> QueryResult:
    student = execute_query(
        """
        SELECT s.roll_no, s.student_name, s.age, s.gender, s.home_city,
               d.department_name, s.current_year, s.current_semester, s.batch_year
        FROM students s
        JOIN departments d ON d.department_id = s.department_id
        WHERE s.roll_no = ?
        """,
        (roll_no,),
    )
    if not student:
        return QueryResult(
            title="Student not found",
            summary=f"No student found for roll number {roll_no}.",
            columns=[],
            rows=[],
        )

    rows = execute_query(
        """
        SELECT m.semester, sub.subject_name, m.marks, m.result
        FROM marks m
        JOIN subjects sub ON sub.subject_id = m.subject_id
        WHERE m.roll_no = ?
        ORDER BY m.semester, sub.subject_name
        """,
        (roll_no,),
    )
    student_row = student[0]
    summary = (
        f"{student_row['student_name']} ({student_row['roll_no']}) - "
        f"{student_row['department_name']}, Year {student_row['current_year']}"
    )
    return QueryResult(
        title=f"Academic History - {student_row['student_name']}",
        summary=summary,
        columns=["Semester", "Subject", "Marks", "Result"],
        rows=[tuple(row) for row in rows],
    )


def subject_wise_marks(roll_no: str) -> QueryResult:
    student = execute_query(
        "SELECT student_name FROM students WHERE roll_no = ?",
        (roll_no,),
    )
    if not student:
        return QueryResult(
            title="Student not found",
            summary=f"No student found for roll number {roll_no}.",
            columns=[],
            rows=[],
        )

    rows = execute_query(
        """
        SELECT m.semester, sub.subject_name, m.marks, m.result
        FROM marks m
        JOIN subjects sub ON sub.subject_id = m.subject_id
        WHERE m.roll_no = ?
        ORDER BY m.semester, sub.subject_name
        """,
        (roll_no,),
    )
    return QueryResult(
        title=f"Subject-wise Marks - {student[0]['student_name']}",
        summary=f"{len(rows)} subject records found for {roll_no}.",
        columns=["Semester", "Subject", "Marks", "Result"],
        rows=[tuple(row) for row in rows],
    )


def semester_performance(roll_no: str) -> QueryResult:
    student = execute_query(
        "SELECT student_name FROM students WHERE roll_no = ?",
        (roll_no,),
    )
    if not student:
        return QueryResult(
            title="Student not found",
            summary=f"No student found for roll number {roll_no}.",
            columns=[],
            rows=[],
        )

    rows = execute_query(
        """
        SELECT m.semester,
               ROUND(AVG(m.marks), 2) AS average_marks,
               SUM(CASE WHEN m.result = 'Fail' THEN 1 ELSE 0 END) AS failed_subjects,
               COUNT(*) AS subjects_attempted
        FROM marks m
        WHERE m.roll_no = ?
        GROUP BY m.semester
        ORDER BY m.semester
        """,
        (roll_no,),
    )
    return QueryResult(
        title=f"Semester-wise Performance - {student[0]['student_name']}",
        summary=f"Performance summary for {roll_no}.",
        columns=["Semester", "Average Marks", "Failed Subjects", "Subjects Attempted"],
        rows=[tuple(row) for row in rows],
    )


def passed_and_failed_counts(department: str, year: int) -> QueryResult:
    rows = execute_query(
        """
        WITH student_summary AS (
            SELECT s.roll_no,
                   SUM(CASE WHEN m.result = 'Fail' THEN 1 ELSE 0 END) AS failed_subjects
            FROM students s
            JOIN departments d ON d.department_id = s.department_id
            JOIN marks m ON m.roll_no = s.roll_no
            WHERE d.department_name = ? AND s.current_year = ?
            GROUP BY s.roll_no
        )
        SELECT
            SUM(CASE WHEN failed_subjects = 0 THEN 1 ELSE 0 END) AS passed_students,
            SUM(CASE WHEN failed_subjects > 0 THEN 1 ELSE 0 END) AS failed_students,
            COUNT(*) AS total_students
        FROM student_summary
        """,
        (department, year),
    )
    row = rows[0] if rows else (0, 0, 0)
    return QueryResult(
        title=f"Pass/Fail Summary - {department}, Year {year}",
        summary="Students are counted as passed only if all completed subject marks are 40 or above.",
        columns=["Passed Students", "Failed Students", "Total Students"],
        rows=[tuple(row)],
    )


def toppers_by_department(department: str) -> QueryResult:
    rows = execute_query(
        """
        SELECT s.roll_no,
               s.student_name,
               s.current_year,
               ROUND(AVG(m.marks), 2) AS average_marks,
               SUM(CASE WHEN m.result = 'Fail' THEN 1 ELSE 0 END) AS failed_subjects
        FROM students s
        JOIN departments d ON d.department_id = s.department_id
        JOIN marks m ON m.roll_no = s.roll_no
        WHERE d.department_name = ?
        GROUP BY s.roll_no
        ORDER BY average_marks DESC, failed_subjects ASC, s.roll_no ASC
        LIMIT 10
        """,
        (department,),
    )
    return QueryResult(
        title=f"Top Performers - {department}",
        summary="Top 10 students ranked by average marks across completed semesters.",
        columns=["Roll No", "Name", "Year", "Average Marks", "Failed Subjects"],
        rows=[tuple(row) for row in rows],
    )


def failed_more_than_two_subjects() -> QueryResult:
    rows = execute_query(
        """
        SELECT s.roll_no,
               s.student_name,
               d.department_name,
               s.current_year,
               SUM(CASE WHEN m.result = 'Fail' THEN 1 ELSE 0 END) AS failed_subjects,
               ROUND(AVG(m.marks), 2) AS average_marks
        FROM students s
        JOIN departments d ON d.department_id = s.department_id
        JOIN marks m ON m.roll_no = s.roll_no
        GROUP BY s.roll_no
        HAVING failed_subjects > 2
        ORDER BY failed_subjects DESC, average_marks ASC, s.roll_no
        """
    )
    return QueryResult(
        title="Students Failed in More Than 2 Subjects",
        summary=f"{len(rows)} students found.",
        columns=["Roll No", "Name", "Department", "Year", "Failed Subjects", "Average Marks"],
        rows=[tuple(row) for row in rows],
    )


def average_marks_by_department() -> QueryResult:
    rows = execute_query(
        """
        SELECT d.department_name, ROUND(AVG(m.marks), 2) AS average_marks
        FROM students s
        JOIN departments d ON d.department_id = s.department_id
        JOIN marks m ON m.roll_no = s.roll_no
        GROUP BY d.department_name
        ORDER BY average_marks DESC, d.department_name
        """
    )
    return QueryResult(
        title="Average Marks by Department",
        summary="Average of all completed subject marks by department.",
        columns=["Department", "Average Marks"],
        rows=[tuple(row) for row in rows],
    )


def average_marks_by_subject() -> QueryResult:
    rows = execute_query(
        """
        SELECT sub.subject_name,
               d.department_name,
               sub.semester,
               ROUND(AVG(m.marks), 2) AS average_marks
        FROM marks m
        JOIN subjects sub ON sub.subject_id = m.subject_id
        JOIN departments d ON d.department_id = sub.department_id
        GROUP BY sub.subject_name, d.department_name, sub.semester
        ORDER BY average_marks DESC, sub.subject_name
        """
    )
    return QueryResult(
        title="Average Marks by Subject",
        summary="Average of all subject marks grouped by subject and department.",
        columns=["Subject", "Department", "Semester", "Average Marks"],
        rows=[tuple(row) for row in rows],
    )


# ---------------------------------------------------------------------------
# AI intent → SQL function dispatch table
# ----------------------------------------
# Maps every supported intent string (from ai_service.SUPPORTED_INTENTS) to a
# callable that accepts keyword arguments matching the IntentResult fields.
# Keeping this as a dispatch table avoids a long if/elif chain and makes it
# trivial to add new intents later.
# ---------------------------------------------------------------------------
def _dispatch_ai_intent(intent_result: Any) -> QueryResult | None:
    """
    Dispatch an ai_service.IntentResult to the corresponding SQL function.

    Returns a QueryResult tagged with source="ai", or None if the intent
    cannot be dispatched (missing required field, unknown intent).
    """
    intent = intent_result.intent
    dept = intent_result.department
    year = intent_result.year
    roll = intent_result.roll_no

    result: QueryResult | None = None

    if intent == "list_departments":
        result = list_departments()
    elif intent == "list_years":
        result = list_years()
    elif intent == "students_by_department" and dept:
        result = students_by_department(dept)
    elif intent == "students_by_department_year" and dept and year:
        result = students_by_department_and_year(dept, year)
    elif intent == "students_with_roll_numbers" and dept:
        result = students_with_roll_numbers(dept)
    elif intent == "academic_history" and roll:
        result = academic_history(roll)
    elif intent == "subject_wise_marks" and roll:
        result = subject_wise_marks(roll)
    elif intent == "semester_performance" and roll:
        result = semester_performance(roll)
    elif intent == "pass_fail_counts" and dept and year:
        result = passed_and_failed_counts(dept, year)
    elif intent == "department_toppers" and dept:
        result = toppers_by_department(dept)
    elif intent == "failed_more_than_two":
        result = failed_more_than_two_subjects()
    elif intent in ("average_marks_by_department", "department_average_marks"):
        result = average_marks_by_department()
    elif intent == "average_marks_by_subject":
        result = average_marks_by_subject()

    if result is not None:
        result.source = "ai"
    return result


# ---------------------------------------------------------------------------
# Main routing function
# ---------------------------------------------------------------------------
def route_question(question: str) -> QueryResult:
    """
    Route a natural-language question to the appropriate query function.

    Resolution order:
    1. Gemini AI intent extraction  (ai_service.py)       — free-form English
    2. Rule-based keyword matching  (this file)           — exact/near-exact phrases
    3. Semantic similarity search   (semantic_engine.py)  — vector embedding fallback
    4. "I could not parse that"                           — last resort

    This waterfall ensures 100% backward compatibility: existing rule-based
    queries continue to work even if the AI layer is disabled or fails.
    """
    # ── Step 1: AI-assisted intent extraction ────────────────────────────────
    # Import is deferred here so that if google-generativeai is not installed
    # the server still starts and the rule-based engine works normally.
    try:
        from ai_service import extract_intent  # noqa: PLC0415
        ai_intent = extract_intent(question)
        if ai_intent is not None:
            dispatched = _dispatch_ai_intent(ai_intent)
            if dispatched is not None:
                logger.info("AI resolved question to intent=%r", ai_intent.intent)
                return dispatched
            # If dispatch returned None (e.g. missing field) fall through
            logger.warning(
                "AI intent %r could not be dispatched — falling back to rule-based engine.",
                ai_intent.intent,
            )
    except Exception as exc:  # noqa: BLE001
        # Catch-all: any unexpected error in the AI layer must not surface to
        # the user — the rule-based engine is the guaranteed fallback.
        logger.warning("Unexpected error in AI layer: %s — using rule-based engine.", exc)

    # ── Step 2: Rule-based keyword / alias matching ───────────────────────────
    normalized = normalize_text(question)
    department = resolve_department(question)
    year = resolve_year(question)
    roll_no = resolve_roll_no(question)

    # Departments list
    if any(phrase in normalized for phrase in DEPT_LIST_PHRASES):
        return list_departments()

    # Years list
    if any(phrase in normalized for phrase in YEAR_LIST_PHRASES):
        return list_years()

    # ── Global aggregate queries are checked BEFORE per-student queries ──────
    # This ordering prevents 'average marks by subject' from being intercepted
    # by SUBJECT_MARKS_PHRASES which also contains 'subject marks' variants.

    # Average marks by department (global)
    if any(phrase in normalized for phrase in DEPT_AVG_PHRASES):
        return average_marks_by_department()

    # Average marks by subject (global)
    if any(phrase in normalized for phrase in SUBJECT_AVG_PHRASES):
        return average_marks_by_subject()

    # Students failing more than 2 subjects (global)
    if any(phrase in normalized for phrase in FAIL_MANY_PHRASES):
        return failed_more_than_two_subjects()

    # ── Per-student queries (require a roll number) ──────────────────────────

    # Academic history (roll number required)
    if roll_no and any(phrase in normalized for phrase in HISTORY_PHRASES):
        return academic_history(roll_no)

    # Subject-wise marks (roll number required)
    if roll_no and any(phrase in normalized for phrase in SUBJECT_MARKS_PHRASES):
        return subject_wise_marks(roll_no)

    if any(phrase in normalized for phrase in SUBJECT_MARKS_PHRASES):
        return QueryResult(
            title="Roll number needed",
            summary="Please include a roll number to show subject-wise marks.",
            columns=["Example"],
            rows=[("Show subject-wise marks of roll number 2025-CSE-001.",)],
        )

    # Semester performance (roll number required)
    if roll_no and any(phrase in normalized for phrase in SEMESTER_PHRASES):
        return semester_performance(roll_no)

    if any(phrase in normalized for phrase in SEMESTER_PHRASES):
        return QueryResult(
            title="Roll number needed",
            summary="Please include a roll number to show semester-wise performance.",
            columns=["Example"],
            rows=[("Show semester-wise performance of roll number 2025-CSE-001.",)],
        )

    # ── Department-scoped queries ────────────────────────────────────────────

    # Pass/fail counts (department + year required)
    if department and year and any(phrase in normalized for phrase in PASS_PHRASES):
        return passed_and_failed_counts(department, year)

    if department and year and any(phrase in normalized for phrase in FAIL_PHRASES):
        result = passed_and_failed_counts(department, year)
        result.title = f"Failure Summary - {department}, Year {year}"
        result.summary = "Students are counted as failed if at least one completed subject mark is below 40."
        if result.rows:
            passed_students, failed_students, total_students = result.rows[0]
            result.columns = ["Failed Students", "Passed Students", "Total Students"]
            result.rows = [(failed_students, passed_students, total_students)]
        return result

    # Toppers (department required)
    if department and any(phrase in normalized for phrase in TOPPER_PHRASES):
        return toppers_by_department(department)

    # Students with roll numbers for a department
    if department and any(phrase in normalized for phrase in ROLL_LIST_PHRASES):
        return students_with_roll_numbers(department)

    # Students in department + year
    if department and year:
        return students_by_department_and_year(department, year)

    # All students in a department
    if department:
        return students_by_department(department)

    # ── Step 3: Semantic similarity search ──────────────────────────────────
    # Only reached when both AI intent extraction and rule-based matching fail.
    # Embeds the question and finds the closest pre-embedded intent cluster.
    try:
        from semantic_engine import engine as _sem_engine  # noqa: PLC0415
        from ai_service import IntentResult as _IntentResult  # noqa: PLC0415
        matched_intent = _sem_engine.find_intent(question)
        if matched_intent:
            # Re-use the same AI dispatch table — semantic layer is just a
            # smarter way to determine the intent, SQL functions are unchanged.
            synthetic = _IntentResult(
                intent=matched_intent,
                department=resolve_department(question),
                year=resolve_year(question),
                roll_no=resolve_roll_no(question),
            )
            dispatched = _dispatch_ai_intent(synthetic)
            if dispatched is not None:
                dispatched.source = "semantic"
                logger.info(
                    "Semantic engine resolved question to intent=%r", matched_intent
                )
                return dispatched
    except Exception as exc:  # noqa: BLE001
        logger.warning("Semantic engine error: %s — returning could-not-parse.", exc)

    # ── Step 4: Text-to-SQL ───────────────────────────────────────────────
    # Last resort: Gemini generates a SELECT query from scratch using the
    # database schema as context.  Only questions that genuinely cannot be
    # answered reach this layer (e.g. city-based, age-based, custom analytics).
    try:
        from text_to_sql import run_text_to_sql  # noqa: PLC0415
        sql_result = run_text_to_sql(question)
        if sql_result is not None:
            logger.info(
                "Text-to-SQL resolved question source=%r title=%r",
                sql_result.source, sql_result.title,
            )
            return sql_result
    except Exception as exc:  # noqa: BLE001
        logger.warning("Text-to-SQL error: %s — returning could-not-parse.", exc)

    # Catch-all: question not recognised by any layer
    return QueryResult(
        title="I could not parse that question",
        summary="Try one of the supported question patterns below.",
        columns=["Supported examples"],
        rows=[
            ("List all engineering departments.",),
            ("What branches are available?",),
            ("List all students in Computer Science.",),
            ("Who studies in CSE?",),
            ("List all years available.",),
            ("Show all 3rd year Mechanical Engineering students.",),
            ("Show all 2nd year ME students.",),
            ("How many students passed in Computer Science, 2nd year?",),
            ("How many students failed in Civil Engineering, 3rd year?",),
            ("Show toppers in Information Technology.",),
            ("Who are the top performers in ECE?",),
            ("Best students in Biotechnology?",),
            ("Show students who failed in more than 2 subjects.",),
            ("Show backlog students.",),
            ("Show average marks by department.",),
            ("Which department has the best academic performance?",),
            ("Show average marks by subject.",),
            ("Show full academic history of roll number 2025-CSE-001.",),
            ("Show subject-wise marks of roll number 2025-CSE-001.",),
            ("Show semester-wise performance of roll number 2025-CSE-001.",),
            ("Show the list of students with roll numbers in Electrical Engineering.",),
        ],
        note="Tip: include a department name, year, or roll number for specific questions. Abbreviations like CSE, ECE, ME, IT are supported.",
    )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def database_stats() -> dict[str, int]:
    return {
        "departments": int(scalar_query("SELECT COUNT(*) FROM departments") or 0),
        "students":    int(scalar_query("SELECT COUNT(*) FROM students") or 0),
        "subjects":    int(scalar_query("SELECT COUNT(*) FROM subjects") or 0),
        "marks":       int(scalar_query("SELECT COUNT(*) FROM marks") or 0),
    }
