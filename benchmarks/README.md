# Reviewed benchmark dataset

`reviewed_query_pairs.jsonl` is the Milestone 6 step 2 dataset.

- Schema version: `1.1`
- Dataset version: `reviewed-query-pairs-1.1`
- Records: 32 (24 baseline + 8 expansion candidates merged)
- Review status: manually reviewed ground-truth pairs
- Reusable pairs: exact duplicates, whitespace-equivalent queries, and
  semantically compatible variants
- Non-reusable pairs: language, format, entity, audience, length, numeric,
  dietary, operation, and other constraint changes

Every non-reusable record includes a short decision reason.

Evaluation label contract (compatibility vs correctness vs preference):
[EVALUATION_LABEL_CONTRACT_v1.md](./EVALUATION_LABEL_CONTRACT_v1.md).

Human review process (compatibility, correctness, preference, adjudication):
[ANNOTATION_GUIDE_v1.md](./ANNOTATION_GUIDE_v1.md) (`annotation_guide_version`
`1.0.0` in `split_manifest.json`).

## Phase 2 data policy

This benchmark is a checked-in evaluation artifact, not an operational request
or response log.

- **Approved source:** repository-authored, hand-written query pairs created
  for SSCRE evaluation. No production user prompts, provider transcripts, or
  unapproved third-party dataset content is included in this version.
- **Licensing and ownership:** the project repository owns the authored
  examples. Any future imported or externally sourced examples require a
  recorded license/permission decision before inclusion.
- **Redaction:** do not add credentials, authorization headers, API keys,
  personal data, private URLs, proprietary source text, or complete provider
  transcripts. Review text before committing it.
- **Stable identity:** IDs are immutable within a dataset version. A changed
  pair receives a new ID or dataset version; an existing ID must not be
  silently repurposed.
- **Current artifact:** `reviewed-query-pairs-1.1` contains 32 records, with
  21 development records and 11 held-out records. It is an expanded working
  baseline, not the Phase 2 target of 500 reviewed pairs.

## Pair and answer semantics

- Pairs are ordered evaluation inputs. The evaluator replays both
  `a_to_b` and `b_to_a`; compatibility must therefore be checked in the
  direction being evaluated.
- The current schema contains query text and reviewed reuse/compatibility
  labels, but no cached or generated answer payloads.
- Answer correctness and preference are therefore not collected for the
  current records beyond the existing `correctness_label` field. A future
  schema must represent answer availability separately and must leave
  correctness null when no answer was reviewed.
- A reviewed compatibility label describes whether reuse is permitted under
  the benchmark policy. It does not assert that an answer is factually
  correct, and it does not replace the observed `SAFE`, `UNSAFE`, or
  `UNCERTAIN` decision emitted by the evaluator.

## Frozen input evidence

The current input identity is defined by:

- `reviewed_query_pairs.jsonl`
- `development.jsonl`
- `held_out_test.jsonl`
- `split_manifest.json`
- dataset version `reviewed-query-pairs-1.1`
- schema version `1.1`
- annotation guide version `1.0.0`

Validate the current artifact from the repository root:

```bash
python -c "from sscre.benchmark import load_benchmark_jsonl; records = load_benchmark_jsonl('benchmarks/reviewed_query_pairs.jsonl'); print(len(records))"
```

The split manifest must continue to agree with the files:

```python
from sscre.benchmark import load_benchmark_jsonl

records = load_benchmark_jsonl("benchmarks/reviewed_query_pairs.jsonl")
```

## Evaluation splits

The split manifest is `split_manifest.json`.

- `development.jsonl` contains 21 pairs for configuration and threshold
  decisions.
- `held_out_test.jsonl` contains 11 disjoint pairs for final reporting only.
- Test labels must not be used when choosing configuration or thresholds.
- Each pair is evaluated in both directions (`a_to_b` and `b_to_a`) where the
  evaluation supports directional replay.

The split files are exact copies of records from the reviewed dataset; their
IDs are disjoint and together cover all 32 reviewed records (dataset version
`reviewed-query-pairs-1.1`).

After rebuilding splits or merging candidates, freeze manifest identity metadata
(record IDs, per-split SHA-256, leakage summary, coverage summary, tool version):

