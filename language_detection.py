import re
import logging
from langdetect import detect_langs, DetectorFactory

# Deterministic detection
DetectorFactory.seed = 0

logger = logging.getLogger("language_detection")

# Unicode ranges for explicit detection
SCRIPT_PATTERNS = {
    "Hindi": re.compile(r'[\u0900-\u097F]'),
    "Urdu": re.compile(r'[\u0600-\u06FF]'),
    "Spanish": re.compile(r'[¿¡]'),
    "German": re.compile(r'[äöüßÄÖÜ]'),
    "French": re.compile(r'[éàèçÉÀÈÇ]')
}

LANGUAGE_MAP = {
    'en': 'English',
    'hi': 'Hindi',
    'es': 'Spanish',
    'de': 'German',
    'fr': 'French',
    'ur': 'Urdu'
}

def detect_language(text: str) -> dict:
    """
    Returns {"language": str, "confidence": float}
    """
    if not text:
        return {"language": "English", "confidence": 1.0}

    # 1. Explicit script/character detection
    for lang, pattern in SCRIPT_PATTERNS.items():
        if pattern.search(text):
            logger.info("Language Detection: Language=%s Confidence=1.0 Method=ExplicitScript", lang)
            return {"language": lang, "confidence": 1.0}

    # 2. Short query protection
    word_count = len(text.strip().split())
    if word_count < 5:
        logger.info("Language Detection: Language=English Confidence=1.0 Method=ShortQueryFallback")
        return {"language": "English", "confidence": 1.0}

    # 3. Hybrid langdetect strategy
    try:
        langs = detect_langs(text)
        if langs:
            top_lang = langs[0]
            mapped_lang = LANGUAGE_MAP.get(top_lang.lang, "English")
            
            if top_lang.prob < 0.90:
                logger.info("Language Detection: Language=English Confidence=%f Method=LowConfidenceFallback (Original: %s)", top_lang.prob, mapped_lang)
                return {"language": "English", "confidence": top_lang.prob}
                
            logger.info("Language Detection: Language=%s Confidence=%f Method=LangDetect", mapped_lang, top_lang.prob)
            return {"language": mapped_lang, "confidence": top_lang.prob}
    except Exception as e:
        logger.warning("Language detection failed: %s. Defaulting to English.", e)

    return {"language": "English", "confidence": 1.0}

def get_language_instruction(target_language: str) -> str:
    """Returns a strict instruction to enforce the target language."""
    if not target_language or target_language.lower() == "english":
        return "Respond ONLY in English. Never switch languages."
        
    return (
        f"Respond ONLY in: {target_language}\n"
        f"Never switch languages.\n"
        f"Never translate unless asked."
    )
