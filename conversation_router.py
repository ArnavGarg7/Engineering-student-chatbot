import logging
import string
import re

logger = logging.getLogger("conversation_router")

GREETING_WORDS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "greetings"}
SMALL_TALK_PHRASES = {"how are you", "how are things", "hows your day", "are you doing well"}
THANKS_WORDS = {"thanks", "thank you", "appreciate it", "much appreciated"}
GOODBYE_WORDS = {"bye", "goodbye", "see you", "catch you later"}
IDENTITY_PHRASES = {"who are you", "what are you", "what can you do", "what is your purpose"}
HELP_PHRASES = {"help", "show examples", "how do i use this", "what can i ask"}
OUT_OF_SCOPE_WORDS = {"weather", "bitcoin", "football", "cricket scores", "stock market", "movies"}

def _normalize(text: str) -> str:
    # Remove punctuation, lowercase, and trim
    return text.translate(str.maketrans('', '', string.punctuation)).lower().strip()

def route_conversation(user_message: str, chat_history: str = "", lang_instruction: str = "") -> dict:
    """
    Analyzes the user's message using FAST, LOCAL rules.
    Does NOT depend on Gemini or any external API.
    """
    norm = _normalize(user_message)
    
    # 1. Greeting
    if norm in GREETING_WORDS or any(norm.startswith(g + " ") for g in GREETING_WORDS):
        logger.info("Conversation Router: Category=greeting Method=local_rule")
        return _build_response("greeting", "Hi! 👋 I'm SPEED AI.\n\nI can help you explore students, departments, academic records, performance analytics, and institutional insights through natural language conversations.", lang_instruction)
        
    # 2. Small Talk
    if any(phrase in norm for phrase in SMALL_TALK_PHRASES):
        logger.info("Conversation Router: Category=small_talk Method=local_rule")
        return _build_response("small_talk", "I'm doing great, thanks for asking! I'm ready to help you analyze the engineering database. What would you like to know?", lang_instruction)
        
    # 3. Thanks
    if norm in THANKS_WORDS or any(phrase in norm for phrase in THANKS_WORDS):
        logger.info("Conversation Router: Category=thanks Method=local_rule")
        return _build_response("thanks", "You're very welcome! Let me know if you need any more insights.", lang_instruction)
        
    # 4. Goodbye
    if norm in GOODBYE_WORDS or any(phrase in norm for phrase in GOODBYE_WORDS):
        logger.info("Conversation Router: Category=goodbye Method=local_rule")
        return _build_response("goodbye", "Goodbye! Feel free to return if you need more data.", lang_instruction)
        
    # 5. Identity
    if norm in IDENTITY_PHRASES or any(phrase in norm for phrase in IDENTITY_PHRASES):
        logger.info("Conversation Router: Category=identity Method=local_rule")
        return _build_response("identity", "I am SPEED AI, your Academic Intelligence Assistant. I specialize in answering natural-language questions about our engineering database.", lang_instruction)
        
    # 6. Help
    if norm in HELP_PHRASES or any(phrase in norm for phrase in HELP_PHRASES):
        logger.info("Conversation Router: Category=help Method=local_rule")
        return _build_response("help", "I can help you explore the database. Try asking:\n- 'Show all Computer Science students'\n- 'Which city produces the most toppers?'\n- 'Which semester is hardest?'", lang_instruction)
        
    # 7. Out of Scope
    if any(word in norm for word in OUT_OF_SCOPE_WORDS):
        logger.info("Conversation Router: Category=out_of_scope Method=local_rule")
        return _build_response("out_of_scope", "I am designed specifically for the Engineering Student Database. Please ask me about students, departments, subjects, or academic performance.", lang_instruction)
        
    # 7.5 Short Words Filter
    if len(norm.split()) == 1 and norm in {"how", "what", "why", "when", "who", "show"}:
        logger.info("Conversation Router: Category=clarification Method=local_rule")
        return _build_response("clarification", "Could you please provide more details about what you'd like to know?", lang_instruction)
        
    # 7.6 Confirmation Questions
    import re
    if re.match(r"^(so|then)?\s*(are|is|there|do|does)\s+.*\?$", user_message, re.IGNORECASE):
        logger.info("Conversation Router: Category=confirmation Method=local_rule")
        return {
            "category": "confirmation",
            "response": None,
            "confidence": 1.0
        }

    # 8. Academic Query (Default)
    logger.info("Conversation Router: Category=academic_query Method=default_route")
    return {
        "category": "academic_query",
        "response": None,
        "confidence": 1.0
    }

def _build_response(category: str, english_response: str, lang_instruction: str) -> dict:
    final_response = english_response
    if lang_instruction and "English" not in lang_instruction:
        from llm_provider import manager
        prompt = f"Translate the following text exactly, preserving its meaning and tone.\n\nTEXT: {english_response}\n\n{lang_instruction}"
        translated, _, _, _ = manager.generate_with_retry(prompt, task_type="conversation")
        if translated:
            final_response = translated
            
    return {
        "category": category,
        "response": final_response,
        "confidence": 1.0
    }
