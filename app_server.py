from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, List

from query_engine import route_question
from memory_manager import create_session, add_message, get_context_for_llm, summarize_conversation_if_needed
from ai_service import generate_conversational_response
from conversation_router import route_conversation
import sys
import os
import sqlite3
from pathlib import Path

# Logging — enable INFO level so AI layer decisions are visible in the console.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("app_server")

# Environment Diagnostics
logger.info("="*50)
logger.info("STARTING SPEED AI - SYSTEM DIAGNOSTICS")
logger.info("Python Executable: %s", sys.executable)
logger.info("Python Version: %s", sys.version.replace('\n', ' '))
logger.info("="*50)

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

@app.on_event("startup")
def startup_event():
    """Run critical startup self-tests."""
    logger.info("Running startup self-tests...")
    
    # 0. Core Module Import Check
    try:
        import text_to_sql
        import vector_store
        import query_engine
        import database_introspection
        logger.info("✓ Core modules compiled and imported successfully.")
    except Exception as e:
        logger.error("✗ CRITICAL STARTUP FAILURE: Core module import failed. Check for syntax errors: %s", e)
        sys.exit(1)
        
    # 1. SQLite Check
    db_path = Path("engineering_college.db")
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1 FROM students LIMIT 1")
            conn.close()
            logger.info("✓ SQLite database is accessible.")
        except Exception as e:
            logger.error("✗ SQLite database exists but cannot be read: %s", e)
        # Cache full schema into memory
        schema_text = database_introspection.get_full_schema()
        logger.info("✓ Database schema introspected and cached in memory.")
    else:
        logger.error("✗ SQLite database file not found at %s", db_path.absolute())
        
    # 2. LLM Providers Check
    try:
        from llm_provider import manager
        from provider_health import health_monitor
        if manager.providers:
            logger.info("✓ %d LLM providers initialized: %s", len(manager.providers), list(manager.providers.keys()))
            
            # Pre-flight Validation
            for p_name in list(manager.providers.keys()):
                logger.info("  Testing provider: %s...", p_name)
                is_working = manager.test_provider(p_name)
                if is_working:
                    logger.info("    ✓ %s is healthy.", p_name)
                else:
                    logger.error("    ✗ %s failed validation. Marking as degraded.", p_name)
                    health_monitor.mark_degraded(p_name)
                    
            logger.info("  - Active Text-to-SQL: %s", manager.active_sql)
            logger.info("  - Active Conversation: %s", manager.active_conv)
            logger.info("  - Fallback Chain: %s", manager.fallbacks)
        else:
            logger.error("✗ No LLM providers initialized. Check API keys.")
    except Exception as e:
        logger.error("✗ LLM Provider initialization failed: %s", e)
        
    # 3. ChromaDB Check
    try:
        import chromadb
        logger.info("✓ ChromaDB module loaded from: %s", chromadb.__file__)
        from vector_store import store
        store.initialize()
        if store.ready:
            logger.info("✓ ChromaDB initialized.")
            
            # Count collections
            if store.rules_coll:
                logger.info("  - Business Rules: %d docs", store.rules_coll.count())
            if store.sql_coll:
                logger.info("  - SQL Examples: %d docs", store.sql_coll.count())
        else:
            logger.error("✗ ChromaDB failed to initialize. Check logs.")
    except ImportError as e:
        logger.error("✗ ChromaDB module could not be imported. Is it installed in this environment? Error: %s", e)
    except Exception as e:
        logger.error("✗ ChromaDB startup test failed: %s", e)
        
    # Start Health Monitor Recovery Thread
    from provider_health import health_monitor
    health_monitor.start_recovery_thread()
    logger.info("✓ Provider health monitor recovery thread started.")
    
    logger.info("Startup self-tests complete.")
    logger.info("="*50)


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

class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str

