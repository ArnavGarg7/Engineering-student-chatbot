"""
text_to_sql.py
==============
Layer 4 of the query resolution pipeline: Text-to-SQL via Gemini.

Called only when all three previous layers (AI intent, rule-based, semantic)
have failed to handle the question.  Generates an arbitrary SELECT query from
the user's natural-language question using the database schema as context.

Security model
--------------
- Only SELECT statements are allowed (whitelist check on first token).
- A blacklist of destructive keywords blocks any unexpected model output.
- Generated SQL is executed on a read-only SQLite URI connection.
- Results are capped at MAX_ROWS rows.
- Any execution error is caught and returned as a friendly message.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger("text_to_sql")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH  = BASE_DIR / "engineering_college.db"

MAX_ROWS = 200

# Keywords that must never appear in a generated query
_BLACKLIST = frozenset([
    "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
    "TRUNCATE", "ATTACH", "DETACH", "PRAGMA", "VACUUM",
    "REPLACE", "UPSERT",
])

# Concise schema description injected into the prompt
_SCHEMA = """
departments
  department_id   INTEGER  PRIMARY KEY
  department_name TEXT     e.g. 'Computer Science', 'Mechanical Engineering'
  department_code TEXT     e.g. 'CSE', 'ME', 'ECE'

students
  roll_no          TEXT     PRIMARY KEY  format: YYYY-DEPT-NNN e.g. '2025-CSE-001'
  student_name     TEXT
  age              INTEGER  18-21
  gender           TEXT     'Male' or 'Female'
  home_city        TEXT     Indian city names e.g. 'Bengaluru', 'Junagadh'
  department_id    INTEGER  FK → departments.department_id
  current_year     INTEGER  1, 2, 3, or 4
  current_semester INTEGER  2, 4, 6, or 8  (ongoing semester)
  batch_year       INTEGER  2022-2025

subjects
  subject_id    INTEGER  PRIMARY KEY
  department_id INTEGER  FK → departments.department_id
  semester      INTEGER  1-8
  subject_code  TEXT
  subject_name  TEXT

marks
  mark_id    INTEGER  PRIMARY KEY
  roll_no    TEXT     FK → students.roll_no
  subject_id INTEGER  FK → subjects.subject_id
  semester   INTEGER  1-7  (only completed semesters have marks)
  marks      INTEGER  0-100  pass threshold is 40
  result     TEXT     'Pass' or 'Fail'
""".strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_text_to_sql(question: str):
    """
    End-to-end Text-to-SQL pipeline.

    Returns a QueryResult with source='text-to-sql' and generated_sql set,
    or None if SQL generation fails entirely.
    """
    from query_engine import QueryResult   # deferred to avoid circular import

    sql_raw = _generate_sql(question)
    if sql_raw is None:
        return None

    sql_safe = _validate_sql(sql_raw)
    if sql_safe is None:
        logger.warning("Text-to-SQL: unsafe SQL rejected: %r", sql_raw[:120])
        return QueryResult(
            title="Generated SQL was unsafe",
            summary="The AI produced a query that failed safety validation. Try rephrasing.",
            columns=[],
            rows=[],
            note=f"Rejected SQL: {sql_raw[:200]}",
            source="text-to-sql",
            generated_sql=sql_raw,
        )

    return _execute(question, sql_safe)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_sql(question: str) -> str | None:
    """Call Gemini to generate a SELECT query. Returns raw SQL or None."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.debug("Text-to-SQL: no API key — disabled.")
        return None

    try:
        from google import genai                        # type: ignore[import]
        from google.genai import types as genai_types   # type: ignore[import]
    except ImportError:
        logger.warning("Text-to-SQL: google-genai not installed.")
        return None

    prompt = f"""You are a SQLite expert for a university student database.
Given the schema below, write a single SQLite SELECT query that answers the user's question.

Return ONLY the raw SQL — no explanation, no markdown, no code fences, no comments.

SCHEMA:
{_SCHEMA}

RULES:
- Use SELECT only. Never use INSERT, UPDATE, DELETE, DROP, or any modifying keyword.
- JOIN students to departments via department_id when department name is needed.
- Use LIKE for case-insensitive partial text matches where helpful.
- Use a clear alias for aggregate columns (e.g. COUNT(*) AS student_count).
- Limit results to at most {MAX_ROWS} rows.

QUESTION: "{question}"
SQL:"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=512,
            ),
        )
        raw: str = response.text.strip()
    except Exception as exc:
        logger.warning("Text-to-SQL: Gemini call failed: %s", exc)
        return None

    # Strip markdown code fences (model sometimes adds them despite instructions)
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]).strip()

    return raw or None


def _validate_sql(sql: str) -> str | None:
    """
    Validate and sanitise generated SQL.

    Returns the (possibly modified) SQL string if safe, or None if rejected.
    """
    s = sql.strip()
    if not s:
        return None

    # Must begin with SELECT
    if not s.upper().lstrip().startswith("SELECT"):
        logger.warning("Text-to-SQL: rejected (not SELECT): %r", s[:80])
        return None

    # Blacklist check — word-boundary match to avoid false positives
    upper = s.upper()
    for kw in _BLACKLIST:
        if re.search(rf"\b{kw}\b", upper):
            logger.warning("Text-to-SQL: rejected (blacklisted keyword %r)", kw)
            return None

    # Enforce row cap — append LIMIT if absent
    if "LIMIT" not in upper:
        s = s.rstrip(";").rstrip()
        s = f"{s}\nLIMIT {MAX_ROWS}"

    return s


def _execute(question: str, sql: str):
    """Execute validated SQL and return a QueryResult."""
    from query_engine import QueryResult   # deferred import

    try:
        db_uri = DB_PATH.as_uri() + "?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows    = cursor.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        logger.warning("Text-to-SQL: execution error: %s | SQL: %s", exc, sql)
        return _QueryResult_from_error(str(exc), sql)

    count = len(rows)
    note  = f"Results capped at {MAX_ROWS} rows." if count == MAX_ROWS else None

    return QueryResult(
        title=f"Results for: {question}",
        summary=f"{count} row{'s' if count != 1 else ''} returned.",
        columns=columns,
        rows=[tuple(row) for row in rows],
        note=note,
        source="text-to-sql",
        generated_sql=sql,
    )


def _QueryResult_from_error(message: str, sql: str):
    """Return a QueryResult describing a SQL execution failure."""
    from query_engine import QueryResult
    return QueryResult(
        title="SQL Execution Error",
        summary=f"The generated query could not be executed: {message}",
        columns=[],
        rows=[],
        note="Try rephrasing your question with more specific details.",
        source="text-to-sql",
        generated_sql=sql,
    )
