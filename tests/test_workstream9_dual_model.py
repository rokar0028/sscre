from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.dual_model import (
    DUAL_MODEL_EXPERIMENT_ID,
    DUAL_MODEL_EXPERIMENT_SCHEMA_VERSION,
    DualModelExperimentError,
    authorize_dual_model_execution,
    build_provider_clients,
    build_unavailable_dual_model_result,
    load_dual_model_experiment,
    main,
    resolve_dual_model_unavailable_reason,
    run_dual_model_experiment,
    validate_dual_model_experiment,
    validate_dual_model_result,
    write_dual_model_result,
)
from sscre.llm import LLMResult
from sscre.remote_llm import RemoteLLMError

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXPERIMENT = _REPO_ROOT / "experiments" / "workstream9_dual_model_v1.json"
_MANIFEST = _REPO_ROOT / "benchmarks" / "split_manifest.json"
_DEVELOPMENT = _REPO_ROOT / "benchmarks" / "development.jsonl"


def test_checked_in_definition_is_valid_and_disabled() -> None:
    payload = load_dual_model_experiment()

    assert payload["dual_model_experiment_schema_version"] == (
        DUAL_MODEL_EXPERIMENT_SCHEMA_VERSION
    )
    assert payload["experiment_id"] == DUAL_MODEL_EXPERIMENT_ID
    assert payload["enabled"] is False
    assert payload["approval"]["status"] == "pending"
    assert payload["approval"]["model_pair_approved"] is False
    assert payload["approval"]["budget_approved"] is False
    assert payload["sample"]["evaluation_split"] == "development"
    assert payload["sample"]["operating_point_change"] is False
    assert payload["correctness_unavailable"]["status"] == "unavailable"
    assert "preference_review" in payload
    assert "correctness_review" not in payload
    with pytest.raises(DualModelExperimentError, match="disabled"):
        authorize_dual_model_execution(payload)


def test_definition_rejects_forbidden_raw_content_and_credentials() -> None:
    payload = load_dual_model_experiment()
    payload["prompt"] = "unrestricted prompt text"
    with pytest.raises(DualModelExperimentError, match="redaction"):
        validate_dual_model_experiment(payload)

    payload = load_dual_model_experiment()
    payload["api_key"] = "secret-value"
    with pytest.raises(DualModelExperimentError, match="redaction"):
        validate_dual_model_experiment(payload)


def test_enabled_definition_requires_approval_and_bound_models() -> None:
    payload = load_dual_model_experiment()
    payload["enabled"] = True
    with pytest.raises(DualModelExperimentError, match="pending approval"):
        validate_dual_model_experiment(payload)

    payload["approval"] = {
        "status": "approved",
        "model_pair_approved": True,
        "budget_approved": True,
        "approved_by": "test",
        "approved_at": "2026-10-11T00:00:00+00:00",
    }
    with pytest.raises(DualModelExperimentError, match="pending approval"):
        validate_dual_model_experiment(payload)

    payload["models"]["model_a"]["model_identifier"] = "generation-a"
    payload["models"]["model_a"]["version_identifier"] = "generation-a-v1"
    payload["models"]["model_b"]["model_identifier"] = "generation-b"
    payload["models"]["model_b"]["version_identifier"] = "generation-b-v1"
    payload["models"]["endpoint_origin"] = "https://api.example.test"
    payload["models"]["endpoint_origin_status"] = "recorded"
    validate_dual_model_experiment(payload)
    authorize_dual_model_execution(payload)


def test_malformed_definition_fails_closed() -> None:
    payload = load_dual_model_experiment()
    del payload["hypothesis"]
    with pytest.raises(DualModelExperimentError, match="missing field"):
        validate_dual_model_experiment(payload)


def test_sample_ids_are_development_stable_pairs() -> None:
    payload = load_dual_model_experiment()
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    records = {}
    for line in _DEVELOPMENT.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        records[record["id"]] = record

    assert payload["sample"]["split_manifest_sha256"] == (
        "68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51"
    )
    for pair_id in payload["sample"]["pair_ids"]:
        assert pair_id in manifest["development"]["record_ids"]
        record = records[pair_id]
        assert record["review_status"] == "final"
        assert record["freshness_class"] == "stable"
        assert pair_id not in manifest["held_out_test"]["record_ids"]


def test_definition_does_not_embed_queries_or_answers() -> None:
    text = _EXPERIMENT.read_text(encoding="utf-8")
    first = json.loads(_DEVELOPMENT.read_text(encoding="utf-8").splitlines()[0])

    assert first["query_a"] not in text
    assert '"query"' not in text
    assert '"prompt"' not in text
    assert '"answer"' not in text
    assert "api_key" not in text


