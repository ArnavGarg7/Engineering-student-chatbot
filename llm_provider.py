import os
import time
import logging
from typing import Tuple, Dict, Optional
from provider_health import health_monitor

logger = logging.getLogger("llm_provider")

class LLMProvider:
    def __init__(self, name: str):
        self.name = name

    def generate(self, prompt: str) -> Tuple[Optional[str], float]:
        raise NotImplementedError
        
class GeminiProvider(LLMProvider):
    def __init__(self):
        super().__init__("gemini")
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except ImportError:
                self.client = None
        else:
            self.client = None

    def generate(self, prompt: str) -> Tuple[Optional[str], float]:
        if not self.client:
            return None, 0.0
        start = time.time()
        from google.genai import types as genai_types
        response = self.client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(temperature=0.0, max_output_tokens=1500)
        )
        raw = response.text.strip() if response.text else ""
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else lines[0].replace("```sql", "").replace("```json", "").replace("```", "")
        return raw, time.time() - start

class GroqProvider(LLMProvider):
    def __init__(self):
        super().__init__("groq")
        self.api_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except ImportError:
                self.client = None
        else:
            self.client = None

    def generate(self, prompt: str) -> Tuple[Optional[str], float]:
        if not self.client:
            return None, 0.0
        start = time.time()
        response = self.client.chat.completions.create(
            model=self.model, 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1500
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else lines[0].replace("```sql", "").replace("```json", "").replace("```", "")
        return raw, time.time() - start

class OpenAIProvider(LLMProvider):
    def __init__(self):
        super().__init__("openai")
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                self.client = None
        else:
            self.client = None

    def generate(self, prompt: str) -> Tuple[Optional[str], float]:
        if not self.client:
            return None, 0.0
        start = time.time()
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1500
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else lines[0].replace("```sql", "").replace("```json", "").replace("```", "")
        return raw, time.time() - start

class OpenRouterProvider(LLMProvider):
    def __init__(self):
        super().__init__("openrouter")
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        self.model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key,
                )
            except ImportError:
                self.client = None
        else:
            self.client = None

    def generate(self, prompt: str) -> Tuple[Optional[str], float]:
        if not self.client:
            return None, 0.0
        start = time.time()
        response = self.client.chat.completions.create(
            model=self.model, 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1500
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else lines[0].replace("```sql", "").replace("```json", "").replace("```", "")
        return raw, time.time() - start

class ProviderManager:
    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        
        enabled_str = os.environ.get("ENABLED_PROVIDERS", "gemini,groq,openrouter,openai").lower()
        enabled_list = [x.strip() for x in enabled_str.split(",") if x.strip()]
        
        for p in [GeminiProvider(), GroqProvider(), OpenAIProvider(), OpenRouterProvider()]:
            if p.name in enabled_list and getattr(p, "client", None) is not None:
                self.providers[p.name] = p
        
        llm_default = os.environ.get("LLM_PROVIDER", "gemini").lower()
        self.active_sql = os.environ.get("TEXT_TO_SQL_PROVIDER", llm_default).lower()
        self.active_conv = os.environ.get("CONVERSATION_PROVIDER", llm_default).lower()
        
        self.fallbacks = []
        for fb in ["FALLBACK_PROVIDER", "SECOND_FALLBACK_PROVIDER", "THIRD_FALLBACK_PROVIDER"]:
            val = os.environ.get(fb)
            if val and val.lower() not in self.fallbacks:
                self.fallbacks.append(val.lower())
                
        default_order = ["gemini", "groq", "openrouter", "openai"]
        for d in default_order:
            if d not in self.fallbacks:
                self.fallbacks.append(d)
                
        health_monitor.active_text_to_sql_provider = self.active_sql
        health_monitor.active_conversation_provider = self.active_conv
        health_monitor.fallback_provider = self.fallbacks[0] if self.fallbacks else None

    def _get_provider_chain(self, task_type: str) -> list[str]:
        chain = []
        active = self.active_sql if task_type == "text_to_sql" else self.active_conv
        chain.append(active)
        for fb in self.fallbacks:
            if fb != active and fb not in chain:
                chain.append(fb)
        return chain
        
    def _switch_active_provider(self, task_type: str, new_provider: str):
        if task_type == "text_to_sql":
            self.active_sql = new_provider
            health_monitor.active_text_to_sql_provider = new_provider
        else:
            self.active_conv = new_provider
            health_monitor.active_conversation_provider = new_provider
        logger.info(f"ProviderManager: Switched active '{task_type}' provider to {new_provider}.")

    def generate_with_retry(self, prompt: str, task_type: str = "text_to_sql") -> Tuple[Optional[str], Optional[str], float, int]:
        """Returns (response, provider_name, latency, fallback_depth)"""
        chain = self._get_provider_chain(task_type)
        fallback_depth = 0
        
        for provider_name in chain:
            if provider_name not in self.providers:
                fallback_depth += 1
                continue
                
            provider = self.providers[provider_name]
            
            with health_monitor._lock:
                stats = health_monitor.providers.get(provider_name)
                if stats and stats.status == "degraded":
                    logger.info(f"ProviderManager: Skipping {provider_name} because it is degraded.")
                    fallback_depth += 1
                    continue
                    
            retries = [1, 2, 4]
            for attempt, wait_time in enumerate([0] + retries):
                if attempt > 0:
                    logger.warning(f"ProviderManager: Retrying {provider_name} in {wait_time}s (Attempt {attempt}).")
                    time.sleep(wait_time)
                
                try:
                    logger.info(f"ProviderManager: Calling {provider_name}...")
                    response, latency = provider.generate(prompt)
                    
                    if response:
                        health_monitor.record_success(provider_name, latency)
                        if fallback_depth > 0:
                            self._switch_active_provider(task_type, provider_name)
                        return response, provider_name, latency, fallback_depth
                        
                except Exception as e:
                    err_str = str(e).lower()
                    non_retryable_codes = ["400", "401", "403", "404"]
                    non_retryable_terms = ["decommissioned", "invalid", "not found", "does not exist"]
                    
                    is_fatal = any(c in err_str for c in non_retryable_codes) or any(t in err_str for t in non_retryable_terms)
                    
                    if is_fatal:
                        logger.error(f"ProviderManager: {provider_name} fatal error: {e}. Skipping retries.")
                        break # break out of retry loop immediately
                        
                    logger.warning(f"ProviderManager: {provider_name} call failed: {e}")
                    
            health_monitor.record_failure(provider_name)
            logger.error(f"ProviderManager: {provider_name} completely failed. Moving to next provider.")
            fallback_depth += 1
            
        return None, None, 0.0, fallback_depth

    def test_provider(self, provider_name: str) -> bool:
        if provider_name not in self.providers:
            return False
        provider = self.providers[provider_name]
        try:
            response, _ = provider.generate("Reply 'OK'")
            return response is not None and "OK" in response.upper()
        except Exception:
            return False

manager = ProviderManager()
