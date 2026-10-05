# Milestone 6 Implementation Plan — Evaluation Baseline

## Goal

Create a reproducible evaluation harness that compares SSCRE against simple
baselines before semantic retrieval is introduced:

```text
versioned benchmark JSONL
        ↓
no-cache baseline + exact-cache baseline
        ↓
hit rate, reuse coverage, tokens, cost, latency
        ↓
machine-readable report
```

This milestone measures whether exact caching provides useful savings. It does
not implement embeddings, semantic similarity, or compatibility-aware reuse.

## Learning objectives

- [ ] JSONL dataset design
- [ ] Benchmark labels and ground truth
- [ ] Train/development and held-out evaluation splits
- [ ] Baseline experiment design
- [ ] Hit rate versus safe reuse coverage
- [ ] Token and cost accounting
- [ ] Reproducible configuration
- [ ] Machine-readable experiment reports
- [ ] Avoiding benchmark leakage

## Implementation steps

### 1. Define the benchmark format

- [x] Create a versioned JSONL schema.
- [x] Define a stable record identifier.
- [x] Store the query text and query pair information.
- [x] Store reusable and non-reusable labels.
- [x] Store correctness and compatibility labels separately.
- [x] Validate every benchmark record before evaluation.

Example record:

```json
{
  "id": "pair-0001",
  "query_a": "Give me Python code for binary search.",
  "query_b": "Give me Java code for binary search.",
  "reusable": false,
  "reason": "programming language constraint differs"
}
```

### 2. Create the reviewed dataset

- [x] Create at least 20 manually reviewed query pairs.
- [x] Include exact duplicates.
- [x] Include whitespace-equivalent queries.
- [x] Include semantically similar but incompatible queries.
- [x] Include different languages, formats, entities, and constraints.
- [x] Record a short reason for every non-reusable label.
- [x] Review labels before running the baselines.

### 3. Define evaluation splits

- [x] Create a development split for configuration decisions.
- [x] Create a held-out test split for final reporting.
- [x] Keep test labels unavailable to threshold selection.
- [x] Require the selected split to be declared explicitly at evaluation time.
- [x] Ensure both query directions are evaluated where applicable.
- [x] Record the dataset version in every experiment report.

### 4. Implement the no-cache baseline

- [x] Replay every benchmark query without cache lookup.
- [x] Count every request as generated.
- [x] Estimate input and output tokens consistently.
- [x] Calculate baseline latency and cost.
- [x] Save the baseline results.

### 5. Implement the exact-cache baseline

- [x] Replay the same workload with exact caching enabled.
- [x] Use the normalized query hash for lookup.
- [x] Count generated requests and cache hits.
- [x] Calculate hit rate.
- [x] Calculate safe reuse coverage.
- [x] Calculate tokens saved.
- [x] Calculate total cost including cache and preprocessing overhead.
- [x] Record cache misses and failure categories.

### 6. Add the evaluation command

- [x] Add an `evaluate` command or module entry point.
- [x] Accept a benchmark path.
- [x] Accept a configuration path.
- [x] Accept the baseline name.
- [x] Accept an output report path.
- [x] Validate the declared split against `split_manifest.json` and reviewed IDs.
- [x] Return a non-zero status for invalid input or failed evaluation.

### 7. Save reproducible reports

- [x] Save results as JSON.
- [x] Include dataset and configuration versions.
- [x] Include baseline name and execution timestamp.
- [x] Include request counts and hit/miss counts.
- [x] Include token, cost, and latency metrics.
- [x] Use a common report schema for no-cache and exact-cache outputs.
- [x] Include the software version or commit identifier when available.
- [x] Record whether the Git worktree was dirty when the report was generated.
- [x] Make repeated runs with the same configuration comparable.

### 8. Document limitations

- [x] Document how labels were created.
- [x] Document how token counts are estimated.
- [x] Document cost assumptions.
- [x] Document why development and held-out data are separated.
- [x] Document what exact caching cannot measure about semantic reuse.
- [x] Document that configured zero costs are placeholders, not production pricing.

## Verification checklist

- [x] The benchmark JSONL validates successfully.
- [x] Invalid records are rejected with useful errors.
- [x] At least 20 reviewed query pairs exist.
- [x] Development and held-out splits are distinct.
- [x] Split manifests and reviewed-record IDs are validated before evaluation.
- [x] The no-cache baseline produces a report.
- [x] The exact-cache baseline produces a report.
- [x] Hit rate and reuse coverage are reported.
- [x] Tokens saved and total cost are reported.
- [x] Latency metrics are reported.
- [x] Reports are valid machine-readable JSON.
- [x] Repeated runs use the same configuration and dataset versions.
- [x] Milestone 6 tests pass (`.venv\Scripts\python.exe -m pytest -q tests/test_benchmark.py`; 14 passed).
- [x] Full suite passes (`.venv\Scripts\python.exe -m pytest -q`; 65 passed, 8 skipped).
- [ ] No linter errors are reported (no linter is currently configured).

## Completion criteria

Milestone 6 is complete when the project can replay a reviewed benchmark using
both no-cache and exact-cache strategies, produce comparable JSON reports, and
show the measured cost, token, latency, and reuse trade-offs without leaking
held-out evaluation data into configuration decisions.
