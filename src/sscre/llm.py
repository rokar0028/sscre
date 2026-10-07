from typing import Literal, Protocol
from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider_name: str = "synthetic"
    model_name: str = "mock"
    usage_source: Literal["provider_reported", "estimated"] = "estimated"
    attempts: int = 1
    retry_count: int = 0


class LLMClient(Protocol):
    """Provider-independent generation boundary."""

    def generate(self, query: str) -> LLMResult:
        """Generate an answer or raise a provider/client error."""
        ...


def validate_llm_result(result: object) -> LLMResult:
    if not isinstance(result, LLMResult):
        raise ValueError("LLM provider returned an invalid result")
    if (
        not isinstance(result.text, str)
        or not result.text.strip()
        or result.input_tokens < 0
        or result.output_tokens < 0
        or result.latency_ms < 0
    ):
        raise ValueError("LLM provider returned invalid response metadata")
    if (
        not isinstance(result.provider_name, str)
        or not result.provider_name.strip()
        or not isinstance(result.model_name, str)
        or not result.model_name.strip()
        or result.usage_source not in {"provider_reported", "estimated"}
        or not isinstance(result.attempts, int)
        or isinstance(result.attempts, bool)
        or result.attempts <= 0
        or not isinstance(result.retry_count, int)
        or isinstance(result.retry_count, bool)
        or result.retry_count < 0
        or result.retry_count != result.attempts - 1
    ):
        raise ValueError("LLM provider returned invalid identity metadata")
    return result


class MockLLMClient:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def generate(self, query: str) -> LLMResult:
        started_at = perf_counter()
        if self.should_fail:
            raise RuntimeError("mock generation failed")

        text = f"Generated answer for: {query}"
        return LLMResult(
            text=text,
            input_tokens=len(query.split()),
            output_tokens=len(text.split()),
            latency_ms=int((perf_counter() - started_at) * 1000),
        )
