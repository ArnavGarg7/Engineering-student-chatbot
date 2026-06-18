from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

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
    confidence: float = 1.0
    clarification_options: list[str] | None = None
    context_used: dict | None = None

def route_question(question: str, lang_instruction: str = "", active_filters: dict | None = None) -> QueryResult:
    """
    Primary routing function for academic database queries.
    This replaces the old Intent Waterfall.
    
    1. Text-to-SQL is the PRIMARY path for all database queries.
    2. It uses Schema-Aware RAG underneath.
    """
    logger.info("Routing question via Text-to-SQL Architecture: %r", question)
    
    # 1. We no longer extract intents or use semantic engine for predefined intents.
    # We directly route the academic question to the Schema-Aware RAG + Text-to-SQL engine.
    
    from text_to_sql import run_text_to_sql
    result = run_text_to_sql(question, lang_instruction, active_filters)
    
    if result is not None:
        return result
        
    # If Text-to-SQL fails catastrophically (e.g. no Gemini API key), return a fallback error.
    return QueryResult(
        title="Query Processing Error",
        summary="SPEED AI was unable to generate a SQL query to answer this question.",
        columns=[],
        rows=[],
        source="system"
    )
