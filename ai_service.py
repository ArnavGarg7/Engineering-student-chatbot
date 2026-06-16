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
    source: str = field(default="ai", init=False)


class AIServiceError(Exception):
    """Raised internally when intent extraction cannot produce a valid result."""


# Prompt template

def _build_prompt(question: str) -> str:

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
- If the question cannot be mapped to a supported intent, return:
  {{"intent": "unknown"}}

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
Output: {{"intent": "pass_fail_counts", "department": "Electronics & Communication Engineering", "year": 2}}

Now classify this question:
User: "{question}"
Output:"""


# Core extraction function

def extract_intent(question: str) -> IntentResult | None:

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.debug(
            "GEMINI_API_KEY not set — AI intent extraction disabled. "
            "Falling back to rule-based engine."
        )
        return None

    try:
        from google import genai  # type: ignore[import]
        from google.genai import types as genai_types  # type: ignore[import]
    except ImportError:
        logger.warning(
            "google-genai not installed. "
            "Run: pip install google-genai  — falling back to rule-based engine."
        )
        return None

    # 3. Build prompt and call the Gemini API.
    prompt = _build_prompt(question)
    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,        # Deterministic output for classification
                max_output_tokens=256,  # Intent JSON is always short
            ),
        )
    except Exception as exc:

        logger.warning("Gemini API call failed: %s — falling back to rule-based engine.", exc)
        return None

    # 4. Extract text from the response safely.

    try:
        raw_text: str = response.text.strip()
    except (AttributeError, ValueError) as exc:
        logger.warning("Gemini response has no text content: %s", exc)
        return None

    if not raw_text:
        logger.warning("Gemini returned an empty response for question: %r", question)
        return None

    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        # Remove first line (``` or ```json) and last line (```)
        raw_text = "\n".join(lines[1:-1]).strip()

    try:
        data: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Gemini returned invalid JSON for question %r: %s — raw: %r",
            question, exc, raw_text[:200],
        )
        return None

    intent: str = data.get("intent", "")
    if intent == "unknown" or intent not in SUPPORTED_INTENTS:
        logger.info(
            "Gemini returned unsupported intent %r for question %r — "
            "falling back to rule-based engine.",
            intent, question,
        )
        return None

    required_fields = SUPPORTED_INTENTS[intent]
    for required_field in required_fields:
        if data.get(required_field) is None:
            logger.warning(
                "Gemini intent %r is missing required field %r — "
                "falling back to rule-based engine.",
                intent, required_field,
            )
            return None

    year_raw = data.get("year")
    year: int | None = None
    if year_raw is not None:
        try:
            year = int(year_raw)
            if year not in (1, 2, 3, 4):
                logger.warning("Gemini returned out-of-range year %r — ignoring.", year_raw)
                year = None
        except (TypeError, ValueError):
            logger.warning("Gemini returned non-integer year %r — ignoring.", year_raw)

    logger.info(
        "AI intent extracted: intent=%r department=%r year=%r roll_no=%r",
        intent, data.get("department"), year, data.get("roll_no"),
    )

    return IntentResult(
        intent=intent,
        department=data.get("department") or None,
        year=year,
        roll_no=data.get("roll_no") or None,
        subject=data.get("subject") or None,
    )


def is_ai_enabled() -> bool:
    """Return True if a Gemini API key is configured in the environment."""
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())
