from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be set system-wide instead

logger = logging.getLogger("ai_service")

SUPPORTED_INTENTS: dict[str, list[str]] = {
    "list_departments":             [],
    "list_years":                   [],
    "students_by_department":       ["department"],
    "students_by_department_year":  ["department", "year"],
    "students_with_roll_numbers":   ["department"],
    "academic_history":             ["roll_no"],
    "subject_wise_marks":           ["roll_no"],
    "semester_performance":         ["roll_no"],
    "pass_fail_counts":             ["department", "year"],
    "department_toppers":           ["department"],
    "failed_more_than_two":         [],
    "average_marks_by_department":  [],
    "average_marks_by_subject":     [],
}


@dataclass
class IntentResult:
    """
    Structured output from the Gemini intent extraction step.

    Fields
    ------
    intent      : One of the keys in SUPPORTED_INTENTS.
    department  : Canonical department name (e.g. "Computer Science").
    year        : Academic year 1–4 as an integer.
    roll_no     : Student roll number (e.g. "2025-CSE-001").
    subject     : Subject name, reserved for future intent types.
    source      : Always "ai" — used by the caller to tag responses.
    """
    intent: str
    department: str | None = None
    year: int | None = None
    roll_no: str | None = None
    subject: str | None = None
    confidence: float = 1.0
    source: str = field(default="ai", init=False)


class AIServiceError(Exception):
    """Raised internally when intent extraction cannot produce a valid result."""


# Prompt template

def _build_prompt(question: str, context: str = "") -> str:

    intent_descriptions = "\n".join(
        f"  {intent}: requires fields {fields if fields else '(none)'}"
        for intent, fields in SUPPORTED_INTENTS.items()
    )

    canonical_departments = (
        "Computer Science, Mechanical Engineering, Civil Engineering, "
        "Electrical Engineering, Electronics & Communication Engineering, "
        "Chemical Engineering, Biotechnology, Information Technology, "
        "Automobile Engineering, Aerospace Engineering"
    )

    return f"""You are an intent classifier for a university student database chatbot.

Your task is to read the user's question and return a JSON object that maps it
to one of the supported intents listed below.  Return ONLY the JSON object —
no markdown, no code fences, no explanations.

SUPPORTED INTENTS (and the entity fields each one requires):
{intent_descriptions}

CANONICAL DEPARTMENT NAMES (resolve any abbreviation or informal name to one of these):
{canonical_departments}

RULES:
- "intent" must be exactly one of the supported intent strings above.
- Include only entity fields that are clearly present in the question.
- "year" must be an integer 1, 2, 3, or 4.
- "roll_no" format: YYYY-DEPT-NNN  (e.g. 2025-CSE-001).
- Include a "confidence" field (float 0.0 to 1.0) indicating how certain you are of this intent.
- If the question cannot be mapped to a supported intent, return:
  {{"intent": "unknown", "confidence": 0.0}}

EXAMPLES:
User: "Which department has the best academic performance?"
Output: {{"intent": "average_marks_by_department"}}

User: "Show me all third year mechanical students"
Output: {{"intent": "students_by_department_year", "department": "Mechanical Engineering", "year": 3}}

User: "Who are the top performers in CSE?"
Output: {{"intent": "department_toppers", "department": "Computer Science"}}

User: "What is the transcript of 2025-CSE-001?"
Output: {{"intent": "academic_history", "roll_no": "2025-CSE-001"}}

User: "How many ECE second year students passed?"
Output: {{"intent": "pass_fail_counts", "department": "Electronics & Communication Engineering", "year": 2, "confidence": 0.95}}

CONTEXT FROM PREVIOUS CONVERSATION (including Summaries and Recent Messages):
{context}

Now classify this latest question.
CRITICAL CONTEXT INHERITANCE RULES:
1. If the user specifies "Only 3rd year" without a department, but the previous context was discussing "Computer Science", you MUST output both "department": "Computer Science" and "year": 3.
2. Maintain constraints like department, year, or roll_no from the context unless the user's current question explicitly changes them.
3. If the user asks a completely new question, drop the old constraints.

User: "{question}"
Output:"""


# Core extraction function

