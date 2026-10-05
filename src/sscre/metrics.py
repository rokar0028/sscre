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
    generation_failures: int = Field(ge=0)


class MetricsCollector:
    def __init__(self) -> None:
        self.cache_hits = 0
        self.cache_misses = 0
        self.generation_failures = 0

    def record_hit(self) -> None:
        self.cache_hits += 1

    def record_miss(self) -> None:
        self.cache_misses += 1

    def record_generation_failure(self) -> None:
        self.generation_failures += 1

    def snapshot(
        self,
        *,
        request_id: UUID,
        total_latency_ms: int,
        llm_latency_ms: int = 0,
        llm_input_tokens: int = 0,
        llm_output_tokens: int = 0,
    ) -> RequestMetrics:
        return RequestMetrics(
            request_id=request_id,
            total_latency_ms=total_latency_ms,
            llm_latency_ms=llm_latency_ms,
            llm_input_tokens=llm_input_tokens,
            llm_output_tokens=llm_output_tokens,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            generation_failures=self.generation_failures,
        )