class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    text: str
    data: QueryResponse | None = None
    source: str | None = None
    confidence: float | None = None
    context_used: dict | None = None
    clarification_options: List[str] | None = None
    active_filters: dict | None = None


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

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    Stateful chat endpoint.
    """
    session_id = req.session_id or create_session()
    
    # Save user message
    add_message(session_id, "user", req.message)
    
    # 1. Detect Language
    from language_detection import detect_language, get_language_instruction
    
    detection_result = detect_language(req.message)
    detected_lang = detection_result["language"]
    lang_instruction = get_language_instruction(detected_lang)
    
    # 2. Context Persistence (Active Filters & Classification)
    # The resolver now handles standalone classification and entity canonicalization
    from context_resolver import resolve_active_filters
    active_filters = resolve_active_filters(session_id, req.message)
    
    # Translate the query to English if it's in another language so the LLM Text-to-SQL logic doesn't hallucinate
    from query_normalizer import translate_to_english, normalize_entities
    translated_msg = translate_to_english(req.message, detected_lang)
    
    # Normalize the translated query string so the text-to-sql model receives canonical English entities
    normalized_msg = normalize_entities(translated_msg)
    
    # Get conversational context
    context = get_context_for_llm(session_id)
    
    # Process via Conversation Router First
    logger.info("Chat API: Processing message %r (Lang: %s) for session %s", req.message, detected_lang, session_id)
    routing = route_conversation(normalized_msg, context, lang_instruction)
    
    if routing.get("category") != "academic_query":
        # Non-academic query (greeting, out of scope, etc.)
        if routing.get("category") == "confirmation":
            ai_text = generate_conversational_response(req.message, context, None, lang_instruction)
        else:
            ai_text = routing.get("response") or "I am an AI assistant for the Engineering Student Database."
            
        msg_id = add_message(session_id, "assistant", ai_text)
        summarize_conversation_if_needed(session_id)
        
        return ChatResponse(
            session_id=session_id,
            message_id=msg_id,
            text=ai_text,
            data=None,
            source="conversational",
            confidence=routing.get("confidence", 1.0),
            active_filters=active_filters
        )

    # Proceed to academic database query
    result = route_question(normalized_msg, lang_instruction=lang_instruction, active_filters=active_filters)
    
    # If Text-to-SQL returned our custom fail-safe message, intercept it here.
    if result.title == "System Error" and "All AI providers are temporarily unavailable" in result.summary:
        msg_id = add_message(session_id, "assistant", result.summary)
        return ChatResponse(
            session_id=session_id,
            message_id=msg_id,
            text=result.summary, # Direct display string
            data=None,
            source="system_error",
            confidence=1.0,
            active_filters=active_filters
        )
    
    # Format query response
    query_resp = QueryResponse(
        title=result.title,
        summary=result.summary,
        columns=result.columns,
        rows=[list(r) for r in result.rows] if result.rows else [],
        note=result.note,
        source=result.source,
        generated_sql=result.generated_sql,
    )
    
    # Generate natural language response using LLM
    ai_text = generate_conversational_response(req.message, context, query_resp.model_dump(), lang_instruction)
    
    # Save assistant message
    msg_id = add_message(session_id, "assistant", ai_text, structured_data=query_resp.model_dump())
    
    # Summarize if needed
    summarize_conversation_if_needed(session_id)
    
    return ChatResponse(
        session_id=session_id,
        message_id=msg_id,
        text=ai_text,
        data=query_resp,
        source=getattr(result, "source", "rule-based"),
        confidence=getattr(result, "confidence", 1.0),
        context_used=getattr(result, "context_used", None),
        clarification_options=getattr(result, "clarification_options", []),
        active_filters=active_filters
    )


@app.get("/api/sessions")
def get_sessions():
    from memory_manager import get_all_sessions
    return get_all_sessions()

@app.get("/api/chat/{session_id}/history")
def get_chat_history(session_id: str):
    from memory_manager import get_session_messages, get_active_filters
    messages = get_session_messages(session_id)
    active_filters = get_active_filters(session_id)
    return {
        "messages": messages,
        "active_filters": active_filters
    }

class RemoveFilterRequest(BaseModel):
    session_id: str
    filter_key: str

@app.post("/api/chat/remove_filter")
def remove_filter(req: RemoveFilterRequest):
    from context_resolver import remove_active_filter
    remove_active_filter(req.session_id, req.filter_key)
    return {"status": "success"}

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
    Detailed health check endpoint.
    """
    from vector_store import store
    from provider_health import health_monitor
    
    db_path = Path("engineering_college.db")
    db_status = "ok" if db_path.exists() else "missing"
    
    # Try to import chromadb to test availability
    chroma_status = "unavailable"
    try:
        import chromadb
        chroma_status = "ok" if store.ready else "initialization_failed"
    except ImportError:
        pass
        
    return {
        "server": "ok",
        "database": db_status,
        "chromadb": chroma_status,
        "llm_providers": health_monitor.get_health_report(),
        "version": "4.1.0",
    }

