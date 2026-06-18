import logging
from google import genai
from google.genai import types
import os

logger = logging.getLogger("confidence_router")

# Configurable Thresholds
INTENT_CONFIDENCE_THRESHOLD = 0.8
VECTOR_CONFIDENCE_THRESHOLD = 0.75
SQL_CONFIDENCE_THRESHOLD = 0.8

def evaluate_confidence(stage: str, confidence: float, query: str = None) -> dict:
    """
    Evaluates confidence from a stage (intent, vector, sql).
    Returns dict:
    {
       "action": "proceed" | "clarify" | "abort",
       "clarification_message": "..." (only if action is clarify or abort),
       "clarification_options": [...]
    }
    """
    threshold = 0.8
    if stage == "intent":
        threshold = INTENT_CONFIDENCE_THRESHOLD
    elif stage == "vector":
        threshold = VECTOR_CONFIDENCE_THRESHOLD
    elif stage == "sql":
        threshold = SQL_CONFIDENCE_THRESHOLD

    logger.info(f"Evaluating {stage} confidence: {confidence} (threshold: {threshold})")

    if confidence >= threshold:
        return {
            "action": "proceed",
            "clarification_message": None,
            "clarification_options": []
        }
    
    if confidence >= (threshold - 0.3): # Medium confidence
        import assistant_personality
        clarification = assistant_personality.get_clarification_message(stage)
        
        return {
            "action": "clarify",
            "clarification_message": clarification["text"],
            "clarification_options": clarification["options"]
        }
    
    # Low confidence
    return {
        "action": "abort", 
        "clarification_message": "I'm having trouble understanding exactly what you're looking for. Could you please rephrase your question?",
        "clarification_options": []
    }

def _generate_clarification(query: str, stage: str) -> str:
    """Generates a polite clarification question using the LLM."""
    if not query:
        return "Could you please clarify your request?"
        
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "Could you please clarify your request?"
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are SPEED AI, an Academic Intelligence Assistant for an Engineering Student Database.
    The user asked: "{query}"
    
    However, the system has medium confidence ({stage} stage) about what exactly they mean.
    Generate a polite, very brief clarifying question.
    Give the user 2-3 bulleted options of what they might mean (e.g. Students, Departments, Subjects, Performance).
    Keep it extremely natural and concise.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.4)
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating clarification: {e}")
        return "I'm not quite sure I understood. Could you clarify if you are asking about students, departments, or subjects?"
