import json
from pathlib import Path

import pytest

from sscre.benchmark import BenchmarkMetadata, BenchmarkRecord
from sscre.benchmark_splits import file_sha256
from sscre.cache import CacheByteBreakdown, CacheEntry, InMemoryExactCache
from sscre.phase3_embedding_storage import (
    DEVELOPMENT_BENCHMARK,
    EVALUATION_CONFIG,
    EmbeddingStorageBaselineError,
    EmbeddingStorageReplay,
    embedding_storage_baseline_document,
    measure_development_embedding_storage,
    quantize_authorized,
    write_embedding_storage_baseline,
)
from sscre.safety import QueryMetadata


def _entry(
    query_hash: str,
    query: str,
    answer: str,
    *,
    embedding: tuple[float, ...] | None = None,
    metadata: QueryMetadata | None = None,
) -> CacheEntry:
    return CacheEntry(
        query_hash=query_hash,
        normalized_query=query,
        answer=answer,
        embedding=embedding,
        embedding_model="fake-embedding" if embedding is not None else None,
        embedding_dimension=len(embedding) if embedding is not None else None,
        metadata=metadata,
    )


def test_breakdown_without_embedding_matches_storage_bytes() -> None:
    cache = InMemoryExactCache()
    cache.insert(_entry("h1", "café", "answer"))
    parts = cache.byte_breakdown()

    assert parts.embedding_bytes == 0
    assert parts.query_bytes == len("café".encode("utf-8"))
    assert parts.total_bytes == cache.storage_bytes()
    assert parts.total_bytes == cache.storage_stats().total_bytes
    assert parts.embedding_share == 0.0
    metadata = json.dumps({}, separators=(",", ":"), ensure_ascii=False)
    assert parts.metadata_bytes == len(metadata.encode("utf-8"))
    assert (
        parts.query_bytes
        + parts.metadata_bytes
        + parts.embedding_bytes
        + parts.answer_bytes
        == cache.storage_bytes()
    )


def test_embedding_bytes_are_four_per_dimension() -> None:
    embedding = (0.1, -0.2, 0.3, 0.4)
    cache = InMemoryExactCache()
    cache.insert(
        _entry(
            "h1",
            "query",
            "answer",
            embedding=embedding,
            metadata=QueryMetadata(domain="programming", entities=("café",)),
        )
    )
    parts = cache.byte_breakdown()

    assert parts.embedding_bytes == len(embedding) * 4
    assert parts.total_bytes == cache.storage_bytes()
    assert parts.embedding_share == parts.embedding_bytes / parts.total_bytes


def test_dedup_counts_shared_answer_once() -> None:
    answer = "shared-answer"
    embedding = (0.5, 0.5)
    dedup = InMemoryExactCache(deduplicate=True)
    plain = InMemoryExactCache(deduplicate=False)
    for cache in (dedup, plain):
        cache.insert(_entry("h1", "first", answer, embedding=embedding))
        cache.insert(_entry("h2", "second", answer, embedding=embedding))

    dedup_parts = dedup.byte_breakdown()
    plain_parts = plain.byte_breakdown()
    answer_bytes = len(answer.encode("utf-8"))

    assert dedup_parts.answer_bytes == answer_bytes
    assert plain_parts.answer_bytes == answer_bytes * 2
    assert dedup_parts.embedding_bytes == len(embedding) * 4 * 2
    assert dedup_parts.total_bytes == dedup.storage_bytes()
    assert plain_parts.total_bytes == plain.storage_bytes()
    assert dedup_parts.total_bytes < plain_parts.total_bytes


def _record(index: int, query_a: str, query_b: str) -> BenchmarkRecord:
    return BenchmarkRecord(
        id=f"pair-{index:04d}",
        query_a=query_a,
        query_b=query_b,
        reusable=True,
        compatibility_label="compatible",
        coverage_category="paraphrase",
        metadata=BenchmarkMetadata(domain="programming"),
        review_status="final",
    )


def _write_jsonl(path: Path, records: list[BenchmarkRecord]) -> None:
    path.write_text(
        "".join(f"{record.model_dump_json()}\n" for record in records),
        encoding="utf-8",
    )


def test_development_replay_counts_requests_separately_from_entries(tmp_path: Path) -> None:
    path = tmp_path / "development.jsonl"
    _write_jsonl(
        path,
        [
            _record(1, "Explain caching", "Explain caching"),
            _record(2, "Explain caching", "What is an embedding?"),
        ],
    )

    replay = measure_development_embedding_storage(path)

    assert replay.requests == 4
    assert replay.entries == 2
    assert replay.duplicate_requests == 2
    assert replay.entries == replay.requests - replay.duplicate_requests
    assert replay.eviction_count == 0
    assert replay.max_entries is None
    assert replay.max_bytes is None
    assert replay.embedding_model == "fake-embedding"
    assert replay.embedding_dimensions == 8
    assert replay.breakdown.embedding_bytes == replay.entries * 8 * 4
    assert replay.breakdown.total_bytes == (
        replay.breakdown.query_bytes
        + replay.breakdown.metadata_bytes
        + replay.breakdown.embedding_bytes
        + replay.breakdown.answer_bytes
    )


