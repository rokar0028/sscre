"""Development-split float32 embedding storage replay and baseline artifact.

Inserts every directed request through the Strategy C cache entry helper with
caps unset. Duplicate normalized queries stay one entry. The baseline writer
does not run ``storage_evaluation`` and does not quantize embeddings.
"""

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path

from sscre.baseline import (
    _baseline_cache_entry_after_generation,
    _insert_if_absent,
)
from sscre.benchmark import BenchmarkRecord, load_benchmark_jsonl
from sscre.benchmark_splits import file_sha256
from sscre.cache import CacheByteBreakdown, InMemoryExactCache
from sscre.embedding import FakeEmbeddingClient
from sscre.llm import MockLLMClient
from sscre.metadata import extract_metadata
from sscre.query import hash_query, normalize_query
from sscre.storage_evaluation import _git_metadata

DEVELOPMENT_BENCHMARK = Path("benchmarks/development.jsonl")
EVALUATION_CONFIG = Path("experiments/evaluation_config.json")
BASELINE_OUTPUT = Path("artifacts/evaluation/phase3-embedding-storage-baseline.json")
DATASET_VERSION = "reviewed-query-pairs-2.0"
DOMINANCE_SHARE = 0.20
BYTES_PER_DIMENSION = 4


class EmbeddingStorageBaselineError(ValueError):
    """Raised when a capped replay evicts entries."""


@dataclass(frozen=True)
class EmbeddingStorageReplay:
    requests: int
    entries: int
    duplicate_requests: int
    eviction_count: int
    embedding_model: str
    embedding_dimensions: int
    max_entries: int | None
    max_bytes: int | None
    breakdown: CacheByteBreakdown


def replay_development_embedding_storage(
    records: list[BenchmarkRecord],
    *,
    max_entries: int | None = None,
    max_bytes: int | None = None,
) -> EmbeddingStorageReplay:
    """Replay both pair directions and return the in-memory byte breakdown.

    ``max_entries`` and ``max_bytes`` stay unset for the Feature 6 baseline.
    A run that evicts is rejected so it cannot be saved as that baseline.
    """
    if (max_entries is None) != (max_bytes is None):
        raise ValueError("max_entries and max_bytes must be provided together")
    if max_entries is not None and max_entries <= 0:
        raise ValueError("max_entries must be positive")
    if max_bytes is not None and max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    embedding_client = FakeEmbeddingClient()
    llm_client = MockLLMClient()
    cache = InMemoryExactCache(
        embedding_dimension=embedding_client.config.dimension,
    )
    requests = 0
    duplicate_requests = 0

    for record in records:
        for query in (record.query_a, record.query_b):
            normalized_query = normalize_query(query)
            query_hash = hash_query(normalized_query)
            requests += 1
            if cache.get_by_query_hash(query_hash) is not None:
                duplicate_requests += 1
            embedding_result = embedding_client.embed(normalized_query)
            generated = llm_client.generate(normalized_query)
            _insert_if_absent(
                cache,
                _baseline_cache_entry_after_generation(
                    query_hash=query_hash,
                    normalized_query=normalized_query,
                    answer=generated.text,
                    query_metadata=replace(
                        extract_metadata(normalized_query),
                        temporal_class=record.freshness_class,
                    ),
                    embedding_result=embedding_result,
                    freshness_replay_clock=None,
                ),
                max_entries=max_entries,
                max_bytes=max_bytes,
            )

    stats = cache.storage_stats()
    if stats.evictions != 0:
        raise EmbeddingStorageBaselineError(
            "embedding storage baseline requires eviction_count == 0; "
            "leave max_entries and max_bytes unset"
        )
    return EmbeddingStorageReplay(
        requests=requests,
        entries=stats.entries,
        duplicate_requests=duplicate_requests,
        eviction_count=stats.evictions,
        embedding_model=embedding_client.config.model_name,
        embedding_dimensions=embedding_client.config.dimension,
        max_entries=max_entries,
        max_bytes=max_bytes,
        breakdown=cache.byte_breakdown(),
    )


def quantize_authorized(embedding_share: float) -> bool:
    """True only when embeddings are at least 20% of measured cache bytes."""
    return embedding_share >= DOMINANCE_SHARE


