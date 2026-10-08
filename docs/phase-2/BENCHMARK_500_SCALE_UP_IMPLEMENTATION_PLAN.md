# Benchmark 500+ scale-up implementation plan

## Goal

Expand the reviewed benchmark from the current **32-pair** working artifact
(`reviewed-query-pairs-1.1`) to **≥500 human-reviewed pairs** that pass Phase 2
validation, with disjoint development and held-out splits and no cross-split
leakage. This unblocks final Phase 2 statistical claims and held-out Workstream
5 artifacts.

This plan is **data and review work**, not application code. Use existing
tooling in `sscre.benchmark_build`, `sscre.benchmark_validate`, and
`sscre.benchmark_splits`.

## Status

**Phase 5 complete** (2026-10-08). The benchmark manifest was re-frozen after
the scale-up repair, and Workstream 5 artifacts were regenerated on
`reviewed-query-pairs-2.0` (615 pairs). Real-provider and held-out storage Pareto
companion remain deferred per WS5 evidence.

**Evidence:** [BENCHMARK_500_SCALE_UP_EVIDENCE.md](./BENCHMARK_500_SCALE_UP_EVIDENCE.md)

**Parent:** [WORKSTREAM_2_IMPLEMENTATION_PLAN.md](./WORKSTREAM_2_IMPLEMENTATION_PLAN.md)  
**Phase 2 gate:** [PHASE_2_IMPLEMENTATION_PLAN.md](./PHASE_2_IMPLEMENTATION_PLAN.md) (≥500 pairs)  
**Annotation rules:** [benchmarks/ANNOTATION_GUIDE_v1.md](../../benchmarks/ANNOTATION_GUIDE_v1.md)  
**Candidate staging:** [benchmarks/candidates/README.md](../../benchmarks/candidates/README.md)

## Learning objectives

- [ ] Explain why imported “duplicate” or “paraphrase” labels are not the same
  as SSCRE `compatible` / `reusable` without human review.
- [ ] Trace a candidate row from external source → JSONL → merge → split →
  `benchmark_validate --phase2`.
- [ ] List which upstream licenses allow redistribution in this repository and
  which rows must be filtered.

## Recommended external sources (research summary)

