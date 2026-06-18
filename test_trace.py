import os
import sys
import json

def trace_pipeline():
    from app_server import route_question, add_message, create_session, route_conversation, get_context_for_llm
    from language_detection import detect_language, get_language_instruction
    from query_normalizer import normalize_entities
    from context_resolver import resolve_active_filters
    from memory_manager import get_active_filters

    import uuid
    session_id = f"test_trace_{uuid.uuid4().hex[:8]}"
    
    queries = [
        "Show all Computer Science students",
        "Only from Delhi",
        "दिल्ली से कितने छात्र हैं?"
    ]
    
    with open("trace_result.txt", "w", encoding="utf-8") as f:
        f.write("="*50 + "\n")
        f.write("CRITICAL TRACE: PIPELINE EXECUTION\n")
        f.write("="*50 + "\n")

        for q in queries:
            
            # 1. Add user message so filters can attach to it
            from app_server import add_message
            add_message(session_id, "user", q)
            # Detect Language
            from language_detection import detect_language, get_language_instruction
            detection_result = detect_language(q)
            detected_lang = detection_result["language"]
            lang_instruction = get_language_instruction(detected_lang)
            
            f.write(f"\n---> Raw User Query: {q}\n")
            f.write(f"Detected Language: {detected_lang}\n")
            
            # Context Persistence (Active Filters & Classification)
            from context_resolver import resolve_active_filters
            active_filters = resolve_active_filters(session_id, q)
            
            from query_normalizer import translate_to_english, normalize_entities
            translated_msg = translate_to_english(q, detected_lang)
            normalized_msg = normalize_entities(translated_msg)
            
            f.write(f"Translated/Normalized Query: {normalized_msg}\n")
            f.write(f"Merged Filters: {active_filters}\n")
            
            # Get conversational context
            context = get_context_for_llm(session_id)
            
            # Process via Conversation Router First
            routing = route_conversation(normalized_msg, context, lang_instruction)
            f.write(f"Routing Classification: {routing.get('category')} / {routing.get('query_type')}\n")
            
            if routing.get("category") != "academic_query":
                f.write(f"Processed as Conversational. Response: {routing.get('response')}\n")
                add_message(session_id, "assistant", routing.get("response"))
                continue
                
            # Proceed to academic database query
            f.write(f"Final Context Sent To Text-to-SQL: active_filters={active_filters}, normalized_msg={normalized_msg}\n")
            
            result = route_question(normalized_msg, lang_instruction=lang_instruction, active_filters=active_filters)
            f.write(f"Generated SQL: {result.generated_sql if result else None}\n")
            
            # Save assistant message
            add_message(session_id, "assistant", f"Generated SQL: {result.generated_sql if result else None}")

if __name__ == "__main__":
    trace_pipeline()
