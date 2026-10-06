from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def validate_llm_result(result: object) -> LLMResult:
    if not isinstance(result, LLMResult):
        raise ValueError("LLM provider returned an invalid result")
    if (
        not isinstance(result.text, str)
        or result.input_tokens < 0
        or result.output_tokens < 0
        or result.latency_ms < 0
    ):
        raise ValueError("LLM provider returned invalid response metadata")
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
