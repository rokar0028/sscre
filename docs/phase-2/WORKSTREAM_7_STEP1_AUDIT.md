# Workstream 7 — Step 1 audit record

**Completed:** 2026-10-10  
**Scope:** failure gallery outputs, aggregate statistics strata, Workstream 6
stale-exposure blocks, operational redaction, and split-manifest alignment on
checked-in held-out artifacts.  
**Parent plan:** [WORKSTREAM_7_IMPLEMENTATION_PLAN.md](./WORKSTREAM_7_IMPLEMENTATION_PLAN.md)

This audit inventories existing outputs only. It does not freeze the failure-gallery
contract, package consolidated JSON, or regenerate comparison artifacts.

## Evidence reviewed

| Area | Location |
|---|---|
| Comparison gallery assembly | `src/sscre/evaluate.py` (`--baseline all`, `failure_gallery`) |
| Example collection | `src/sscre/baseline.py` (`false_positive_examples`, `failure_examples`, `example_with_labels`) |
| Statistics strata | `src/sscre/evaluation_statistics.py` (via saved `statistics` on comparison JSON) |
| Operational redaction | `src/sscre/serialization.py` (`redact_operational_evaluation_report`) |
| Static HTML export (Phase 1 carryover) | `src/sscre/gallery_export.py`, `tests/test_gallery_export.py` |
| WS6 artifact validation helpers | `src/sscre/freshness_artifacts.py`, `src/sscre/freshness_stale_exposure.py` |
| Trace bounds | [CANDIDATE_TRACE_CONTRACT_v1.md](./CANDIDATE_TRACE_CONTRACT_v1.md) |
| Checked-in WS5 input | `artifacts/evaluation/workstream5-held-out-comparison.json` |
| Checked-in WS6 input | `artifacts/evaluation/workstream6-held-out-freshness.json` |
| Split manifest (current) | `benchmarks/split_manifest.json` |

## Selected evaluation sample scope

Primary scope for Workstream 7 (per parent plan):

- **Split:** `held-out`
- **Dataset:** `reviewed-query-pairs-2.0`
- **Directed requests:** 430 (`215` held-out pair records × `a_to_b` / `b_to_a`)
- **Strategy C threshold:** `0.95` (from `threshold_selection.selected_threshold` on the
  WS5 comparison artifact; development rule recorded in `selection_rule`)
- **Measurement environment:** `synthetic_replay` on both WS5 and WS6 held-out artifacts

The checked-in comparison artifact was produced with `git_commit`
`1beed4de227d00bd3dbbc1b9b57ccaa0f92add02` at `2026-10-08T14:53:27.749628+00:00`.

## Input artifact paths and schema versions

| Artifact | Path | Notable schema / contract fields |
|---|---|---|
| WS5 held-out comparison | `artifacts/evaluation/workstream5-held-out-comparison.json` | `schema_version` `1.0.0`, `statistics_schema_version` `evaluation-statistics-1.0`, `trace_contract_version` `1.0.0`, `safety_contract_version` (present), `baseline` `comparison` |
| WS6 held-out freshness | `artifacts/evaluation/workstream6-held-out-freshness.json` | `schema_version` `1.0.0`, `freshness_evaluation_schema_version` `freshness-evaluation-1.0`, `trace_contract_version` `1.0.0`, `baseline` `freshness-policy-replay` |

WS5 comparison includes `failure_gallery` and `statistics`. It does **not** include
`freshness_policy_companion_artifacts` on the checked-in file (`null` / absent).

WS6 held-out freshness has **no** `failure_gallery` block. Stale-exposure and
protection summaries live under `freshness_experiment` (see §6).

## Split manifest SHA comparison

| Source | `split_manifest_sha256` |
|---|---|
| Current `benchmarks/split_manifest.json` (SHA-256 of file bytes, 2026-10-10) | `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51` |
| WS5 `benchmark_artifact.split_manifest_sha256` | `69c90c4182644dfedd8c9d018a9c452b539bedede22215d768ec382c6ec29e02` |
| WS6 `benchmark_artifact.split_manifest_sha256` | `c0109b36346442858d712ec13c183c8178ebb3e244b082f845cb7426750d8bbd` |

**Result:** all three differ. WS5 and WS6 held-out inputs are not aligned with each
other or with the current split manifest. Step 8 (regenerate or annotate) must run
before cross-artifact consistency claims; WS7 packaging should fail closed or record
`manifest_mismatch` when merging WS5 + WS6.

## Failure gallery sections (WS5 comparison)

Assembly (`evaluate.py`): embedding baseline `false_positive_examples`, compatibility
baseline `failure_examples`, and embedding FPs whose `(id, direction)` are absent
from compatibility `false_positive_examples`.

| Section | Count | Example shape (operational save) |
|---|---:|---|
| `embedding_only_false_positives` | 15 | `id`, `direction`, `similarity`, `reason` (reviewed pair text) |
| `embedding_only_false_positives_caught_by_strategy_c` | 15 | Same four fields as embedding-only list |
| `strategy_c_failures` | 99 | `id`, `direction`, `similarity`, `reason` (runtime aggregate), `predicted_decision`, `expected_reusable`, `expected_compatibility`, `failure_category` (runtime outcome), `evaluation_labels`, `candidate_traces` |

Notes:

- Compatibility held-out **`false_positive_rate` is `0.0`** with **zero**
  `false_positive_examples` on the compatibility baseline payload. All 15 embedding
  FPs appear in both embedding sections because none coincide with a Strategy C
  compatibility false positive.
- Embedding gallery examples are collected only on **`b_to_a`** replay direction in
  `baseline.py` (unsafe reuse / false-positive example path); all 15 gallery rows are
  `b_to_a`.