| Priority | Source | Size | Fit | License notes |
| --- | --- | --- | --- | --- |
| 1 | [BudEcosystem/CacheEval](https://github.com/BudEcosystem/CacheEval) (`cachebench.jsonl`) | ~2,000 pairs | **Best:** cache HIT/MISS / safety-oriented labels | CC BY-SA 4.0; filter QQP / NC-tagged rows for commercial use per repo `ATTRIBUTION.md` |
| 2 | [redis/langcache-sentencepairs-v3](https://huggingface.co/datasets/redis/langcache-sentencepairs-v3) | Large pool | Paraphrase / hard negatives | Apache-2.0 |
| 3 | [redis/llm-paraphrases](https://huggingface.co/datasets/redis/llm-paraphrases) | Synthetic pairs | Semantic-cache paraphrase training/eval | Apache-2.0 |
| 4 | [google-research-datasets/paws](https://huggingface.co/datasets/google-research-datasets/paws) | Human labels | High-similarity non-paraphrase | Per subset; PAWS-Wiki usable; PAWS-QQP rebuild only |
| 5 | [PolyAI/banking77](https://huggingface.co/datasets/PolyAI/banking77) | 13k queries | Intent/domain pair **candidates** (not pairs) | CC BY 4.0 |
| 6 | [clinc/clinc_oos](https://huggingface.co/datasets/clinc/clinc_oos) | Multi-domain intents | Intent / OOS **candidates** | CC BY 3.0 |

**Do not** treat NLI corpora (SNLI/MNLI/ANLI) as direct `reusable` labels; use
only as inspiration for pair authoring after review.

## Label mapping (CacheEval → schema 1.1)

Map only after reading each row’s fields in CacheEval `SCHEMA.md`. Treat this
table as a **starting point**; every row still needs human review.

| CacheEval-style label (conceptual) | Starting `compatibility_label` | Starting `reusable` | Typical `coverage_category` |
| --- | --- | --- | --- |
| Equivalent / safe paraphrase | `compatible` | `true` | `exact_duplicate`, `whitespace_variant`, `paraphrase`, or `low_overlap_compatible` |
| Related but unsafe | `incompatible` | `false` | `high_similarity_incompatible`, `constraint_change`, `entity_change`, … |
| Adversarial near-duplicate | `incompatible` | `false` | `high_similarity_incompatible` |
| Unrelated | `incompatible` | `false` | `intent_change` or `domain_change` |
| Ambiguous / insufficient evidence | `uncertain` | `false` | `insufficient_evidence` or `ambiguity` |

Set `review_status: final` only after a human agrees with the mapped labels.
Set `annotation_source` and `source_group` to a registered family in
[benchmarks/source_inventory.json](../../benchmarks/source_inventory.json).

## Phase 0 — Governance and inventory

- [x] Record a **license decision** in project docs (commercial vs research-only;
  which upstream rows are excluded).
  - [BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md](./BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md)
- [x] Add approved source families to `benchmarks/source_inventory.json`, for
  example:
  - `cacheeval_v1:filtered` (CC BY-SA 4.0, attribution documented)
  - `redis_paraphrase_v1` (Apache-2.0)
  - `hand_reviewed_v2` (project-owned edits of imported candidates)
- [x] Bump `dataset_version` when merged labels or pair set changes (e.g.
  `reviewed-query-pairs-2.0`); do not silently grow `1.1` without a version bump.
  - Applied consistently in the source dataset, split manifest, and evaluation
    configuration.
- [x] Update [benchmarks/README.md](../../benchmarks/README.md) data-policy section
  when new families are approved.

## Phase 1 — Obtain and filter CacheEval

- [x] Clone or download [BudEcosystem/CacheEval](https://github.com/BudEcosystem/CacheEval)
  and read `LICENSE`, `ATTRIBUTION.md`, and `SCHEMA.md`.
- [x] Copy or reference `cachebench.jsonl` locally (do not commit restricted
  upstream blobs without license approval).
  - Clone instructions: [benchmarks/candidates/upstream/README.md](../../benchmarks/candidates/upstream/README.md)
- [x] Build a **filtered export** that removes rows flagged for restrictive
  upstream sources (QQP, NC-tagged, etc.) if your deployment requires it.
  - [filter_cacheeval_commercial.py](../../benchmarks/candidates/tools/filter_cacheeval_commercial.py)
  - 1945 retained / 55 excluded at upstream `cd3ff21`
- [x] Record filter counts and retained row count in a short audit note
  (suggested path: `docs/phase-2/BENCHMARK_500_SCALE_UP_EVIDENCE.md`, create
  when work starts).
  - [cacheeval_v1_filter_audit.json](../../benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json)

## Phase 2 — Convert to SSCRE candidate JSONL

- [x] Implement a one-off converter script or notebook (suggested location:
  `scripts/convert_cacheeval_candidates.py` or `benchmarks/candidates/tools/`)
  that outputs schema `1.1` JSONL under `benchmarks/candidates/`.
  - [convert_cacheeval_candidates.py](../../benchmarks/candidates/tools/convert_cacheeval_candidates.py)
- [x] Converter requirements:
  - [x] Stable new IDs (`pair-XXXX` pattern, no collisions with existing 32).
  - [x] `schema_version: "1.1"`, `directionality`, `freshness_class`, metadata
    bounds per `BenchmarkRecord`.
  - [x] Provisional labels marked `review_status: draft` until reviewed.
  - [x] `source_group` matching `source_inventory.json`.
  - [x] Run `validate_redaction` logic (no credentials, keys, or banned tokens).
- [x] Validate candidates before review:

```powershell
python -m sscre.benchmark_build --benchmark-dir benchmarks validate-candidates --candidates benchmarks/candidates/cacheeval_batch_01.jsonl
```

- [x] Target **550–600** candidate rows to absorb dedupe, validation failures,
  and split/leakage rejects.
  - [cacheeval_batch_01.jsonl](../../benchmarks/candidates/cacheeval_batch_01.jsonl): **575** rows (`pair-0033`–`pair-0607`)

## Phase 3 — Human review (largest effort)

Review in batches of **25–50** pairs using
[ANNOTATION_GUIDE_v1.md](../../benchmarks/ANNOTATION_GUIDE_v1.md).

Review tool: [apply_phase3_cacheeval_review.py](../../benchmarks/candidates/tools/apply_phase3_cacheeval_review.py)
→ [cacheeval_batch_01_reviewed.jsonl](../../benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl)
(batches 1–12: `pair-0033`–`pair-0607` + 8 gap-fill rows; see evidence file).

Per batch:

- [x] Confirm `compatible` / `incompatible` / `uncertain` and `reusable`.
  - Batches 1–12 complete; see evidence file.
- [x] Set exactly one `coverage_category` and appropriate `failure_category`.
  - Batch 12: 11 explicit overrides in `BATCH12_OVERRIDES`; remaining rows keep
    validated converter mapping.
- [x] Set `review_status: final` only when confident.
  - **583** / **583** rows `final` (2026-10-08).
- [x] Flag disputed rows with `review_status: disputed` and adjudication notes.
  - None flagged (`disputed`: 0).
- [x] Keep correctness / preference null unless answers were reviewed
  (`answer_availability: none` remains valid for compatibility-only benchmark).

Coverage targets (Phase 2 policy in `sscre.benchmark_coverage`):

- [x] At least **500** total final records.
  - **583** finals on `cacheeval_batch_01_reviewed.jsonl`.
- [x] At least **20%** reusable and **20%** non-reusable (positive/negative balance).
  - 226 reusable (~39%) / 357 non-reusable (~61%).
- [x] Paraphrase fraction **≤ 35%** of all records.
  - 146 / 583 ≈ **25.0%**.
- [x] At least one record each in every required `coverage_category` (14 categories).
- [x] Freshness: include `stable`, `semi_dynamic`, and `dynamic` examples.
  - stable 578, semi_dynamic 3, dynamic 2.

Suggested review order:

1. [x] CacheEval-derived batches (bulk compatible / unsafe / adversarial).
2. [x] Hand-authored gaps (freshness, stale_answer, whitespace, constraint).
  - Batch 1 gap-fill (8 rows) in reviewed file.
3. [ ] Optional Redis/PAWS supplements for hard negatives only where CacheEval
  is thin.
  - **Deferred:** coverage gates met without supplement.

## Phase 4 — Merge, split, and freeze

- [x] Assign every new ID to **development** or **held_out_test** in
  `benchmarks/split_manifest.json` **before** merge (no unassigned IDs).
  - [assign_phase4_cacheeval_splits.py](../../benchmarks/candidates/tools/assign_phase4_cacheeval_splits.py),
    seed **20261008**, per-row `source_group` for leakage policy.
- [x] Suggested split: **~400 development / ~100 held-out** (adjust while keeping
  category balance on held-out).
  - **400** / **215** development / held-out (615 source rows).
- [x] Merge reviewed candidates:

```powershell
python -m sscre.benchmark_build --benchmark-dir benchmarks merge --candidates benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl --rebuild-splits
```

- [x] Or merge then freeze explicitly:

```powershell
python -m sscre.benchmark_build --benchmark-dir benchmarks merge --candidates benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl
python -m sscre.benchmark_build --benchmark-dir benchmarks freeze-splits
```

- [x] Run validation (working baseline, then Phase 2 gate):

```powershell
python -m sscre.benchmark_validate --benchmark-dir benchmarks --production
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
```

- [x] Fix leakage, duplicate pair keys, manifest drift, or coverage failures until
  both commands pass.
  - Set `annotator_count: 2` on high-impact finals before freeze; see evidence.

## Phase 5 — Downstream artifacts (after scale gate)

Only after `--phase2` passes:

- [x] Regenerate Workstream 5 development sweep and held-out comparison
  ([WORKSTREAM_5_IMPLEMENTATION_PLAN.md](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md)).
  - Artifacts under `artifacts/evaluation/workstream5-*.json` (2026-10-08).
- [ ] Regenerate Pareto artifact with held-out-aligned storage companion when
  storage simulation exists.
  - **Deferred:** no `reviewed-query-pairs-2.0` storage report; Pareto regenerated
    without `--storage-report` (`storage_measurement_environment`: unavailable).
- [x] Update [WORKSTREAM_5_EVIDENCE.md](./WORKSTREAM_5_EVIDENCE.md) from **interim**
  to **final** where claims are supported.
  - Final for scale + synthetic held-out; real-provider still open.
- [x] Update [PHASE_2_IMPLEMENTATION_PLAN.md](./PHASE_2_IMPLEMENTATION_PLAN.md)
  benchmark acceptance checkboxes with command evidence.

## Verification checklist (evidence file)

When closing this workstream slice, record:

- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production`
- [x] Record counts: source, development, held-out.
  - **615** / **400** / **215** (2026-10-08).
- [x] `split_manifest.json` `frozen_at` and SHA-256 fields updated.
  - `frozen_at=2026-10-08T15:28:12+00:00` (re-freeze after manifest repair).
- [x] Category counts and balance from validator output.
  - See [BENCHMARK_500_SCALE_UP_EVIDENCE.md](./BENCHMARK_500_SCALE_UP_EVIDENCE.md) Phase 4.
- [x] License / attribution summary and filtered row counts.
  - CacheEval: CC BY-SA 4.0; 2,000 input, 1,945 retained, 55 excluded
    (20 QQP and 35 xLAM-NC); see the filter audit and policy document.
- [x] `python -m pytest -q tests/test_benchmark.py` after tooling changes.
  - 54 passed (2026-10-08).
- [x] Full suite: `python -m pytest -q` → **603 passed**, **14 skipped**
  (2026-10-08).

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Treating import labels as ground truth | Mandatory human review; `review_status: draft` until final |
| License contamination (QQP, NC) | Filter + document; register families in `source_inventory.json` |
| Split leakage | Use `validate_cross_split_leakage`; never tune on held-out |
| Paraphrase-heavy dataset | Monitor `max_paraphrase_fraction`; add incompatible diversity |
| Scope creep (answers, providers) | Stay compatibility-only unless Workstream 2 schema extended |

## Acceptance criteria

- [x] `reviewed_query_pairs.jsonl` contains **≥500** records with
  `review_status: final` when `--production` is used.
  - **615** finals (2026-10-08).
- [x] `benchmark_validate --phase2 --production` passes.
- [x] Development and held-out splits are disjoint, cover all source IDs, and
  manifest checksums match files.
- [x] Approved source families and license notes are documented.
  - [BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md](./BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md)
- [x] Phase 2 parent plan benchmark gate can be marked complete with linked
  evidence.

## Execution sequence (summary)

```text
License decision → CacheEval filter → convert to candidates/ → human review batches
→ assign split IDs → merge + freeze-splits → validate (--production, --phase2)
→ regenerate WS5 artifacts → update evidence docs
```

Estimated effort (solo, beginner-friendly pacing): **multiple sessions** —
review dominates; conversion and validation are automatable.