```bash
python -m sscre.benchmark_build --benchmark-dir benchmarks freeze-splits
python -m sscre.benchmark_validate --benchmark-dir benchmarks
```

Regenerating splits without bumping `dataset_version` invalidates prior frozen
manifests; treat a new `frozen_at` timestamp as the authoritative split identity
for that dataset version.

## Phase 2 record schema

Schema `1.1` defines the expanded record shape for new reviewed data. The
canonical names are:

- `expected_reuse` and `expected_compatibility` for reviewed expectations;
- `failure_category` for one primary failure category;
- `freshness_class` with `stable`, `semi_dynamic`, or `dynamic`;
- `metadata` for bounded intent, domain, entity, constraint, temporal, and
  output-format signals;
- `answer_availability` with `none`, `query_a`, `query_b`, or `both`;
- `review_status` and `annotator_count` for review state and provenance.

The legacy `reusable` and `compatibility_label` fields remain the stored
compatibility fields during this additive transition. The model exposes the
canonical `expected_*` fields and rejects contradictory values. Existing
schema `1.0` fixtures remain loadable until the record migration and expanded
dataset work is completed; new records should use schema `1.1`.

`failure_category` is a single primary category. Secondary evidence belongs in
bounded metadata or the review rationale rather than an unordered list of
categories. Correctness remains nullable, and `answer_availability: "none"`
means that no cached or generated answer was reviewed.

### Validation rules

Record loading uses `sscre.benchmark.load_benchmark_jsonl(path)`. Supported
schema versions are `1.0` and `1.1`; other versions fail closed.

- Duplicate IDs within a file are rejected.
- Query text must normalize successfully and stay within request bounds.
- Non-reusable pairs require a non-blank `reason`.
- `expected_reuse` and `expected_compatibility` must match the legacy
  compatibility fields when present.
- Preference labels require `answer_availability` other than `none`.
- Benchmark `metadata` uses the same entity and constraint size limits as
  operational trace metadata.

Schema `1.1` adds semantic checks:

- `reusable` + `compatible` → `failure_category` must be `none`.
- `incompatible` → explicit non-`none` `failure_category`.
- `uncertain` → `reusable` false and uncertain-oriented failure categories.
- `compatible` but not reusable → `stale_answer` or `temporal_mismatch`.
- `correctness_label` requires reviewed answer availability.

Schema `1.0` fixtures keep legacy validation only. The checked-in 32-pair
artifact uses schema `1.1` with reviewed `coverage_category` values.
Production-sized reviewed files may pass `require_final_review=True` so every
record has `review_status: final`.

## Category coverage

Each schema `1.1` record carries one reviewed `coverage_category` describing
why the pair exists in the benchmark. This is assigned during review; it is
not inferred from model failures.

Inclusion rules and targets live in `sscre.benchmark_coverage`:

- `WORKING_BASELINE_COVERAGE` — minimum counts and balance limits for the
  current 32-pair expanded working artifact.
- `PHASE2_REVIEWED_COVERAGE` — minimum of one record per category, freshness
  class coverage, stricter paraphrase balance, and **500+ records** for the
  Phase 2 completion target.

Validate the full artifact (manifest checksum, coverage, split leakage):

```bash
python -m sscre.benchmark_validate --benchmark-dir benchmarks
```

Require the Phase 2 size gate (fails until the dataset reaches 500 pairs):

```bash
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2
```

Stage and merge new reviewed pairs:

```bash
python -m sscre.benchmark_build validate-candidates --candidates benchmarks/candidates/expansion_v1.jsonl
python -m sscre.benchmark_build --benchmark-dir benchmarks merge --candidates benchmarks/candidates/expansion_v1.jsonl --rebuild-splits
```

Validate coverage after loading:

```python
from sscre.benchmark import load_benchmark_jsonl
from sscre.benchmark_coverage import WORKING_BASELINE_COVERAGE, validate_coverage

records = load_benchmark_jsonl("benchmarks/reviewed_query_pairs.jsonl")
validate_coverage(records, policy=WORKING_BASELINE_COVERAGE)
```

Balance policy for the working baseline:

- at least 25% positive (reusable) and 25% negative examples;
- paraphrase category must not exceed 45% of records;
- at least one example each for exact duplicates, whitespace variants,
  paraphrases, low-overlap compatible pairs, high-similarity incompatible
  pairs, intent, constraint, entity, and format changes.

