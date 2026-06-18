from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path

import database_introspection

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

FALLBACK_RULES = """
Marks < 40 = Fail.
Current semester has NO marks.
"""

def verify_sql_matches_entities(test_sql: str, context_filters: dict, user_query: str) -> bool:
    """Verifies that the generated SQL does not hallucinate filters."""
    from llm_provider import manager
    if not manager.providers:
        return True
    prompt = f"""You are a strict SQL Verification guardrail.
The user asked: "{user_query}"
Active conversation filters: {json.dumps(context_filters, ensure_ascii=False) if context_filters else "{}"}
Generated SQL: {test_sql}

TASK:
1. Extract requested entities (department, city, year, semester) from the user query and active filters.
2. Check if the Generated SQL introduces ANY of these filters (department, city, year, semester) in its WHERE or JOIN clauses that were NOT requested.
3. If the SQL is safe and ONLY uses requested filters, respond with YES (PASS). If it hallucinates unrequested filters, respond with NO (FAIL).

Respond ONLY with YES or NO."""
    ans, _, _, _ = manager.generate_with_retry(prompt, task_type="conversation")
    logger.info("Requested Entities Check: User Query='%s', Active Filters=%s", user_query, context_filters)
    logger.info("Verification Result: %s for SQL: %s", ans, test_sql)
    if ans and "NO" in ans.upper():
        logger.warning("Verification Failed. Hallucination detected.")
        return False
    logger.info("Verification Passed.")
    return True