- `strategy_c_failures` is **`failure_examples`**, not strictly compatibility false
  positives: runtime categories are `false_negative` (84) and `unnecessary_abstention`
  (15).

### Failure counts (held-out comparison artifact)

| Metric | Value | Source |
|---|---:|---|
| Embedding-only false positives (Strategy B unsafe reuse) | 15 | `baselines.embedding-cache.unsafe_reuse_hits`, gallery sections |
| Strategy C compatibility false positives | 0 | `baselines.compatibility-cache.false_positive_rate`, `false_positive_examples` |
| Strategy C failure gallery rows | 99 | `failure_gallery.strategy_c_failures` |
| Embedding false positive rate (Strategy B) | ~0.357 | `baselines.embedding-cache.false_positive_rate` |

## Category and reason completeness (false positives)

Workstream 7 requires every false positive in the **selected sample** to carry a
reviewed or runtime failure category, or an explicit documented exclusion in the
consolidated artifact (later steps).

| Gallery cohort | `failure_category` on example | Reviewed `reason` on example | Audit result |
|---|---|---|---|
| Embedding-only FPs (15) | **Absent** on all 15 | **Present** on all 15 (benchmark pair `reason`) | Category gap for WS7 completeness; reviewed reason available for enrichment |
| Embedding FPs caught by Strategy C (15) | **Absent** on all 15 | **Present** on all 15 | Same as embedding-only list (identical keys when Strategy C FP set is empty) |
| Strategy C compatibility FPs | N/A (count 0) | N/A | No compatibility FP rows in held-out artifact |
| Strategy C failure gallery (99) | **Present** on all 99 | **Present** (runtime resolver text, e.g. `all candidates were incompatible`) | Runtime `failure_category` populated via compatibility replay |

Aggregate reviewed failure-category strata exist on the compatibility baseline
statistics block (`statistics.by_baseline.compatibility-cache.strata.by_failure_category`)
with bootstrap metadata and `sample_count` per category (e.g. `false_negative` 84,
`unnecessary_abstention` 15, `intent_mismatch` 55). These strata describe benchmark
labels on the replay sample, not the 15 embedding-only FP rows.

Freshness-class strata are also present:
`statistics.by_baseline.compatibility-cache.strata.by_freshness_class` →
`dynamic`, `semi_dynamic`, `stable`.

## `candidate_traces` vs trace contract

On **strategy_c_failures** examples that include traces (99 rows), each trace object
carries exactly these keys (495 traces total across the gallery):

`candidate_query_hash`, `similarity`, `decision`, `reason`, `candidate_order`,
`stage`, `query_metadata`, `candidate_metadata`, `freshness_class`,
`cache_control_outcome`.

This matches required and optional fields in
[CANDIDATE_TRACE_CONTRACT_v1.md](./CANDIDATE_TRACE_CONTRACT_v1.md). No extra trace
keys were observed. Embedding-only gallery rows **omit** `candidate_traces` (Strategy B
path does not attach traces to saved FP examples).

## Operational redaction behavior

`redact_operational_evaluation_report()` (`serialization.py`):

- Strips `query_a` and `query_b` from lists keyed as failure examples and from each
  `failure_gallery` section.
- Recursively redacts nested `baselines.*.false_positive_examples` /
  `failure_examples`.
- Validates forbidden keys under `statistics`, `freshness_experiment`, and
  `request_samples` via `_FORBIDDEN_LOG_KEYS` (includes `query_a`, `query_b`,
  `query_text`, `prompt`, `answer`, credentials, etc.).

**Checked-in WS5 artifact:** scan of `failure_gallery` found **no**
`query_a`, `query_b`, or `query_text` keys.

**Tests (2026-10-10):** `python -m pytest -q tests/test_gallery_export.py` — pass.

## Workstream 6 stale-exposure and protection (companion source)

Checked-in `artifacts/evaluation/workstream6-held-out-freshness.json`
(`git_commit` `88997ed1d7463c90fb57a2beee39b2b0a78f4b7c`):

| Block | Location | Purpose for WS7 companion |
|---|---|---|
| `stale_exposure_accounting` | `freshness_experiment.stale_exposure_accounting` | Served vs protection numerators/denominators, rates, intervals |
| `protection_counts` | under stale exposure accounting | e.g. `dynamic_reuse_blocked_count` 8, zero expired/missing/invalid expiration on held-out |
| `stale_exposure_accounting_by_policy` | `freshness_experiment.stale_exposure_accounting_by_policy` | Per-policy copies (e.g. `conservative`) |
| `held_out_freshness_scope` | `freshness_experiment.held_out_freshness_scope` | Documents `semi_dynamic` / `dynamic` **unavailable** on held-out; `stable` evaluated |

There is **no** `failure_gallery` section in WS6 artifacts. WS7 must attach freshness
failure summaries by reference / bounded copy (Steps 5–6), not replay freshness.

## Gaps for Steps 2+

- [ ] No `FAILURE_GALLERY_CONTRACT_v1.md` or `failure-gallery-1.0` schema version.
- [ ] No consolidated `workstream7-quality-analysis.json`.
- [ ] Embedding-only FP rows lack runtime `failure_category`; WS7 must map reviewed
  benchmark categories or emit explicit `category_unavailable` rules in the contract.
- [ ] WS5 / WS6 / current manifest SHA mismatch — regenerate comparison (Step 8) or
  flag limitations before merge.
- [ ] `gallery_export` consumes WS5 comparison only; no WS6 freshness section in HTML.
- [ ] No automated false-positive category completeness test for held-out comparison
  (Step 10).
- [ ] `mitigation` / `open_limitation` not present on gallery examples.

## Handoff

Step 2 should freeze section names, example required keys, aggregate table shapes,
and freshness companion attachment using this inventory as the baseline.
