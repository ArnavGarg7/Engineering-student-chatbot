import threading
import time
import logging
from typing import Dict, Any

logger = logging.getLogger("provider_health")

class ProviderStats:
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_latency = 0.0
        self.status = "healthy"
        self.consecutive_failures = 0
    
    @property
    def average_latency(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return round(self.total_latency / self.successful_requests, 3)

class HealthMonitor:
    def __init__(self):
        self.providers: Dict[str, ProviderStats] = {}
        self._lock = threading.Lock()
        self._recovery_thread = None
        self._stop_event = threading.Event()

        self.active_text_to_sql_provider = None
        self.active_conversation_provider = None
        self.fallback_provider = None

    def start_recovery_thread(self):
        if self._recovery_thread is None:
            self._recovery_thread = threading.Thread(target=self._recovery_loop, daemon=True)
            self._recovery_thread.start()

    def _recovery_loop(self):
        while not self._stop_event.is_set():
            time.sleep(60) # User requested exactly 60 seconds
            self.check_degraded_providers()
            
    def check_degraded_providers(self):
        from llm_provider import manager
        with self._lock:
            degraded = [name for name, stats in self.providers.items() if stats.status == "degraded"]
            
        for name in degraded:
            logger.info("HealthMonitor: Running 60s recovery check for degraded provider '%s'", name)
            success = manager.test_provider(name)
            if success:
                with self._lock:
                    self.providers[name].status = "healthy"
                    self.providers[name].consecutive_failures = 0
                logger.info("HealthMonitor: Provider '%s' recovered and is now marked healthy.", name)

    def record_success(self, provider_name: str, latency: float):
        with self._lock:
            if provider_name not in self.providers:
                self.providers[provider_name] = ProviderStats()
            stats = self.providers[provider_name]
            stats.total_requests += 1
            stats.successful_requests += 1
            stats.total_latency += latency
            stats.consecutive_failures = 0

    def record_failure(self, provider_name: str):
        with self._lock:
            if provider_name not in self.providers:
                self.providers[provider_name] = ProviderStats()
            stats = self.providers[provider_name]
            stats.total_requests += 1
            stats.failed_requests += 1
            stats.consecutive_failures += 1
            
            if stats.consecutive_failures >= 3 and stats.status == "healthy":
                stats.status = "degraded"
                logger.warning("HealthMonitor: Provider '%s' marked as degraded due to 3 consecutive failures.", provider_name)

    def mark_degraded(self, provider_name: str):
        """Immediately marks a provider as degraded (used for startup validation)."""
        with self._lock:
            if provider_name not in self.providers:
                self.providers[provider_name] = ProviderStats()
            stats = self.providers[provider_name]
            stats.status = "degraded"
            logger.warning("HealthMonitor: Provider '%s' explicitly marked as degraded.", provider_name)

    def get_health_report(self) -> Dict[str, Any]:
        with self._lock:
            provider_status = {}
            for name, stats in self.providers.items():
                provider_status[name] = {
                    "status": stats.status,
                    "total_requests": stats.total_requests,
                    "successful_requests": stats.successful_requests,
                    "failed_requests": stats.failed_requests,
                    "average_latency": stats.average_latency
                }
            return {
                "active_text_to_sql_provider": self.active_text_to_sql_provider,
                "active_conversation_provider": self.active_conversation_provider,
                "fallback_provider": self.fallback_provider,
                "provider_status": provider_status
            }

health_monitor = HealthMonitor()
