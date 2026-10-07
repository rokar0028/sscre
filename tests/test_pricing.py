import pytest

from sscre.pricing import PricingSchedule, estimate_request_cost


def _schedule(**overrides) -> PricingSchedule:
    values = {
        "schedule_id": "prices-2026-10",
        "currency": "USD",
        "effective_date": "2026-10-07",
        "source": "provider_list_estimate",
        "generation_input_per_1k": 0.01,
        "generation_output_per_1k": 0.02,
        "embedding_input_per_1k": 0.001,
        "cache_lookup_per_request": 0.0001,
        "preprocessing_per_request": 0.0002,
    }
    values.update(overrides)
    return PricingSchedule(**values)


def test_cost_accounting_includes_generation_embedding_and_wrapper() -> None:
    result = estimate_request_cost(
        _schedule(),
        generation_input_tokens=1000,
        generation_output_tokens=500,
        embedding_input_tokens=2000,
    )

    assert result.generation_cost_usd == 0.02
    assert result.embedding_cost_usd == 0.002
    assert result.retry_cost_usd == 0.0
    assert result.wrapper_cost_usd == 0.0003
    assert result.total_estimated_cost_usd == 0.0223
    assert result.cost_source == "provider_list_estimate"


def test_exact_hit_can_exclude_embedding_and_generation() -> None:
    result = estimate_request_cost(
        _schedule(),
        cache_lookup=True,
        preprocessing=True,
    )

    assert result.generation_cost_usd == 0.0
    assert result.embedding_cost_usd == 0.0
    assert result.total_estimated_cost_usd == 0.0003


def test_semantic_hit_cost_includes_embedding_and_excludes_generation() -> None:
    result = estimate_request_cost(
        _schedule(),
        embedding_input_tokens=1500,
        cache_lookup=True,
        preprocessing=True,
    )

    assert result.generation_cost_usd == 0.0
    assert result.embedding_cost_usd == 0.0015
    assert result.total_estimated_cost_usd == 0.0018


def test_miss_cost_includes_embedding_and_generation() -> None:
    result = estimate_request_cost(
        _schedule(),
        generation_input_tokens=800,
        generation_output_tokens=400,
        embedding_input_tokens=1200,
    )

    assert result.generation_cost_usd == 0.016
    assert result.embedding_cost_usd == 0.0012
    assert result.total_estimated_cost_usd == 0.0175


def test_wrapper_cost_is_included_once_per_request() -> None:
    with_wrapper = estimate_request_cost(_schedule(), cache_lookup=True, preprocessing=True)
    without_wrapper = estimate_request_cost(
        _schedule(),
        cache_lookup=False,
        preprocessing=False,
    )

    assert with_wrapper.wrapper_cost_usd == 0.0003
    assert without_wrapper.wrapper_cost_usd == 0.0
    assert with_wrapper.total_estimated_cost_usd == 0.0003


def test_retry_cost_is_unavailable_when_failed_attempt_billing_is_unknown() -> None:
    result = estimate_request_cost(
        _schedule(),
        generation_input_tokens=100,
        generation_output_tokens=100,
        generation_retry_count=1,
    )

    assert result.retry_cost_usd is None
    assert result.total_estimated_cost_usd is None


def test_missing_schedule_is_explicitly_unavailable() -> None:
    result = estimate_request_cost(None, generation_input_tokens=10)

    assert result.total_estimated_cost_usd is None
    assert result.cost_source == "unavailable"
    assert result.pricing_schedule_id is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generation_input_per_1k", float("nan")),
        ("generation_output_per_1k", float("inf")),
        ("embedding_input_per_1k", -1.0),
    ],
)
def test_prices_must_be_finite_and_non_negative(field: str, value: float) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        _schedule(**{field: value})