def embedding_storage_baseline_document(
    replay: EmbeddingStorageReplay,
    *,
    dataset_version: str,
    development_sha256: str,
    config_sha256: str,
    git_commit: str | None,
    git_worktree_dirty: bool | None,
) -> dict[str, object]:
    """Build the Feature 6 artifact body from an uncapped replay."""
    if replay.max_entries is not None or replay.max_bytes is not None:
        raise EmbeddingStorageBaselineError(
            "embedding storage baseline requires unset max_entries and max_bytes"
        )
    if replay.eviction_count != 0:
        raise EmbeddingStorageBaselineError(
            "embedding storage baseline requires eviction_count == 0"
        )
    if replay.entries <= 0 or replay.breakdown.total_bytes <= 0:
        raise EmbeddingStorageBaselineError(
            "embedding storage baseline requires a non-empty cache"
        )
    parts = replay.breakdown
    share = parts.embedding_share
    return {
        "report_type": "phase3_embedding_storage_baseline",
        "dataset_version": dataset_version,
        "split": "development",
        "development_sha256": development_sha256,
        "config_sha256": config_sha256,
        "git_commit": git_commit,
        "git_worktree_dirty": git_worktree_dirty,
        "measurement_environment": "synthetic_replay",
        "embedding_provider": "fake",
        "embedding_model": replay.embedding_model,
        "embedding_dimensions": replay.embedding_dimensions,
        "embedding_dtype": "float32",
        "bytes_per_dimension": BYTES_PER_DIMENSION,
        "requests": replay.requests,
        "entries": replay.entries,
        "duplicate_requests": replay.duplicate_requests,
        "query_bytes": parts.query_bytes,
        "metadata_bytes": parts.metadata_bytes,
        "embedding_bytes": parts.embedding_bytes,
        "answer_bytes": parts.answer_bytes,
        "total_bytes": parts.total_bytes,
        "embedding_share": share,
        "average_entry_bytes": parts.total_bytes / replay.entries,
        "eviction_count": replay.eviction_count,
        "max_entries": None,
        "max_bytes": None,
        "quantize_authorized": quantize_authorized(share),
    }


def write_embedding_storage_baseline(
    output_path: str | Path,
    *,
    benchmark_path: str | Path = DEVELOPMENT_BENCHMARK,
    config_path: str | Path = EVALUATION_CONFIG,
    dataset_version: str = DATASET_VERSION,
) -> dict[str, object]:
    """Replay development records and write the float32 storage baseline."""
    benchmark = Path(benchmark_path)
    config = Path(config_path)
    config_payload = json.loads(config.read_text(encoding="utf-8"))
    configured_version = config_payload.get("dataset_version")
    if configured_version != dataset_version:
        raise ValueError(
            "dataset version does not match evaluation config "
            f"({configured_version!r} != {dataset_version!r})"
        )
    replay = measure_development_embedding_storage(benchmark)
    git_commit, git_worktree_dirty = _git_metadata()
    document = embedding_storage_baseline_document(
        replay,
        dataset_version=dataset_version,
        development_sha256=file_sha256(benchmark),
        config_sha256=file_sha256(config),
        git_commit=git_commit,
        git_worktree_dirty=git_worktree_dirty,
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=DEVELOPMENT_BENCHMARK)
    parser.add_argument("--config", type=Path, default=EVALUATION_CONFIG)
    parser.add_argument("--output", type=Path, default=BASELINE_OUTPUT)
    parser.add_argument("--dataset-version", default=DATASET_VERSION)
    args = parser.parse_args(argv)
    document = write_embedding_storage_baseline(
        args.output,
        benchmark_path=args.benchmark,
        config_path=args.config,
        dataset_version=args.dataset_version,
    )
    print(
        "quantize_authorized="
        f"{str(document['quantize_authorized']).lower()} "
        f"embedding_share={document['embedding_share']:.6f} "
        f"output={args.output}"
    )
    return 0


def measure_development_embedding_storage(
    benchmark_path: str | Path = DEVELOPMENT_BENCHMARK,
    *,
    max_entries: int | None = None,
    max_bytes: int | None = None,
) -> EmbeddingStorageReplay:
    """Load a development JSONL file and replay it for the storage baseline."""
    records = load_benchmark_jsonl(benchmark_path)
    return replay_development_embedding_storage(
        records,
        max_entries=max_entries,
        max_bytes=max_bytes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