def extract_intent(question: str, context: str = "") -> IntentResult | None:
    from llm_provider import manager

    if not manager.providers:
        logger.debug("No LLM providers available — falling back to rule-based engine.")
        return None

    # 3. Build prompt and call the ProviderManager
    prompt = _build_prompt(question, context)
    
    raw_text, provider, lat, depth = manager.generate_with_retry(prompt, task_type="conversation")
    if not raw_text:
        return None

    try:
        data: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Provider %s returned invalid JSON for question %r: %s — raw: %r",
            provider, question, exc, raw_text[:200],
        )
        return None

    intent: str = data.get("intent", "")
    if intent == "unknown" or intent not in SUPPORTED_INTENTS:
        logger.info(
            "Provider %s returned unsupported intent %r for question %r — falling back to rule-based engine.",
            provider, intent, question,
        )
        return None

    required_fields = SUPPORTED_INTENTS[intent]
    for required_field in required_fields:
        if data.get(required_field) is None:
            logger.warning(
                "Intent %r missing required field %r — falling back to rule-based engine.",
                intent, required_field,
            )
            return None

    year_raw = data.get("year")
    year: int | None = None
    if year_raw is not None:
        try:
            year = int(year_raw)
            if year not in (1, 2, 3, 4):
                logger.warning("Returned out-of-range year %r — ignoring.", year_raw)
                year = None
        except (TypeError, ValueError):
            logger.warning("Returned non-integer year %r — ignoring.", year_raw)

    logger.info(
        "AI intent extracted: intent=%r department=%r year=%r roll_no=%r confidence=%r",
        intent, data.get("department"), year, data.get("roll_no"), data.get("confidence")
    )

    return IntentResult(
        intent=intent,
        department=data.get("department") or None,
        year=year,
        roll_no=data.get("roll_no") or None,
        subject=data.get("subject") or None,
        confidence=float(data.get("confidence", 1.0)),
    )

def is_ai_enabled() -> bool:
    """Return True if any LLM provider is configured."""
    from llm_provider import manager
    return len(manager.providers) > 0

def generate_conversational_response(question: str, context: str, structured_data: dict | list, lang_instruction: str = "") -> str:
    """Generates a natural language response based on the query, context, and data returned from the DB."""
    from llm_provider import manager
    
    if not manager.providers:
        return "Here is the data you requested."
        
    try:
        import assistant_personality
        
        # Clean up structured_data to prevent Demo Mode metadata leaking into natural language
        clean_data = {}
        if isinstance(structured_data, dict):
            clean_data = {k: v for k, v in structured_data.items() if k not in ["context_used", "generated_sql", "source", "confidence"]}
        else:
            clean_data = structured_data
            
        # We need to cap the size of structured_data to avoid huge payloads
        data_str = str(clean_data)
        if len(data_str) > 3000:
            data_str = data_str[:3000] + "... (truncated)"
            
        system_persona = assistant_personality.get_system_prompt_addition()
            
        prompt = f"""{system_persona}
The user asked a database question: "{question}"
We executed a SQL query and got the following data back:
{data_str}

CRITICAL INSTRUCTIONS:
1. Write a concise, professional response summarizing the data (e.g. "There are 4 students from Delhi." or "The average age is 20.").
2. EVIDENCE-BASED ANSWERING: You MUST ONLY describe what is supported by the DATABASE RESULTS. Do not speculate or hallucinate.
3. If the results are empty, state clearly that no matching records were found.
4. DO NOT use filler phrases like "It looks like", "We found some data", or "Based on the data". Just state the facts directly.
5. NEVER leak internal details. NEVER say "Using current context", "Generated SQL", or mention metadata.
6. Do NOT output raw JSON or markdown tables unless explicitly asked.
{lang_instruction}

CONVERSATION CONTEXT:
{context}

USER'S LATEST QUESTION:
{question}

DATABASE RESULTS:
{data_str}

CONVERSATIONAL RESPONSE:"""

        raw, provider, lat, depth = manager.generate_with_retry(prompt, task_type="conversation")
        if not raw:
            return "Here is the data."
        return raw.strip()
    except Exception as exc:
        logger.warning("Conversational response generation failed: %s", exc)
        return "Here is the data."
