from sscre.storage_evaluation import (
    StorageWorkloadItem,
    run_storage_control_evaluation,
    save_storage_control_report,
)


def test_storage_evaluation_reports_deduplication_and_expiration(tmp_path) -> None:
    report = run_storage_control_evaluation(
        [
            StorageWorkloadItem("first query", "shared answer"),
            StorageWorkloadItem("second query", "shared answer"),
            StorageWorkloadItem("first query", "shared answer"),
            StorageWorkloadItem("expired query", "expired", ttl_seconds=-1),
            StorageWorkloadItem("expired query", "expired", ttl_seconds=-1),
        ],
        dataset_version="storage-test-v1",
        max_entries=10,
        max_bytes=10_000,
    )

    assert report.report_type == "storage_controls"
    assert report.dataset_version == "storage-test-v1"
    assert report.cache_hits == 1
    assert report.deduplication_hits == 1
    assert report.no_dedup_total_bytes > report.total_bytes
    assert report.expiration_count == 2
    assert report.expired_reuse_prevented == 1
    assert report.reusable_opportunities == 2
    assert report.safe_reuse_coverage == 0.5
    assert report.latency_source.startswith("synthetic_")
    assert report.token_source.startswith("synthetic_")
    assert report.no_dedup_total_bytes > report.total_bytes

    provider_report = run_storage_control_evaluation(
        [StorageWorkloadItem(
            "provider query",
            "provider answer",
            input_tokens=12,
            output_tokens=7,
            generation_latency_ms=240,
        )],
        dataset_version="storage-provider-v1",
        input_cost_per_1k_tokens=1.0,
        output_cost_per_1k_tokens=2.0,
    )
    assert provider_report.token_source == "provider_usage_per_item"
    assert provider_report.latency_source == "provider_usage_per_item"
    assert provider_report.baseline_cost_usd == 0.026

    output = tmp_path / "storage-report.json"
    save_storage_control_report(report, output)
    assert '"report_type": "storage_controls"' in output.read_text()