class _FakeClient:
    def __init__(self, name: str, *, fail: str | None = None) -> None:
        self.name = name
        self.fail = fail
        self.calls = 0

    def generate(self, query: str) -> LLMResult:
        self.calls += 1
        if self.fail:
            raise RemoteLLMError(self.fail)
        return LLMResult(
            text="bounded",
            input_tokens=2,
            output_tokens=1,
            latency_ms=3,
            provider_name="test",
            model_name=self.name,
        )


def _approved_experiment(*, pair_ids: list[str] | None = None) -> dict[str, object]:
    payload = load_dual_model_experiment()
    payload["enabled"] = True
    payload["approval"] = {
        "status": "approved",
        "model_pair_approved": True,
        "budget_approved": True,
        "approved_by": "test",
        "approved_at": "2026-10-11T00:00:00+00:00",
    }
    payload["models"]["model_a"]["model_identifier"] = "generation-a"
    payload["models"]["model_a"]["version_identifier"] = "generation-a-v1"
    payload["models"]["model_b"]["model_identifier"] = "generation-b"
    payload["models"]["model_b"]["version_identifier"] = "generation-b-v1"
    payload["models"]["endpoint_origin"] = "https://api.example.test"
    payload["models"]["endpoint_origin_status"] = "recorded"
    if pair_ids is not None:
        payload["sample"]["pair_ids"] = pair_ids
        payload["sample"]["sample_size"] = len(pair_ids)
    return payload


