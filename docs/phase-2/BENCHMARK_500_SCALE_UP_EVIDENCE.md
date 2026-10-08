# Benchmark 500+ scale-up evidence

Workstream: [BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md](./BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md)

## Phase 1 — CacheEval obtain and filter (2026-10-08)

### Upstream review

| Document | Location | Notes |
| --- | --- | --- |
| LICENSE | [CacheEval/LICENSE](https://github.com/BudEcosystem/CacheEval/blob/cd3ff21fc2ea41957730ecc128c3e5cd3e4286a1/LICENSE) | CC BY-SA 4.0 (ShareAlike via PAWS-X lineage) |
| ATTRIBUTION.md | [CacheEval/ATTRIBUTION.md](https://github.com/BudEcosystem/CacheEval/blob/cd3ff21fc2ea41957730ecc128c3e5cd3e4286a1/ATTRIBUTION.md) | QQP (~80 cited) and xLAM-NC (~30 cited) flagged for commercial removal |
| SCHEMA.md | [CacheEval/SCHEMA.md](https://github.com/BudEcosystem/CacheEval/blob/cd3ff21fc2ea41957730ecc128c3e5cd3e4286a1/SCHEMA.md) | 2,000-row JSONL schema; labels `EQUIV`, `PARA_SAFE`, `RELATED_UNSAFE`, `ADVERSARIAL`, `UNRELATED` |

**Upstream revision used:** `cd3ff21fc2ea41957730ecc128c3e5cd3e4286a1` (shallow clone of `main`).

Obtain locally (do not commit unfiltered `cachebench.jsonl`):

```powershell
git clone --depth 1 https://github.com/BudEcosystem/CacheEval.git $env:TEMP\CacheEval
```

### Commercial filter

Policy: [BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md](./BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md)

Tool: [benchmarks/candidates/tools/filter_cacheeval_commercial.py](../../benchmarks/candidates/tools/filter_cacheeval_commercial.py)

Rules (`cacheeval_commercial_v1`):

- Exclude when `source` matches Quora / QQP (restrictive ToS).
- Exclude when `source` matches `xLAM-irrelevance` (CC BY-NC 4.0).

```powershell
python benchmarks/candidates/tools/filter_cacheeval_commercial.py `
  --input $env:TEMP\CacheEval\cachebench.jsonl `
  --output benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl `
  --audit benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json `
  --upstream-revision cd3ff21fc2ea41957730ecc128c3e5cd3e4286a1
```

### Filter audit (committed manifest)

Canonical counts and excluded IDs:
[benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json](../../benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json)

| Metric | Value |
| --- | --- |
| Input rows | 2000 |
| Retained rows | **1945** |
| Excluded rows | **55** |
| Excluded: Quora QQP (`source`) | 20 |
| Excluded: xLAM-NC (`source`) | 35 |
| Filtered output SHA-256 | `9a05755d5382d15b087382743c3b7cf27f12cbda6188b88f6855bfa51dcd6d61` |

The filtered JSONL is **gitignored**; regenerate with the command above.

**QQP vs attribution (pinned `cd3ff21`):** CacheEval `ATTRIBUTION.md` cites ~80
QQP-derived rows at a methodology level; this revision excludes **20** rows with an
explicit Quora QQP `source` tag. A full-row scan found no other `quora` / `qqp`
strings in retained JSON. On any **new upstream pin**, repeat filter + compare excluded
QQP count to attribution and re-scan retained rows (see policy
[Upstream pin and QQP re-audit](./BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md#upstream-pin-and-qqp-re-audit)).

### Verification (Phase 1)

- [x] Upstream LICENSE / ATTRIBUTION / SCHEMA reviewed (table above).
- [x] Unfiltered blob not committed (`.gitignore` + [upstream README](../../benchmarks/candidates/upstream/README.md)).
- [x] Filtered export built locally; audit manifest committed.
- [x] `python -m pytest -q tests/test_cacheeval_filter.py` → 4 passed (2026-10-08).

## Phase 2 — Convert to SSCRE candidates (2026-10-08)

Tool: [convert_cacheeval_candidates.py](../../benchmarks/candidates/tools/convert_cacheeval_candidates.py)

| Setting | Value |
| --- | --- |
| Input | `cacheeval_v1_filtered.jsonl` (1945 rows) |
| Domains | `qa_factual`, `qa_open`, `conversational`, `math`, `code` |
| Sample limit | 575 (stratified by CacheEval label, seed `20261008`) |
| Output | [cacheeval_batch_01.jsonl](../../benchmarks/candidates/cacheeval_batch_01.jsonl) |
| SSCRE IDs | `pair-0033` – `pair-0607` |
| `source_group` | `cacheeval_v1:filtered` |
| `review_status` | `draft` (all rows) |

Selection skips: 895 rows outside domain filter, 1 pair key already in baseline,
3 within-batch duplicate keys.

Coverage category counts (provisional mapping): paraphrase 115, low_overlap_compatible
115, high_similarity_incompatible 115, intent_change 134, constraint_change 84,
entity_change 12. Reusable true: 230 / false: 345.

```powershell
python benchmarks/candidates/tools/convert_cacheeval_candidates.py
python -m sscre.benchmark_build --benchmark-dir benchmarks validate-candidates --candidates benchmarks/candidates/cacheeval_batch_01.jsonl
```

### Verification (Phase 2)

- [x] Converter implements schema `1.1`, draft review, redaction checks, inventory `source_group`.
- [x] `validate-candidates` passed on `cacheeval_batch_01.jsonl`.
- [x] `python -m pytest -q tests/test_cacheeval_convert.py tests/test_cacheeval_filter.py` → 7 passed (2026-10-08).

## Phase 3 — Human review (complete, 2026-10-08)

Tool: [apply_phase3_cacheeval_review.py](../../benchmarks/candidates/tools/apply_phase3_cacheeval_review.py)
→ [cacheeval_batch_01_reviewed.jsonl](../../benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl)

| Batches | ID range | Cumulative finals | Draft left |
| --- | --- | --- | --- |
| 1–11 | `0033`–`0562` | 538 | — |
| 12 | `0563`–`0607` | **583** (all rows) | **0** |

Batch 12 overrides (11 rows): `pair-0566`/`pair-0586`/`pair-0601`/`pair-0606`
→ uncertain (`insufficient_evidence`, identical multi-turn surface forms);
`pair-0571` → `constraint_change`; `pair-0578`/`pair-0581`/`pair-0591` →
`intent_change`; `pair-0596` → `entity_change`; `pair-0599` → banking intent
split; `pair-0602` → compatible `paraphrase` (`a week` vs `per week`).

```powershell
python benchmarks/candidates/tools/apply_phase3_cacheeval_review.py --batch 12 --force
python -m sscre.benchmark_build --benchmark-dir benchmarks validate-candidates --candidates benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl
```

`validate-candidates` passed after batch 12 `--force` (2026-10-08).

Batch 2 overrides (examples): `pair-0066`/`pair-0096` uncertain (identical
multi-turn surface forms); ORM/React runtime `constraint_change`; `pair-0088`
`entity_change` (account vs card).

Batch 1 label overrides: `pair-0036` → uncertain (`insufficient_evidence`);
`pair-0038` → `constraint_change`; several `low_overlap_compatible` → `paraphrase`.

```powershell
python benchmarks/candidates/tools/apply_phase3_cacheeval_review.py --batch 2 `
  --input benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl `
  --output benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl
python -m sscre.benchmark_build --benchmark-dir benchmarks validate-candidates --candidates benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl
```

`validate-candidates` passed after batch 2 (2026-10-08).

### Phase 3 gate progress (project-wide)

| Target | Status |
| --- | --- |
| ≥500 `review_status: final` | **583** / 500 |
| ≥20% reusable / non-reusable | 226 reusable / 357 non-reusable (~39% / ~61%) |
| Paraphrase ≤35% | 146 / 583 ≈ **25.0%** |
| 14 coverage categories | **14/14** among all finals |
| Freshness mix | stable 578, semi_dynamic 3, dynamic 2 |
| `validate-candidates` (reviewed file) | passed (2026-10-08, post batch 12) |

## Phase 4 — Merge, split, and freeze (2026-10-08)

Split assignment: [assign_phase4_cacheeval_splits.py](../../benchmarks/candidates/tools/assign_phase4_cacheeval_splits.py)

| Setting | Value |
| --- | --- |
| `dataset_version` | `reviewed-query-pairs-2.0` |
| Split seed | `20261008` |
| New → development / held-out | **379** / **204** (baseline **21** / **11** unchanged) |
| Source / development / held-out | **615** / **400** / **215** |
| Merge input | `cacheeval_batch_01_reviewed.jsonl` (583 rows) |
| `source_group` | Per-row `hand_reviewed_v2:cacheeval_batch01:{id}` (leakage-safe) |
| High-impact finals | `annotator_count: 2` on 30 uncertain/ambiguity/stale rows |

```powershell
python benchmarks/candidates/tools/assign_phase4_cacheeval_splits.py
python -m sscre.benchmark_build --benchmark-dir benchmarks merge `
  --candidates benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl --rebuild-splits
python -m sscre.benchmark_validate --benchmark-dir benchmarks --production
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
```

### Verification (Phase 4)

- [x] Both validate commands passed (2026-10-08).
- [x] `leakage_validation.status`: **passed** (`cross_split_fingerprint_overlaps=0`).
- [x] `python -m pytest -q tests/test_benchmark.py` → **54 passed** (2026-10-08).
- [x] Category counts (source): paraphrase 150 / 615 ≈ 24.4%; 14/14 categories present.

Held-out coverage (215 rows): all 14 categories represented; 84 reusable (~39%).

## Phase 5 — Downstream artifacts (2026-10-08)

Regenerated on `reviewed-query-pairs-2.0` after Phase 4 freeze. Full detail:
[WORKSTREAM_5_EVIDENCE.md](./WORKSTREAM_5_EVIDENCE.md).

| Artifact | Path |
| --- | --- |
| Development sweep | `artifacts/evaluation/workstream5-development-sweep.json` |
| Held-out comparison | `artifacts/evaluation/workstream5-held-out-comparison.json` |
| Held-out Pareto | `artifacts/evaluation/workstream5-held-out-pareto.json` |
| WS3 development replay | `artifacts/evaluation/workstream3-development.json` |

- [x] Selected threshold **0.95** (development-only selection).
- [x] Development sweep `constraint_satisfied`: **false** at FPR cap 0.0.
- [x] Held-out Strategy C constraint at selected threshold: **satisfied** (Pareto).
- [x] Storage Pareto plane: **deferred** (no 2.0 storage report).
- [x] `python -m pytest -q tests/test_benchmark.py` → 54 passed (2026-10-08).
- [x] `python -m pytest -q` → **603 passed**, **14 skipped** (2026-10-08).
- [x] `python -m pytest -q tests/test_pareto.py tests/test_workstream4_regression.py`
  → 10 passed (2026-10-08).
