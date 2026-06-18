import logging
from langdetect import detect, DetectorFactory

# Set seed for deterministic language detection
DetectorFactory.seed = 0

logger = logging.getLogger("language_utils")

LANGUAGE_MAP = {
    'en': 'English',
    'hi': 'Hindi',
    'es': 'Spanish',
    'de': 'German',
    'fr': 'French',
    'ur': 'Urdu'
}

def detect_language(text: str) -> str:
    """Detects the language of the provided text and returns its English name."""
    try:
        if not text or len(text.strip()) < 3:
            return "English"
        lang_code = detect(text)
        return LANGUAGE_MAP.get(lang_code, "English")
    except Exception as e:
        logger.warning(f"Language detection failed: {e}. Defaulting to English.")
        return "English"

def get_language_instruction(target_language: str) -> str:
    """Returns a strict instruction to enforce the target language."""
    if not target_language or target_language.lower() == "english":
        return "Respond ONLY in English. Do not switch languages."
        
    return (
        f"LANGUAGE POLICY:\n"
        f"You MUST respond ONLY in {target_language}.\n"
        f"Never switch languages. Never mix languages.\n"
        f"Never translate unless explicitly requested."
    )