def run_text_to_sql(question: str, lang_instruction: str = "", active_filters: dict | None = None) -> Any:
    from query_engine import QueryResult   # deferred to avoid circular import
    from vector_store import store
    
    start_time = time.time()
    
    try:
        # 1. RAG Retrieval with Fallback to Full Schema
        schema_chunks, schema_ids = store.retrieve_schema(question, top_k=3)
        if not schema_chunks:
            logger.warning("RAG Retrieval Failed → Using Full Schema Fallback")
            full_schema_text = database_introspection.get_full_schema()
            retrieved_schema_count = len(full_schema_text.split("CREATE TABLE")) - 1
        else:
            full_schema_text = "\n\n".join(schema_chunks)
            retrieved_schema_count = len(schema_chunks)
            logger.info("Retrieved %d schema chunks via RAG.", retrieved_schema_count)
            logger.info("Retrieved Schema IDs: %s", schema_ids)
            
        rules_chunks, rules_ids = store.retrieve_business_rules(question, top_k=2)
        sql_examples_chunks, sql_ids = store.retrieve_sql_examples(question, top_k=4)
        
        logger.info("Retrieved Rule IDs: %s", rules_ids)
        
        rules_context = "\n\n".join(rules_chunks) if rules_chunks else FALLBACK_RULES
        examples_context = "\n\n".join(sql_examples_chunks) if sql_examples_chunks else ""
    
        # 2. Initial SQL Generation
        sql_raw, provider, lat, depth = _generate_sql(question, full_schema_text, rules_context, examples_context, lang_instruction, active_filters)
        
        if provider is None:
            return _QueryResult_from_error("⚠ All AI providers are temporarily unavailable.", None)
            
        if not sql_raw:
            return _QueryResult_from_error("Could not generate SQL query.", None)
        logger.info("Generated SQL: %s", sql_raw)
    
        # 3. SQL Validation (Blacklist + LIMIT)
        sql_safe = _validate_sql(sql_raw)
        if not sql_safe:
            logger.warning("Text-to-SQL: unsafe SQL rejected: %r", sql_raw[:120])
            return _QueryResult_from_error("Generated SQL was unsafe.", sql_raw)
    
        # 4. Self-Correction Loop (Up to 2 Attempts)
        max_attempts = 2
        attempt = 0
        execution_success = False
        rows = []
        columns = []
        
        while attempt <= max_attempts and not execution_success:
            if attempt > 0:
                logger.warning("Text-to-SQL: Attempting self-correction %d/%d...", attempt, max_attempts)
                
            explain_error = _explain_query(sql_safe)
            
            if explain_error:
                logger.warning("Text-to-SQL: Validation failed: %s", explain_error)
                if attempt < max_attempts:
                    sql_raw, provider, lat, depth = _repair_sql(question, full_schema_text, rules_context, sql_safe, explain_error, lang_instruction, active_filters)
                    if provider is None:
                        return _QueryResult_from_error("⚠ All AI providers are temporarily unavailable during repair.", sql_safe)
                    if not sql_raw:
                        return _QueryResult_from_error("SQL repair failed to generate query.", sql_safe)
                    logger.info("Corrected SQL: %s", sql_raw)
                    sql_safe = _validate_sql(sql_raw)
                    if not sql_safe:
                        return _QueryResult_from_error("Repaired SQL was unsafe.", sql_raw)
                    attempt += 1
                    continue
                else:
                    return _QueryResult_from_error(f"Failed after {max_attempts} repairs: {explain_error}", sql_safe)
            
            # --- SQL Verification Layer ---
            if sql_safe and not verify_sql_matches_entities(sql_safe, active_filters, question):
                if attempt >= max_attempts:
                    return _QueryResult_from_error(f"Failed to fix hallucinated filters after {max_attempts} repairs.", sql_safe)
                    
                err_msg = "The SQL hallucinated constraints not present in the user query or active context."
                sql_raw, provider, lat, depth = _repair_sql(
                    question, full_schema_text, rules_context, sql_safe, err_msg, lang_instruction, active_filters
                )
                sql_safe = _validate_sql(sql_raw) if sql_raw else None
                if not sql_safe:
                    return _QueryResult_from_error("Repaired SQL was invalid or unsafe.", sql_safe)
                attempt += 1
                continue

            # Execute
            try:
                db_uri = DB_PATH.as_uri() + "?mode=ro"
                conn = sqlite3.connect(db_uri, uri=True)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql_safe)
                columns = [d[0] for d in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                conn.close()
                execution_success = True
            except sqlite3.Error as exc:
                logger.warning("Text-to-SQL: execution error: %s | SQL: %s", exc, sql_safe)
                if attempt < max_attempts:
                    sql_raw, provider, lat, depth = _repair_sql(question, full_schema_text, rules_context, sql_safe, str(exc), lang_instruction)
                    if provider is None:
                        return _QueryResult_from_error("⚠ All AI providers are temporarily unavailable during repair.", sql_safe)
                    if not sql_raw:
                        return _QueryResult_from_error("SQL repair failed.", sql_safe)
                    logger.info("Corrected SQL: %s", sql_raw)
                    sql_safe = _validate_sql(sql_raw)
                    if not sql_safe:
                        return _QueryResult_from_error("Repaired SQL was unsafe.", sql_raw)
                    attempt += 1
                    continue
                else:
                    return _QueryResult_from_error(f"Execution failed after {max_attempts} repairs: {exc}", sql_safe)
    
        exec_time_ms = int((time.time() - start_time) * 1000)
        count = len(rows)
        logger.info("Execution Time: %d ms | Rows Returned: %d", exec_time_ms, count)
        
        note  = f"Results capped at {MAX_ROWS} rows." if count == MAX_ROWS else None
    
        rag_context_dict = {
            "Execution Time (ms)": f"{exec_time_ms} ms",
            "Provider Used": provider,
            "Fallback Depth": depth,
            "Latency": f"{lat:.2f}s",
            "Retrieved Schema Count": retrieved_schema_count,
            "Retrieved Rule Count": len(rules_chunks) if rules_chunks else 0,
            "Retrieved Schema IDs": ", ".join(schema_ids) if schema_ids else "N/A",
            "Retrieved Rule IDs": ", ".join(rules_ids) if rules_ids else "N/A"
        }
    
        return QueryResult(
            title=f"Results for: {question}",
            summary=f"{count} row{'s' if count != 1 else ''} returned.",
            columns=columns,
            rows=[tuple(row) for row in rows],
            note=note,
            source="text-to-sql",
            generated_sql=sql_safe,
            context_used=rag_context_dict
        )
    except Exception as exc:
        logger.error("Text-to-SQL: Catastrophic failure in pipeline: %s", exc)
        from query_engine import QueryResult
        return QueryResult(
            title="System Error",
            summary="SPEED AI encountered an internal error while processing the database query.",
            columns=[],
            rows=[],
            note="Try rephrasing your question or check system logs.",
            source="system"
        )

def _generate_sql(question: str, schema: str, rules: str, examples: str, lang_instruction: str = "", active_filters: dict | None = None) -> tuple[str | None, str | None, float, int]:
    """Call LLM to generate a SELECT query based on RAG context."""
    from llm_provider import manager
    import json
    
    prompt = f"""You are an elite SQLite expert for a university database.
Write a single, highly accurate SQLite SELECT query to answer the user's question.

CRITICAL INSTRUCTIONS:
1. USE ONLY COLUMNS AND TABLES PRESENT IN THE PROVIDED SCHEMA. DO NOT INVENT COLUMNS!
2. Do not invent aliases without declaring them in the FROM or JOIN clause.
3. Return ONLY valid SQLite SQL. No markdown formatting, no comments, no explanations.
4. Use SELECT only. Never use modifying keywords.
5. Use LIKE for case-insensitive matches.
6. Limit results to at most {MAX_ROWS} rows.
7. CRITICAL: EXAMPLES are for SQL structure ONLY. NEVER copy literal filter values (like "Computer Science", "Delhi", etc.) from EXAMPLES. You MUST ONLY use filter values if they appear in the user's QUESTION or the ACTIVE FILTERS CONTEXT.

DATABASE SCHEMA:
{schema}

BUSINESS RULES:
{rules}

EXAMPLES:
{examples}

QUESTION: "{question}"

ACTIVE FILTERS CONTEXT (MUST APPLY THESE CONDITIONS IF PRESENT):
{json.dumps(active_filters, ensure_ascii=False) if active_filters else "{}"}

{lang_instruction}

SQL:"""

    raw, provider, lat, depth = manager.generate_with_retry(prompt, task_type="text_to_sql")
    return raw or None, provider, lat, depth

def _repair_sql(question: str, schema: str, rules: str, bad_sql: str, error_msg: str, lang_instruction: str = "", active_filters: dict | None = None) -> tuple[str | None, str | None, float, int]:
    """Call LLM to repair a failed SQL query."""
    from llm_provider import manager

    prompt = f"""You are an elite SQLite expert. Your previous SQL query failed. Fix it.

CRITICAL INSTRUCTIONS:
1. Review the ERROR MESSAGE and the BAD SQL carefully.
2. USE ONLY COLUMNS AND TABLES PRESENT IN THE SCHEMA. DO NOT INVENT COLUMNS.
3. Ensure every alias used is explicitly defined in a FROM or JOIN clause.
4. Return ONLY the corrected raw SQLite SELECT query. No markdown formatting, no comments.

DATABASE SCHEMA:
{schema}

BUSINESS RULES:
{rules}

QUESTION: "{question}"

BAD SQL:
{bad_sql}

ERROR MESSAGE:
{error_msg}

ACTIVE FILTERS CONTEXT:
{json.dumps(active_filters, ensure_ascii=False) if active_filters else "{}"}

{lang_instruction}

SQL:"""

    raw, provider, lat, depth = manager.generate_with_retry(prompt, task_type="text_to_sql")
    return raw or None, provider, lat, depth

def _validate_sql(sql: str) -> str | None:
    s = sql.strip()
    if not s: return None
    if not s.upper().lstrip().startswith("SELECT"): return None

    upper = s.upper()
    for kw in _BLACKLIST:
        if re.search(rf"\b{kw}\b", upper): return None

    if "LIMIT" not in upper:
        s = s.rstrip(";").rstrip()
        s = f"{s}\nLIMIT {MAX_ROWS}"

    return s

def _explain_query(sql: str) -> str | None:
    """Run EXPLAIN QUERY PLAN to validate SQLite parsing. Returns error message if failed, else None."""
    try:
        db_uri = DB_PATH.as_uri() + "?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        conn.execute("EXPLAIN QUERY PLAN " + sql)
        conn.close()
        return None
    except sqlite3.Error as exc:
        return str(exc)

def _QueryResult_from_error(message: str, sql: str | None):
    from query_engine import QueryResult
    return QueryResult(
        title="SQL Execution Error",
        summary=f"The query could not be executed: {message}",
        columns=[], rows=[],
        note="Try rephrasing your question.",
        source="text-to-sql",
        generated_sql=sql,
    )
