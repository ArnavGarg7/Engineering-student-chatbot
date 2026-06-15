from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, List

from query_engine import route_question

# Logging — enable INFO level so AI layer decisions are visible in the console.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("app_server")

# FastAPI app

app = FastAPI(
    title="Engineering College Query API",
    description=(
        "Natural-language chatbot API for the Engineering Student Database. "
        "Queries are first processed by Google Gemini for intent extraction; "
        "a rule-based engine acts as the guaranteed fallback."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    title: str
    summary: str | None = None
    columns: List[str] | None = None
    rows: List[List[Any]] | None = None
    note: str | None = None
    source: str = "rule-based"       # "ai", "semantic", "text-to-sql", "rule-based"
    generated_sql: str | None = None  # populated by text-to-sql layer, shown in UI


# Endpoints

@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    """
    Accept a natural-language question and return structured query results.

    Processing order:
    1. Gemini AI intent extraction (if GEMINI_API_KEY is configured).
    2. Rule-based keyword matching (always runs as fallback).
    """
    logger.info("Received question: %r", req.question)
    result = route_question(req.question)
    logger.info(
        "Resolved via %s → title=%r  rows=%d",
        result.source, result.title, len(result.rows),
    )
    return QueryResponse(
        title=result.title,
        summary=result.summary,
        columns=result.columns,
        rows=[list(r) for r in result.rows],
        note=result.note,
        source=result.source,
        generated_sql=result.generated_sql,
    )


@app.get("/api/sample_questions")
def sample_questions() -> list[str]:
    """
    Return a curated list of example questions demonstrating both the original
    query patterns and the expanded natural-language / abbreviation support.
    """
    return [
        # Departments
        "List all engineering departments.",
        "What branches are available?",
        # Years
        "List all years available.",
        # Students by department
        "List all students in Computer Science.",
        "Who studies in CSE?",
        "Show students enrolled in IT.",
        # Students by department + year
        "Show all 3rd year Mechanical Engineering students.",
        "Show all 2nd year ECE students.",
        "Show 1st year Aerospace Engineering students.",
        # Pass / fail
        "How many students passed in Computer Science, 2nd year?",
        "How many students failed in Civil Engineering, 3rd year?",
        # Roll number list
        "Show the list of students with roll numbers in Electrical Engineering.",
        # Academic history
        "Show full academic history of roll number 2025-CSE-001.",
        # Subject-wise marks
        "Show subject-wise marks of roll number 2025-CSE-001.",
        # Semester performance
        "Show semester-wise performance of roll number 2025-CSE-001.",
        # Toppers
        "Show toppers in Information Technology.",
        "Who are the top performers in ECE?",
        "Best students in Biotechnology?",
        # Failures
        "Show students who failed in more than 2 subjects.",
        "Show backlog students.",
        # Averages
        "Show average marks by department.",
        "Which department has the best academic performance?",
        "Show average marks by subject.",
    ]


@app.get("/api/health")
def health() -> dict[str, Any]:
    """
    Lightweight health check endpoint.

    Returns
    -------
    status           : "ok" — always present if the server is running.
    ai_enabled       : True if GEMINI_API_KEY is configured.
    semantic_enabled : True if the semantic engine has loaded its embeddings.
    version          : API version string.
    """
    from ai_service import is_ai_enabled
    from semantic_engine import engine as _sem_engine
    return {
        "status": "ok",
        "ai_enabled": is_ai_enabled(),
        "semantic_enabled": _sem_engine.is_ready(),
        "version": "3.0.0",
    }

