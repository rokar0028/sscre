import pytest

from sscre.llm import LLMResult, validate_llm_result


def _result(**overrides) -> LLMResult:
    values = {
        "text": "answer",
        "input_tokens": 1,
        "output_tokens": 2,
        "latency_ms": 3,
        "provider_name": "provider",
        "model_name": "model",
        "usage_source": "provider_reported",
        "attempts": 1,
        "retry_count": 0,
    }
    values.update(overrides)
    return LLMResult(**values)


def test_validate_llm_result_accepts_valid_metadata() -> None:
    assert validate_llm_result(_result()) == _result()


def test_validate_llm_result_accepts_unavailable_usage_source() -> None:
    assert validate_llm_result(_result(usage_source="unavailable")) == _result(
        usage_source="unavailable"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"input_tokens": -1},
        {"output_tokens": -1},
        {"latency_ms": -1},
        {"text": ""},
        {"provider_name": " "},
        {"model_name": ""},
        {"attempts": 0},
        {"retry_count": 1},
    ],
)
def test_validate_llm_result_rejects_invalid_metadata(overrides: dict) -> None:
    with pytest.raises(ValueError, match="invalid"):
        validate_llm_result(_result(**overrides))