def test_capped_replay_with_evictions_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "development.jsonl"
    _write_jsonl(
        path,
        [_record(1, "Explain caching", "What is an embedding?")],
    )

    with pytest.raises(EmbeddingStorageBaselineError):
        measure_development_embedding_storage(
            path,
            max_entries=1,
            max_bytes=100_000_000,
        )


def test_development_split_replay_has_800_requests() -> None:
    replay = measure_development_embedding_storage(DEVELOPMENT_BENCHMARK)

    assert replay.requests == 800
    assert replay.entries == replay.requests - replay.duplicate_requests
    assert replay.eviction_count == 0
    assert replay.embedding_dimensions == 8
    assert replay.breakdown.embedding_bytes == replay.entries * 8 * 4


def _replay(**overrides: object) -> EmbeddingStorageReplay:
    breakdown = overrides.pop(
        "breakdown",
        CacheByteBreakdown(
            query_bytes=40,
            metadata_bytes=30,
            embedding_bytes=32,
            answer_bytes=98,
        ),
    )
    values = {
        "requests": 2,
        "entries": 1,
        "duplicate_requests": 1,
        "eviction_count": 0,
        "embedding_model": "fake-embedding",
        "embedding_dimensions": 8,
        "max_entries": None,
        "max_bytes": None,
        "breakdown": breakdown,
    }
    values.update(overrides)
    return EmbeddingStorageReplay(**values)


def test_quantize_gate_uses_registered_share() -> None:
    assert quantize_authorized(0.20) is True
    assert quantize_authorized(0.19) is False


def test_baseline_document_authorizes_only_dominant_embeddings() -> None:
    small = embedding_storage_baseline_document(
        _replay(),
        dataset_version="reviewed-query-pairs-2.0",
        development_sha256="abc",
        config_sha256="def",
        git_commit="abc123",
        git_worktree_dirty=False,
    )
    dominant = embedding_storage_baseline_document(
        _replay(
            breakdown=CacheByteBreakdown(
                query_bytes=10,
                metadata_bytes=10,
                embedding_bytes=50,
                answer_bytes=10,
            )
        ),
        dataset_version="reviewed-query-pairs-2.0",
        development_sha256="abc",
        config_sha256="def",
        git_commit="abc123",
        git_worktree_dirty=False,
    )

    assert small["report_type"] == "phase3_embedding_storage_baseline"
    assert small["measurement_environment"] == "synthetic_replay"
    assert small["embedding_provider"] == "fake"
    assert small["embedding_dtype"] == "float32"
    assert small["bytes_per_dimension"] == 4
    assert small["eviction_count"] == 0
    assert small["max_entries"] is None
    assert small["quantize_authorized"] is False
    assert small["embedding_share"] == small["embedding_bytes"] / small["total_bytes"]
    assert dominant["quantize_authorized"] is True
    assert dominant["average_entry_bytes"] == dominant["total_bytes"] / dominant["entries"]


def test_baseline_document_rejects_caps_and_empty_cache() -> None:
    with pytest.raises(EmbeddingStorageBaselineError):
        embedding_storage_baseline_document(
            _replay(max_entries=10, max_bytes=1000),
            dataset_version="reviewed-query-pairs-2.0",
            development_sha256="abc",
            config_sha256="def",
            git_commit=None,
            git_worktree_dirty=None,
        )
    with pytest.raises(EmbeddingStorageBaselineError):
        embedding_storage_baseline_document(
            _replay(
                entries=0,
                breakdown=CacheByteBreakdown(0, 0, 0, 0),
            ),
            dataset_version="reviewed-query-pairs-2.0",
            development_sha256="abc",
            config_sha256="def",
            git_commit=None,
            git_worktree_dirty=None,
        )


def test_write_baseline_records_hashes(tmp_path: Path) -> None:
    benchmark = tmp_path / "development.jsonl"
    _write_jsonl(benchmark, [_record(1, "Explain caching", "What is an embedding?")])
    output = tmp_path / "baseline.json"

    document = write_embedding_storage_baseline(
        output,
        benchmark_path=benchmark,
        config_path=EVALUATION_CONFIG,
    )
    saved = json.loads(output.read_text(encoding="utf-8"))

    assert saved == document
    assert saved["development_sha256"] == file_sha256(benchmark)
    assert saved["config_sha256"] == file_sha256(EVALUATION_CONFIG)
    assert saved["dataset_version"] == "reviewed-query-pairs-2.0"
    assert saved["split"] == "development"
    assert saved["requests"] == 2
    assert saved["entries"] == 2
    assert saved["eviction_count"] == 0
    assert saved["embedding_dimensions"] == 8
    assert saved["embedding_bytes"] == saved["entries"] * 8 * 4
    assert isinstance(saved["quantize_authorized"], bool)


def test_empty_cache_breakdown_is_zero() -> None:
    cache = InMemoryExactCache()
    parts = cache.byte_breakdown()

    assert parts.total_bytes == 0
    assert parts.embedding_bytes == 0
    assert cache.storage_bytes() == 0
    assert parts.embedding_share == 0.0
