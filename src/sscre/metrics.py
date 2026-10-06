from threading import Lock
from uuid import UUID

from pydantic import BaseModel, Field


class RequestMetrics(BaseModel):
    request_id: UUID
    total_latency_ms: int = Field(ge=0)
    llm_latency_ms: int = Field(default=0, ge=0)
    llm_input_tokens: int = Field(default=0, ge=0)
    llm_output_tokens: int = Field(default=0, ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses: int = Field(ge=0)
    exact_hits: int = Field(default=0, ge=0)
    semantic_hits: int = Field(default=0, ge=0)
    semantic_misses: int = Field(default=0, ge=0)
    threshold_rejections: int = Field(default=0, ge=0)
    generation_failures: int = Field(ge=0)
    cache_rejections: dict[str, int] = Field(default_factory=dict)


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = Lock()
        self.cache_hits = 0
        self.cache_misses = 0
        self.exact_hits = 0
        self.semantic_hits = 0
        self.semantic_misses = 0
        self.threshold_rejections = 0
        self.generation_failures = 0
        self.cache_rejections: dict[str, int] = {}

    def record_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def record_exact_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1
            self.exact_hits += 1

    def record_semantic_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1
            self.semantic_hits += 1

    def record_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def record_semantic_miss(self) -> None:
        with self._lock:
            self.semantic_misses += 1

    def record_threshold_rejection(self) -> None:
        with self._lock:
            self.threshold_rejections += 1

    def record_generation_failure(self) -> None:
        with self._lock:
            self.generation_failures += 1

    def record_cache_rejection(self, reason: str) -> None:
        with self._lock:
            self.cache_rejections[reason] = (
                self.cache_rejections.get(reason, 0) + 1
            )

    def snapshot(
        self,
        *,
        request_id: UUID,
        total_latency_ms: int,
        llm_latency_ms: int = 0,
        llm_input_tokens: int = 0,
        llm_output_tokens: int = 0,
    ) -> RequestMetrics:
        with self._lock:
            return RequestMetrics(
                request_id=request_id,
                total_latency_ms=total_latency_ms,
                llm_latency_ms=llm_latency_ms,
                llm_input_tokens=llm_input_tokens,
                llm_output_tokens=llm_output_tokens,
                cache_hits=self.cache_hits,
                cache_misses=self.cache_misses,
                exact_hits=self.exact_hits,
                semantic_hits=self.semantic_hits,
                semantic_misses=self.semantic_misses,
                threshold_rejections=self.threshold_rejections,
                generation_failures=self.generation_failures,
                cache_rejections=dict(self.cache_rejections),
            )
