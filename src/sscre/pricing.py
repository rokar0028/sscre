"""Versioned provider pricing and conservative request cost accounting."""

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Literal


PricingSource = Literal["provider_list_estimate", "measured_charge", "synthetic_placeholder"]


@dataclass(frozen=True)
class PricingSchedule:
    schedule_id: str
    currency: str
    effective_date: str
    source: PricingSource
    generation_input_per_1k: float
    generation_output_per_1k: float
    embedding_input_per_1k: float
    cache_lookup_per_request: float = 0.0
    preprocessing_per_request: float = 0.0

    def __post_init__(self) -> None:
        if not self.schedule_id.strip():
            raise ValueError("schedule_id must not be empty")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        try:
            date.fromisoformat(self.effective_date)
        except ValueError as exc:
            raise ValueError("effective_date must be ISO-8601 date") from exc
        for name in (
            "generation_input_per_1k",
            "generation_output_per_1k",
            "embedding_input_per_1k",
            "cache_lookup_per_request",
            "preprocessing_per_request",
        ):
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")

    def redacted(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "currency": self.currency.upper(),
            "effective_date": self.effective_date,
            "source": self.source,
            "unit": "USD per 1,000 tokens and USD per request",
            "generation_input_per_1k": self.generation_input_per_1k,
            "generation_output_per_1k": self.generation_output_per_1k,
            "embedding_input_per_1k": self.embedding_input_per_1k,
            "cache_lookup_per_request": self.cache_lookup_per_request,
            "preprocessing_per_request": self.preprocessing_per_request,
        }


@dataclass(frozen=True)
class CostBreakdown:
    generation_cost_usd: float | None
    embedding_cost_usd: float | None
    retry_cost_usd: float | None
    wrapper_cost_usd: float | None
    total_estimated_cost_usd: float | None
    cost_source: str
    pricing_schedule_id: str | None


def estimate_request_cost(
    schedule: PricingSchedule | None,
    *,
    generation_input_tokens: int = 0,
    generation_output_tokens: int = 0,
    embedding_input_tokens: int = 0,
    generation_retry_count: int = 0,
    embedding_retry_count: int = 0,
    cache_lookup: bool = True,
    preprocessing: bool = True,
) -> CostBreakdown:
    """Estimate one request without inventing charges for failed retries."""
    for name, value in (
        ("generation_input_tokens", generation_input_tokens),
        ("generation_output_tokens", generation_output_tokens),
        ("embedding_input_tokens", embedding_input_tokens),
        ("generation_retry_count", generation_retry_count),
        ("embedding_retry_count", embedding_retry_count),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if schedule is None:
        return CostBreakdown(None, None, None, None, None, "unavailable", None)

    generation = round(
        generation_input_tokens * schedule.generation_input_per_1k / 1000
        + generation_output_tokens * schedule.generation_output_per_1k / 1000,
        6,
    )
    embedding = round(
        embedding_input_tokens * schedule.embedding_input_per_1k / 1000,
        6,
    )
    wrapper = round(
        (schedule.cache_lookup_per_request if cache_lookup else 0.0)
        + (schedule.preprocessing_per_request if preprocessing else 0.0),
        6,
    )
    has_retries = generation_retry_count > 0 or embedding_retry_count > 0
    retry_cost = None if has_retries else 0.0
    total = None if retry_cost is None else round(generation + embedding + wrapper, 6)
    return CostBreakdown(
        generation,
        embedding,
        retry_cost,
        wrapper,
        total,
        schedule.source,
        schedule.schedule_id,
    )