def test_cli_requires_opt_in_and_rejects_disabled_definition(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "result.json"
    assert main(["--output", str(output)]) == 1
    assert "requires --package-unavailable or --opt-in" in capsys.readouterr().err
    assert not output.exists()

    assert main(["--opt-in", "--output", str(output)]) == 1
    assert "disabled" in capsys.readouterr().err
    assert not output.exists()


def test_cli_help_does_not_call_providers() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_runner_records_redacted_results_for_declared_sample_only() -> None:
    experiment = _approved_experiment(pair_ids=["pair-0001", "pair-0003"])
    first = json.loads(_DEVELOPMENT.read_text(encoding="utf-8").splitlines()[0])
    clients = {
        "model_a": _FakeClient("generation-a"),
        "model_b": _FakeClient("generation-b"),
    }

    result = run_dual_model_experiment(experiment, clients=clients)

    validate_dual_model_result(result)
    assert result["status"] == "stopped"
    assert result["stop_reason"] == "review_shortfall"
    assert result["sample"]["declared_pair_ids"] == ["pair-0001", "pair-0003"]
    assert result["sample"]["loaded_pair_ids"] == ["pair-0001", "pair-0003"]
    assert result["sample"]["unattempted_pair_ids"] == []
    assert [row["pair_id"] for row in result["pairs"]] == ["pair-0001", "pair-0003"]
    assert result["pairs"][0]["model_a"]["status"] == "ok"
    assert result["preference"]["status"] == "unavailable"
    assert result["preference"]["assigned_denominator"] == 2
    assert result["preference"]["missing_reviews"] == 2
    assert result["provider_summary"]["pairs_attempted"] == 2
    assert result["provider_summary"]["pairs_with_both_models_ok"] == 2
    assert result["correctness"]["status"] == "unavailable"
    assert result["correctness"]["review_scope"] == "unavailable"
    assert result["preference_implies_correctness"] is False
    encoded = json.dumps(result)
    assert first["query_a"] not in encoded
    assert "bounded" not in encoded
    assert "query_a" not in encoded
    assert clients["model_a"].calls == 2
    assert clients["model_b"].calls == 2


def test_runner_stops_on_budget_and_consecutive_failures() -> None:
    budget_experiment = _approved_experiment(pair_ids=["pair-0001", "pair-0003"])
    budget_experiment["budget"]["max_requests"] = 1
    budget_clients = {
        "model_a": _FakeClient("generation-a"),
        "model_b": _FakeClient("generation-b"),
    }

    budget_result = run_dual_model_experiment(
        budget_experiment, clients=budget_clients
    )

    assert budget_result["stop_reason"] == "budget_exhausted"
    assert budget_result["budget_usage"]["requests"] == 1
    assert budget_result["sample"]["unattempted_pair_ids"] == ["pair-0003"]
    assert budget_clients["model_a"].calls == 1
    assert budget_clients["model_b"].calls == 0

    fail_experiment = _approved_experiment(
        pair_ids=["pair-0001", "pair-0003", "pair-0004"]
    )
    fail_clients = {
        "model_a": _FakeClient("generation-a", fail="transient_provider"),
        "model_b": _FakeClient("generation-b", fail="timeout"),
    }

    fail_result = run_dual_model_experiment(fail_experiment, clients=fail_clients)

    assert fail_result["stop_reason"] == "consecutive_provider_failures"
    assert fail_result["sample"]["unattempted_pair_ids"] == ["pair-0004"]
    assert fail_clients["model_a"].calls == 2
    assert fail_result["pairs"][0]["model_a"]["status"] == "transient"
    assert fail_result["pairs"][0]["model_b"]["status"] == "timeout"


def test_runner_records_missing_declared_pairs_as_exclusions(
    tmp_path: Path,
) -> None:
    experiment = _approved_experiment(pair_ids=["pair-0001", "pair-missing"])
    source = tmp_path / "development.jsonl"
    source.write_text(_DEVELOPMENT.read_text(encoding="utf-8").splitlines()[0] + "\n")
    experiment["sample"]["benchmark_path"] = "development.jsonl"
    manifest_dir = tmp_path / "benchmarks"
    manifest_dir.mkdir(parents=True)
    manifest_dir.joinpath("split_manifest.json").write_text(
        _MANIFEST.read_text(encoding="utf-8")
    )

    result = run_dual_model_experiment(
        experiment,
        clients={
            "model_a": _FakeClient("generation-a"),
            "model_b": _FakeClient("generation-b"),
        },
        repo_root=tmp_path,
    )

    assert result["sample"]["loaded_pair_ids"] == ["pair-0001"]
    assert result["sample"]["excluded_pairs"] == [
        {"pair_id": "pair-missing", "reason": "pair_not_in_benchmark"}
    ]


def test_disabled_runner_does_not_use_provider_clients() -> None:
    with pytest.raises(DualModelExperimentError, match="disabled"):
        run_dual_model_experiment(
            load_dual_model_experiment(),
            clients={
                "model_a": _FakeClient("generation-a"),
                "model_b": _FakeClient("generation-b"),
            },
        )
    with pytest.raises(DualModelExperimentError, match="disabled"):
        build_provider_clients(load_dual_model_experiment())


def test_default_application_path_does_not_import_dual_model() -> None:
    app_source = (_REPO_ROOT / "src" / "sscre" / "app.py").read_text(encoding="utf-8")
    assert "dual_model" not in app_source


def test_unavailable_result_packages_without_provider_substitution(
    tmp_path: Path,
) -> None:
    experiment = load_dual_model_experiment()
    assert resolve_dual_model_unavailable_reason(experiment) == "experiment_disabled"

    result = build_unavailable_dual_model_result(
        experiment,
        unavailable_reason="experiment_disabled",
    )
    validate_dual_model_result(result)
    assert result["status"] == "unavailable"
    assert result["unavailable_reason"] == "experiment_disabled"
    assert result["measurement_environment"] == "unavailable"
    assert result["pairs"] == []
    assert result["budget_usage"]["requests"] == 0
    assert result["preference"]["disagreements"] == 0
    assert result["correctness"]["review_scope"] == "unavailable"
    encoded = json.dumps(result)
    assert "bounded" not in encoded

    output = tmp_path / "unavailable.json"
    assert (
        main(
            [
                "--package-unavailable",
                "--config",
                str(_EXPERIMENT),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    packaged = json.loads(output.read_text(encoding="utf-8"))
    validate_dual_model_result(packaged)
    assert packaged["status"] == "unavailable"


def test_result_rejects_preference_embedded_in_provider_observations() -> None:
    experiment = _approved_experiment(pair_ids=["pair-0001"])
    result = run_dual_model_experiment(
        experiment,
        clients={
            "model_a": _FakeClient("generation-a"),
            "model_b": _FakeClient("generation-b"),
        },
    )
    result["pairs"][0]["preference"]["latency_ms"] = 3
    with pytest.raises(DualModelExperimentError, match="provider measurements"):
        validate_dual_model_result(result)


def test_result_requires_sample_and_models_blocks() -> None:
    result = build_unavailable_dual_model_result(
        load_dual_model_experiment(),
        unavailable_reason="experiment_disabled",
    )
    del result["sample"]
    with pytest.raises(DualModelExperimentError, match="sample"):
        validate_dual_model_result(result)


def test_declared_sample_rejects_manifest_mismatch() -> None:
    experiment = _approved_experiment(pair_ids=["pair-0001"])
    experiment["sample"]["split_manifest_sha256"] = "0" * 64
    with pytest.raises(DualModelExperimentError, match="manifest"):
        run_dual_model_experiment(
            experiment,
            clients={
                "model_a": _FakeClient("generation-a"),
                "model_b": _FakeClient("generation-b"),
            },
            repo_root=_REPO_ROOT,
        )


def test_write_dual_model_result_validates_before_write(tmp_path: Path) -> None:
    result = build_unavailable_dual_model_result(
        load_dual_model_experiment(),
        unavailable_reason="experiment_disabled",
    )
    output = tmp_path / "result.json"
    write_dual_model_result(result, output)
    validate_dual_model_result(json.loads(output.read_text(encoding="utf-8")))
