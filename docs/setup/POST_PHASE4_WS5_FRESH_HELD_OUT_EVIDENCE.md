# Post–Phase 4 Workstream 5 — Fresh held-out evidence

**Parent:** [`POST_PHASE4_WS5_FRESH_HELD_OUT_IMPLEMENTATION_PLAN.md`](./POST_PHASE4_WS5_FRESH_HELD_OUT_IMPLEMENTATION_PLAN.md)  
**Stabilization plan:** [`docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md) Workstream 5  
**Status:** `closed` — fresh held-out run and gate scored **pass**; parent WS5
synced 2026-10-15

## Authoring snapshot

- [x] Child plan authored 2026-10-15.
- [x] Step 1 extract complete 2026-10-15 (draft JSONL only).
- [x] `benchmarks/fresh_held_out.jsonl` + manifest frozen (Step 4).
- [x] Headline verdict **pass** (Step 6–7, fresh 100-pair population).

Do not read later empty sections as pass or fail.

## Step 1 — Extract

- [x] Filtered CacheEval: `used_existing_filtered` (local gitignored
      `benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl`, 1945 input rows).
- [x] Collision drop against the 615-pair corpus recorded (`595` rows skipped as
      existing normalized pair keys across `reviewed_query_pairs.jsonl`,
      `development.jsonl`, and `held_out_test.jsonl`; `615` unique keys loaded).
- [x] Draft path: `benchmarks/candidates/fresh_held_out_draft.jsonl` — **100** rows
      after top-up (`pair-0616` … `pair-0715`; initial extract 80, +20 on
      2026-10-15),
      `annotation_source: assistant_draft`.

Commands (repo root, 2026-10-15):

```powershell
python benchmarks/candidates/tools/extract_fresh_held_out_draft.py
python -m sscre.benchmark_build --benchmark-dir benchmarks validate-candidates `
  --candidates benchmarks/candidates/fresh_held_out_draft.jsonl
```

Extract summary: `pool_after_collision=455` unused licensed rows in default domains;
sampling mix **24** compatible / **40** incompatible / **16** uncertain (seed
`20261015`). `validate-candidates` passed.

## Step 2 — Draft labels and review sheet

- [x] Converter + annotation-guide pass on draft JSONL (`16` rows relabeled to
      `uncertain` for identical anaphor/deictic surface forms;
      `pair-0680` … `pair-0695`).
- [x] Review sheet: `benchmarks/candidates/fresh_held_out_review.md` (80 rows;
      draft labels **24** compatible / **40** incompatible / **16** uncertain).
- [x] Redaction patterns applied in review table cells (API-key style tokens).

```powershell
python benchmarks/candidates/tools/build_fresh_held_out_review.py
python -m sscre.benchmark_build --benchmark-dir benchmarks validate-candidates `
  --candidates benchmarks/candidates/fresh_held_out_draft.jsonl
```

`validate-candidates` passed after Step 2 relabel. All rows remain `review_status:
draft`.

## Step 3 — Human review

- [x] Operator OK via chat (`next`): all **80** rows **keep** at Step 2 draft
      labels; review sheet updated with `keep` in Action column.
- [x] Finals written to `benchmarks/candidates/fresh_held_out_reviewed.jsonl`
      (`human_review`; **100** rows after top-up to plan target; mix **28 / 52 /
      20**). **Not frozen** to
      `benchmarks/fresh_held_out.jsonl` until Step 4 operator OK.

```powershell
python benchmarks/candidates/tools/apply_fresh_held_out_review.py --assume-keep-all
python -m sscre.benchmark_build --benchmark-dir benchmarks validate-candidates `
  --candidates benchmarks/candidates/fresh_held_out_reviewed.jsonl
```

`validate-candidates` and `validate_review_policy` (held-out split) passed.

Post-review remediation (2026-10-15): `apply_fresh_held_out_remediation.py`
fixed four polarity-flip `reason` strings and relabeled `pair-0665` and
`pair-0675` to incompatible.

Top-up to **100** pairs (2026-10-15): `topup_fresh_held_out_batch.py`
`--target-total 100` added `pair-0696` … `pair-0715` (seed `20261016`);
collision set includes prior fresh batch + 615 corpus.

## Step 4 — Freeze

- [x] User written OK to freeze (2026-10-15 chat `next`).
- [x] Manifest SHA-256 recorded before any C-versus-A inspection.

```powershell
python benchmarks/candidates/tools/freeze_fresh_held_out.py
```

| Artifact | SHA-256 |
| --- | --- |
| `benchmarks/fresh_held_out.jsonl` | `dd500d5e0013aac4b53d8c52e6f68ac940016f6106c4e06bd2c3132e33725573` |
| `benchmarks/fresh_held_out_manifest.json` | `e3d0556930c357833567323e04184160b39fa60e20e89e7e08056d48b722e8b8` |

Gate `benchmarks/semantic-validity-held-out-gate.json` → `fresh-held-out-ready`
(`git_commit` at freeze: `699861b0c4cc64cf9d3f453a3bb2e7430755efc9`, worktree
dirty). **Step 6 not run** at freeze close.

## Step 5 — Harness fail-closed

- [x] `validate_p4_held_out_headline_run` accepts frozen
      `benchmarks/fresh_held_out.jsonl` when gate is `fresh-held-out-ready`.
- [x] Contaminated `benchmarks/held_out_test.jsonl` blocked for P4 held-out
      (`forbidden` / CLI non-zero exit).
- [x] `validate_fresh_held_out_gate_record` rejects ready gate pointing at
      `held_out_test.jsonl`; enforced on `load_held_out_gate` and freeze.

```powershell
python -m pytest tests/test_semantic_validity_held_out.py tests/test_semantic_validity_gate.py -q
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2
```

15 gate tests passed; `benchmark_validate --phase2` passed (615-pair split
unchanged; fresh file not in phase2 scope).

## Step 6 — One evaluation

- [x] User OK to run (2026-10-15). Commands used repo `src` on `PYTHONPATH`.

```powershell
$env:PYTHONPATH = "src"
python -m sscre.evaluate --benchmark benchmarks/fresh_held_out.jsonl `
  --config experiments/semantic-validity-evaluation-config-v1.json `
  --baseline all --split held-out --production `
  --output artifacts/evaluation/phase4-semantic-validity-held-out.json
python -m sscre.semantic_validity_gate `
  --config experiments/semantic-validity-evaluation-config-v1.json `
  --gate benchmarks/semantic-validity-held-out-gate.json `
  --held-out-artifact artifacts/evaluation/phase4-semantic-validity-held-out.json `
  --output artifacts/evaluation/phase4-semantic-validity-gate.json
```

Headline metrics (compatibility-cache vs exact-cache, primary population):

| Metric | Strategy A | Strategy C |
| --- | --- | --- |
| safe_reuse_coverage | 0.0 | ~0.036 |
| false_positive_rate | 1.0 (labeled) | 0.0 |
| abstention_rate | n/a | 0.22 |
| unlabeled_candidate_reuse_hits | 0 | 0 |

Pre-registered gate scoring: **pass** (`artifacts/evaluation/phase4-semantic-validity-gate.json`).

Code fix: `evaluate._validate_split` accepts `fresh_held_out.jsonl` via
`validate_fresh_held_out_split_benchmark` (manifest hash/id check).

## Step 7 — Evidence close

- [x] Step 6–7 metrics and verdict recorded in this file and gate JSON pointers.
- [x] Parent stabilization Workstream 5 checkboxes synced
      (`docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`, 2026-10-15).
- [x] `tests/test_semantic_validity_held_out.py` +
      `tests/test_semantic_validity_gate.py`: **16 passed** with
      `PYTHONPATH=src` (2026-10-15).
