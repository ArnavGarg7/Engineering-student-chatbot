import logging
import re

logger = logging.getLogger("query_normalizer")

# Canonical mappings for multilinugal entity normalization
ENTITY_MAP = {
    # Hindi
    "दिल्ली": "Delhi",
    "नई दिल्ली": "Delhi",
    "मुंबई": "Mumbai",
    "लखनऊ": "Lucknow",
    "कंप्यूटर विज्ञान": "Computer Science",
    "मेकैनिकल": "Mechanical Engineering",
    "सिविल": "Civil Engineering",
    
    # Spanish
    "Nueva Delhi": "Delhi",
    "Informática": "Computer Science",
    
    # German
    "München": "Munich",
    "Informatik": "Computer Science",
    
    # French
    "Londres": "London",
    
    # Base English aliases
    "New Delhi": "Delhi",
    "CS": "Computer Science",
    "CSE": "Computer Science",
    "ME": "Mechanical Engineering",
    "CE": "Civil Engineering"
}

def normalize_entities(question: str) -> str:
    """Replaces localized entities with their canonical database names."""
    if not question:
        return question
        
    normalized = question
    for local_name, canonical_name in ENTITY_MAP.items():
        # Case insensitive replacement for english variations could be added,
        # but for exact match unicode strings we replace directly.
        # Use regex for word boundaries for English acronyms
        if local_name in ["CS", "CSE", "ME", "CE"]:
            normalized = re.sub(rf"\b{local_name}\b", canonical_name, normalized)
        elif local_name in normalized:
            normalized = normalized.replace(local_name, canonical_name)
            logger.info(f"Normalized entity: '{local_name}' -> '{canonical_name}'")
            
    return normalized

def translate_to_english(question: str, source_lang: str) -> str:
    """Translates a foreign language query entirely to English using the LLM for the SQL pipeline."""
    if not question or source_lang == "English":
        return question
        
    from llm_provider import manager
    
    prompt = f"""You are a translation engine.
Translate the following {source_lang} query to English. 
Keep academic entities (like departments, subjects, cities) accurate.
For example, translate "दिल्ली" as "Delhi", "कंप्यूटर विज्ञान" as "Computer Science".

Query: {question}

Return ONLY the translated English string."""
    
    translated, _, _, _ = manager.generate_with_retry(prompt, task_type="conversation")
    if translated:
        logger.info(f"Translated query from {source_lang}: '{question}' -> '{translated.strip()}'")
        return translated.strip()
    return question

def normalize_entity_dict(filters: dict) -> dict:
    """Canonicalizes the values inside an extracted filter dictionary."""
    if not filters:
        return {}
        
    normalized_dict = {}
    for k, v in filters.items():
        if isinstance(v, str):
            normalized_dict[k] = normalize_entities(v)
        elif isinstance(v, list):
            normalized_dict[k] = [normalize_entities(item) if isinstance(item, str) else item for item in v]
        else:
            normalized_dict[k] = v
            
    return normalized_dict