The expansion slice (`pair-0025`–`pair-0032`) adds at least one example for
temporal freshness, domain change, ambiguity, stale answers, and
insufficient-evidence categories. Correctness and preference labels remain
mostly uncollected (`answer_availability: none`) until answer-bearing pairs
are reviewed.

Saved evaluation reports redact reviewed query text from failure galleries;
use the checked-in JSONL artifact and `benchmark_artifact.split_record_identity`
for approved prompt lookup.

## Workstream 2 completion evidence (2026-10-06)

| Item | Value |
|------|-------|
| Dataset version | `reviewed-query-pairs-1.1` |
| Schema version | `1.1` |
| Annotation guide | `1.0.0` |
| Total / dev / held-out | 32 / 21 / 11 |
| Phase 2 500-pair target | **Not met** (use `--phase2` to enforce) |
| Leakage | `passed` (see `split_manifest.json` `leakage_validation`) |
| Category counts | `split_manifest.json` → `coverage_summary` |
| Correctness collected | 0 pairs with reviewed answers |
| Preference collected | 0 applicable comparisons |
| Disputed / adjudicated | 0 disputed records in artifact |
| Split manifest SHA-256 | output of `benchmark_validate` (`split_manifest_sha256=…`) |

Verification (record `python --version` and `pip show sscre` with each run):

```bash
python -m pytest -q tests/test_benchmark.py tests/test_evaluation_labels.py
python -m pytest -q
python -m sscre.benchmark_validate --benchmark-dir benchmarks
```

Latest full suite: **262 passed**, 13 skipped (Postgres integration tests when
`SSCRE_DATABASE_URL` is unset).

Known limitation: Phase 2 statistical conclusions require scaling to 500+
reviewed pairs; infrastructure (schema, validation, splits, evaluate metadata)
is in place for downstream workstreams.

## Threshold sweep and held-out comparison

### Operating point

The operating point is selected on the development split only. The configured
`max_false_positive_rate` in
[`experiments/evaluation_config.json`](../experiments/evaluation_config.json)
is a constraint: eligible thresholds are filtered first, then the remaining
threshold with the greatest safe reuse coverage is selected. Held-out labels
are never passed to `_select_development_threshold`; held-out evaluation only
reports metrics and constraint satisfaction.

If no development threshold satisfies the configured cap, the sweep fails
closed for selection purposes: it records `constraint_satisfied: false` and
selects the least-unsafe threshold for diagnostic replay. This does not claim
that the operating point satisfies the cap; consumers must check the recorded
constraint flag before treating it as an approved operating point.

Run the development threshold sweep first:

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json `
  --baseline embedding-cache `
  --split development `
  --output experiments/embedding_development.json
```

Run the final comparison using a threshold selected from development data:

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all `
  --split held-out `
  --production `
  --output experiments/embedding_held_out_comparison.json
```

The held-out report includes no-cache, exact-cache, and embedding-only
baselines, latency percentiles, and reviewed false-positive examples. Held-out
labels are used for reporting only, never threshold selection.

### Storage footprint companion for Pareto reporting

Generate the storage companion with the same `dataset_version` and the same
input/output pricing values used by the evaluation config:

```powershell
python -m sscre.storage_evaluation `
  --workload <held-out-aligned-storage-workload>.json `
  --dataset-version reviewed-query-pairs-1.1 `
  --input-cost-per-1k-tokens 0.0 `
  --output-cost-per-1k-tokens 0.0 `
  --output artifacts/evaluation/workstream5-held-out-storage.json
```

Pair this report with the held-out comparison JSON when building the
reuse-versus-storage plane. The storage row is labeled
`synthetic_storage_simulation`; do not treat its measured in-memory footprint
as provider API latency or cost. `total_bytes`, `entries`, and
`eviction_count` are the storage footprint fields, while
`safe_reuse_coverage` is the reuse axis. The values above must match
`experiments/evaluation_config.json` if non-zero pricing is configured.

Build the deterministic Pareto artifact after both inputs exist:

```powershell
python -m sscre.pareto `
  --development-sweep experiments/embedding_development.json `
  --held-out-benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --storage-report artifacts/evaluation/workstream5-held-out-storage.json `
  --output artifacts/evaluation/workstream5-held-out-pareto.json
```
