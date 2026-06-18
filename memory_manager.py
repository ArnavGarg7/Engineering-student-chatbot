import sqlite3
import uuid
import json
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "engineering_college.db"

logger = logging.getLogger("memory_manager")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_session() -> str:
    session_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute("INSERT INTO chat_sessions (session_id) VALUES (?)", (session_id,))
    return session_id

def get_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

def add_message(session_id: str, role: str, content: str, structured_data: dict | None = None) -> str:
    message_id = str(uuid.uuid4())
    struct_str = json.dumps(structured_data) if structured_data else None
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (message_id, session_id, role, content, structured_data) VALUES (?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, struct_str)
        )
    return message_id

def get_recent_context(session_id: str, limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        
        messages = []
        for row in rows:
            msg = dict(row)
            if msg["structured_data"]:
                msg["structured_data"] = json.loads(msg["structured_data"])
            messages.append(msg)
        return messages

def get_session_messages(session_id: str) -> list[dict]:
    """Retrieves all messages for a specific session."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        ).fetchall()
        
        messages = []
        for row in rows:
            msg = dict(row)
            if msg["structured_data"]:
                msg["structured_data"] = json.loads(msg["structured_data"])
            messages.append(msg)
        return messages

def get_all_sessions(limit: int = 20) -> list[dict]:
    """Retrieves recent sessions ordered by creation date."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_sessions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

def update_session_summary(session_id: str, summary: str):
    with get_connection() as conn:
        conn.execute("UPDATE chat_sessions SET conversation_summary = ? WHERE session_id = ?", (summary, session_id))

def update_active_filters(session_id: str, filters: dict):
    with get_connection() as conn:
        filters_str = json.dumps(filters) if filters else None
        conn.execute("UPDATE chat_sessions SET active_filters = ? WHERE session_id = ?", (filters_str, session_id))

def get_active_filters(session_id: str) -> dict:
    session = get_session(session_id)
    if session and session.get("active_filters"):
        try:
            return json.loads(session["active_filters"])
        except json.JSONDecodeError:
            pass
    return {}

def summarize_conversation_if_needed(session_id: str):
    """
    Called periodically to summarize long conversations.
    If the session has > 10 messages, use Gemini to create a summary,
    save it to `conversation_summary`, and (optionally) prune old messages.
    For simplicity, we just maintain the rolling summary.
    """
    messages = get_recent_context(session_id, limit=100)
    if len(messages) <= 10:
        return
    
    # Needs a summary update
    try:
        from llm_provider import manager
        
        conversation_text = ""
        for m in messages:
            conversation_text += f"{m['role'].upper()}: {m['content']}\n"
        
        prompt = f"Summarize this conversation context briefly, highlighting the user's intent, current topic, and any constraints (like department, year, roll number). Keep it under 3 sentences.\n\nConversation:\n{conversation_text}"
        
        response, _, _, _ = manager.generate_with_retry(prompt, task_type="conversation")
        if response:
            update_session_summary(session_id, response.strip())
            logger.info("Updated conversation summary for session %s", session_id)
            
    except Exception as e:
        logger.warning("Failed to summarize conversation: %s", e)

def get_context_for_llm(session_id: str) -> str:
    """
    Returns a string representation of the conversation memory,
    including the summary (if it exists) and the recent messages.
    """
    session = get_session(session_id)
    if not session:
        return ""
    
    context_str = ""
    if session.get("conversation_summary"):
        context_str += f"PREVIOUS CONVERSATION SUMMARY:\n{session['conversation_summary']}\n\n"
    
    recent_msgs = get_recent_context(session_id, limit=6)
    if recent_msgs:
        context_str += "RECENT MESSAGES:\n"
        for msg in recent_msgs:
            # We don't need to pass all the structured data JSON to the LLM context, just the text.
            context_str += f"[{msg['role'].upper()}]: {msg['content']}\n"
            
    return context_str
