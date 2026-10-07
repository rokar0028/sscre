import json
from pathlib import Path

from sscre.provider_measure import build_unavailable_measurement


ROOT = Path(__file__).resolve().parents[1]


def test_unavailable_measurement_is_redacted_and_explicit() -> None:
    payload = build_unavailable_measurement(
        benchmark_path=ROOT / "benchmarks" / "development.jsonl",
        config_path=ROOT / "experiments" / "evaluation_config.json",
        reason="live_opt_in_missing",
    )

    encoded = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "unavailable"
    assert payload["provider_available"] is False
    assert payload["requests"]["count"] == 0
    assert payload["cost_usd"]["source"] == "unavailable"
    assert payload["redaction"]["raw_prompts"] is False
    assert payload["redaction"]["raw_answers"] is False
    assert "Write Python" not in encoded
    assert "api_key" not in encoded.lower()
    assert "authorization" not in encoded.lower()
