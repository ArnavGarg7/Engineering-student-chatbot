import logging
import json
from memory_manager import get_active_filters, update_active_filters
from llm_provider import manager

logger = logging.getLogger("context_resolver")

def resolve_active_filters(session_id: str, new_message: str) -> dict:
    """
    Intelligently updates the active context state (filters) based on the user's latest message.
    """
    from query_normalizer import normalize_entity_dict
    
    current_filters = get_active_filters(session_id)
    
    q_type = classify_query_type(new_message)
    logger.info("Deterministic Routing: %r -> %s", new_message, q_type)
    
    if q_type == "STANDALONE":
        # Clear existing filters for standalone queries
        current_filters = {}
        update_active_filters(session_id, {})
    
    if not manager.providers:
        # If no LLM, just fallback to whatever we had
        return current_filters
        
    prompt = f"""You are a strict context resolver for a database chatbot.
The user is having an ongoing conversation. They previously applied these filters:
{json.dumps(current_filters, ensure_ascii=False)}

The user just sent this new message:
"{new_message}"

RULES:
1. Identify any NEW filters or constraints in the user's new message. A filter MUST be a concrete value that restricts the data (e.g., "Computer Science", "Delhi", "Year 3", "Semester 6").
2. DO NOT extract aggregate targets or question subjects as filters. If the user asks "Which city...", then "city" is the target of the question, NOT a filter. "toppers" is a status/concept, NOT a city name.
3. ADD valid filters to the current filters.
4. OVERWRITE existing filters if the user contradicts them (e.g., changing "Delhi" to "Mumbai").
5. If the user asks a COMPLETELY new question that implies clearing old filters, then REMOVE the irrelevant old filters.
6. If the new message is just a follow-up (e.g., "Only from Delhi", "What about third year?"), KEEP the old filters and add the new ones.
7. Return ONLY raw JSON representing the final active filters. No markdown.

JSON OUTPUT FORMAT:
{{
  "department": "Computer Science",
  "city": "Delhi",
  "year": 3
}}
"""

    raw, provider, lat, depth = manager.generate_with_retry(prompt, task_type="conversation")
    
    if not raw:
        return current_filters
        
    try:
        # Extract the FIRST JSON block using regex to avoid trailing/intermediate prose
        import re
        match = re.search(r'\{[^{}]*\}', raw)
        if match:
            cleaned_raw = match.group(0)
        else:
            cleaned_raw = raw.strip()
            
        new_filters = json.loads(cleaned_raw)
        if isinstance(new_filters, dict):
            # The LLM prompt says "Return ONLY raw JSON representing the final active filters."
            merged_filters = new_filters
            
            # Clean up nulls if LLM tried to delete them
            merged_filters = {k: v for k, v in merged_filters.items() if v is not None and v != ""}
            
            # Canonicalize entities AFTER entity extraction
            merged_filters = normalize_entity_dict(merged_filters)
            
            update_active_filters(session_id, merged_filters)
            logger.info("Loaded Filters: %s", current_filters)
            logger.info("Merged Filters: %s", merged_filters)
            logger.info("Saved Filters: %s", merged_filters)
            return merged_filters
    except Exception as e:
        logger.warning("Context Resolver failed to parse JSON: %s. Raw: %s", e, raw)
        
    return current_filters

def classify_query_type(query: str) -> str:
    """
    Deterministic rule-based classification for Standalone vs Follow-up queries.
    """
    q_lower = query.lower()
    
    # Follow-up indicators
    follow_up_keywords = [
        "only from", "only ", "those", "their", "what about", "show their", "what are their", "and from"
    ]
    for kw in follow_up_keywords:
        if q_lower.startswith(kw) or kw in q_lower:
            return "FOLLOW_UP"
            
    # Standalone indicators
    standalone_keywords = [
        "how many", "which", "average", "show all", "list all", "find all", 
        "कितने", "सभी", "कौन", "how", "what is", "who"
    ]
    for kw in standalone_keywords:
        if q_lower.startswith(kw) or kw in q_lower:
            return "STANDALONE"
            
    # Default to LLM or standalone if very short
    if len(q_lower.split()) <= 3:
        return "FOLLOW_UP"
    return "STANDALONE"

def remove_active_filter(session_id: str, filter_key: str):
    current_filters = get_active_filters(session_id)
    if filter_key in current_filters:
        del current_filters[filter_key]
        update_active_filters(session_id, current_filters)
        logger.info("Removed filter %r from session %s", filter_key, session_id)
