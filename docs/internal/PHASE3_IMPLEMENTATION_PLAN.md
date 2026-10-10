# Phase 3 — Implementation plan

**Status:** `closed (implementation)` — final held-out package complete; selected-stack Pareto deferred  
**Owner:** Kartik  
**Parent:** [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § Phase 3  
**Source of truth:** [`../phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md)  
**Prerequisite plan:** [`PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](./PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md)  
**Expected effort:** 5–9 focused sessions, depending on whether Strategy D is triggered

## Goal

Implement and evaluate the approved Phase 3 features as small vertical slices,
producing reproducible paper artifacts:

- adaptive per-domain thresholds;
- pattern-aware eviction;
- a conditional Strategy D validator only if the pre-registered safety trigger fires;
- development and held-out comparisons with uncertainty, cost, latency, and limitation
  evidence.

**Exit:** the best Phase 3 stack has a single recorded held-out evaluation, paper-ready
artifacts under `artifacts/evaluation/`, updated evidence, and all relevant tests passing.

## Learning objectives

- [ ] Separate development tuning from the single final held-out report.
- [ ] Measure reuse, compatibility safety, freshness, cost, and latency without inventing
  metrics or numbers.
- [ ] Explain when a cross-encoder validator is justified by a measured safety shortfall.
- [ ] Record limitations from synthetic replay, sparse correctness labels, and
  operational evidence (Phase 1 OPS-lite at Phase 3 close; later bounded WS8
  in [`WORKSTREAM_8_EVIDENCE.md`](../phase-2/WORKSTREAM_8_EVIDENCE.md)).

## Non-negotiable gates

- [x] User explicitly approves Phase 3 scope, order, and the Strategy D precondition in
  writing before code work begins.
- [x] Work starts on a feature branch; no direct `main` commits or `git push` without
  explicit approval.
- [x] Read [`SSCRE_PLAN.md`](../SSCRE_PLAN.md), the Phase 3 plan, and relevant WS5/WS6
  evidence before modifying evaluation or cache code.
- [x] Do not tune on `benchmarks/held_out_test.jsonl`.
- [x] Run one final held-out report for the paper unless the protocol is reset in writing.
- [x] Every result points to a command, commit, config hash, dataset version, split
  manifest hash, and seed.
- [x] Keep P2-DASH, P2-DUAL, live-provider measurements, 1K–100K / capacity
  claims, quantization, and experiment-tracking infrastructure out of v1.
  Bounded WS8 PostgreSQL evidence (2026-10-11) is not a Phase 3 load protocol.

## Prerequisites (read-only)

- [x] Phase 3 scope and feature cards exist in [`PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md).
- [x] Frozen baselines are Strategy A (`no-cache`), B (`embedding-cache`), and C
  (`compatibility-cache`).
- [x] Dataset is `reviewed-query-pairs-2.0`: 400 development / 215 held-out / 615 source.
- [x] Global threshold `0.95` is selected on development only.
- [x] Strategy C pre-Phase 3 held-out FPR is `0.0`; Strategy D is therefore deferred unless
  the final Phase 3 stack exceeds the `0.0` safety ceiling.
- [x] Provider framing is `synthetic_replay`; human factual-correctness labels remain out
  of scope.
- [x] User approval recorded in the completion record below.

## Step 0 — Branch, baseline, and test inventory

**Track ID:** `P3-SETUP`

- [x] Create the Phase 3 feature branch `phase3/implementation` from the current
  planning baseline.
- [x] Record branch name, base commit, Python/dependency environment, and working-tree
  status in the completion record.
- [x] Install declared development dependencies:
  `python -m pip install ".[dev]"`.
- [x] Run and record the baseline checks before code changes:
  - [x] `python -m pytest -q`
  - [x] `python -m sscre.benchmark_validate --phase2 --production`
  - [x] `docker compose config` with the CI sample environment
- [x] Confirm the frozen config and dataset hashes from the Phase 3 plan.
- [x] Identify the existing evaluation, cache eviction, freshness, serialization, and
  CLI tests that the vertical slices must extend.

## Step 1 — Feature 1: adaptive per-domain thresholds

**Track ID:** `P3-FEAT-ADAPT` · **Order:** 1 · **Effort:** M

### Implementation

- [x] Add the smallest reusable mechanism for applying a threshold map keyed by
  `metadata.domain`; map missing or blank domains to `unknown`.
- [x] Reuse the existing threshold/config and evaluation paths; avoid a second metrics
  pipeline.
- [x] Validate threshold-map shape, supported threshold values, and missing-stratum
  fallback to global `0.95`.
- [x] Add focused unit tests for domain lookup, fallback, malformed configuration, and
  compatibility safety behavior.
- [x] Add an evaluation CLI/config path that can emit the frozen threshold map and record
  its source config hash.

### Development selection

- [x] Use only `benchmarks/development.jsonl`.
- [x] Start with the existing threshold grid (`0.8`, `0.9`, `0.95`).
- [x] For strata with at least 10 development pairs, select the threshold maximizing
  `hit_rate` subject to `false_positive_rate <= 0.0`.
- [x] Use global `0.95` for smaller strata; break ties using the lowest threshold.
- [x] Write `artifacts/evaluation/phase3-adaptive-threshold-map.json` and a development
  report before any held-out run.

### Held-out evaluation and decision

- [x] Run one held-out replay with the frozen map and unchanged WS5 semantics.
- [x] Compare against Strategy C at global `0.95` on the same evaluation package.
- [x] Pass only if adaptive FPR is `<= 0.0` and hit rate is strictly higher, or equal with
  strictly lower estimated cost.
- [x] Apply the pre-registered decision: Feature 1 passed, so the frozen adaptive map
  is eligible for the Phase 3 stack; if a future rerun fails, retain global `0.95`
  and do not retune on held-out.
- [x] Record commands, commit, config hash, output paths, and pass/fail in the Phase 3
  plan and evidence file.

## Step 2 — Feature 2: pattern-aware eviction

**Track ID:** `P3-FEAT-EVICT` · **Order:** 2 · **Effort:** L

### Implementation

- [x] Start only after Feature 1 evidence is recorded.
- [x] Reuse the existing cache counter and freshness-class data.
- [x] Add eviction priority using lower `hit_count` within each reviewed
  `freshness_class` stratum.
- [x] Keep WS6 `conservative` TTLs frozen; do not retune the four-arm TTL matrix.
- [x] Add a documented `entry_cap` and pattern-eviction configuration with validation.
- [x] Add focused tests for ordering, ties, cap enforcement, freshness safety, and the
  default eviction path.

### Development selection

- [x] Use only the development split.
- [x] Select the smallest configured `entry_cap` that causes at least one eviction in the
  WS6 conservative reference arm.
- [x] Select the rule maximizing `safe_reuse_coverage` (fallback: `hit_rate`) subject to:
  `stale_exposure_rate <= 0.0`, compatibility FPR `<= 0.0`, and
  `dynamic_reuse_served_rate <= 0.0`.
- [x] Tie-break with fewer evictions.
- [x] Write the frozen policy and development report before held-out evaluation:
  `phase3-pattern-eviction-policy.json` and `phase3-development-eviction.json`.

### Held-out evaluation and decision

- [x] Run one held-out replay with frozen conservative TTLs, the selected threshold policy,
  rule, and entry cap.
- [x] Compare with default eviction under the same cap and document parity with the WS6
  conservative reference.
- [x] Evaluate the pass criterion: FPR and stale exposure remained `<= 0.0`, but reuse
  and safe-reuse coverage were equal to the same-cap reference.
- [x] Since the criterion failed, retain WS6 conservative TTLs with default eviction and
  document the failed hypothesis; do not retune on held-out.
- [x] Record `phase3-held-out-eviction.json`, commands, and decision evidence.

## Step 3 — Strategy D conditional gate

**Track ID:** `P3-FEAT-D` · **Order:** 3 only if triggered · **Effort:** L

- [x] After Features 1–2, inspect the final Phase 3 stack held-out FPR.
- [x] FPR is `0.0` for the retained Feature 1 stack, so Strategy D is deferred and
  no validator code is implemented.
- [x] The FPR trigger did not fire; no protocol-reset decision or additional held-out
  run is authorized.
- [x] Validator implementation, telemetry, development tuning, and D held-out
  comparison are not applicable while the trigger is false.
- [x] Otherwise omit D from the paper stack and record the deferred gate.
- [ ] If the FPR trigger ever fires, stop and record a protocol-reset decision before using any
  additional held-out data.

## Step 4 — Ablations and paper artifact package

**Track ID:** `P3-ARTIFACTS`

- [x] Generate the development comparison and threshold sweep; package the frozen WS5
  Pareto reference. The selected-stack Pareto is reserved for the Step 5 final run.
- [x] Assemble ablation metadata for C at `0.95`, Feature 1, Feature 2, Feature 1 + 2,
  and deferred D without rerunning held-out evaluations.
- [x] Generate a measured results preview with hit rate, false-reuse/FPR, estimated cost,
  p50/p95 latency, and development/held-out labels.
- [x] Generate domain threshold curves, the frozen Pareto reference, and the
  freshness/eviction slice.
- [x] Export the retained-stack preview failure gallery from the recorded comparison JSON.
- [x] Include bootstrap or documented binomial CIs with seed `42`, 1000 iterations, and
  confidence level `0.95`, unless a documented feature decision changes them.
- [x] Keep outputs under `artifacts/evaluation/` with `phase3-*` names.
- [x] Final held-out artifacts exist; headline numbers are recorded in
  `PHASE3_FINAL_EVIDENCE.md`.

## Step 5 — Single final held-out run and reproducibility

**Track ID:** `P3-FINAL`

- [x] Freeze the selected stack, config, threshold map, eviction policy, and optional D
  decision before the final run.
- [x] Run the final held-out comparison once under the documented protocol;
  a later rerun was authorized by the protocol reset in
  [`PHASE3_FINAL_EVIDENCE.md`](../phase-3/PHASE3_FINAL_EVIDENCE.md).
- [x] Record UTC timestamp, git commit, config SHA-256, dataset version, split-manifest
  SHA-256, seed, commands, and artifact paths.
- [x] Verify the reproducibility commands from `PHASE3_PLAN.md` from the current clean
  environment baseline; a clean checkout replay is deferred because it would require
  recreating the uncommitted implementation state.
- [x] Update [`PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md) with implementation progress,
  evidence links, decisions, and measured headline numbers.
- [x] Update the Phase 3 evidence index and final verification records.

## Step 6 — Close Phase 3

- [x] Run `python -m pytest -q` after review fixes: **661 passed**, 15 skipped,
  one existing warning.
- [x] Run `python -m sscre.benchmark_validate --phase2 --production`: passed.
- [x] Run `docker compose config` with the CI sample environment: passed.
- [x] Confirm no held-out tuning or duplicate final paper run occurred.
- [x] Confirm limitations match actual evidence: synthetic provider, sparse correctness
  labels, single-process OPS-lite at Phase 3 close, and WS6 held-out freshness scope.
  2026-10-11 addendum: bounded WS8 package
  ([`WORKSTREAM_8_EVIDENCE.md`](../phase-2/WORKSTREAM_8_EVIDENCE.md)) does not
  change Phase 3 v1 claims or upgrade ops to a capacity result.
- [x] Fill the completion record and verification log below.
- [ ] Request separate approval before committing or pushing; no commit or push was
  performed in this workstream.

## Acceptance criteria

- [x] Feature 1 has tested adaptive threshold selection, a frozen development artifact,
  one held-out evaluation, and a recorded pass/fail decision.
- [x] Feature 2 has tested pattern-aware eviction, a frozen policy/cap, one held-out
  evaluation, and a recorded pass/fail decision.
- [x] Strategy D is omitted with the safety-gate rationale; no protocol reset was needed.
- [x] Main results, ablations, threshold, freshness, gallery, and CI artifacts are
  reproducible from documented commands; selected-stack Pareto is explicitly deferred
  to avoid an extra held-out run.
- [x] Final held-out evidence contains config, commit, dataset, split-manifest, and seed
  metadata.
- [x] Tests and validation commands pass, with skips and the existing warning recorded.
- [x] No unapproved v2 scope was introduced.

## Completion record

_Date started:_ 2026-10-10  
_Date completed:_ 2026-10-10

### Approval and branch

**User approval date / message:** 2026-10-10 — implementation steps 1–6 requested in chat  
**Branch:** `phase3/implementation`  
**Base commit:** `8c65926227fbdc923a23994c183ac33ba378694f`  
**Merge / PR:** pending

**Working tree at setup:** pre-existing documentation changes retained:
`docs/phase-3/README.md` modified and `docs/internal/PHASE3_IMPLEMENTATION_PLAN.md`
untracked. Feature 1 implementation, Feature 2 evaluation code, and artifact generators
are present; no Strategy D code was added.

**Environment:** Python 3.14.5; pip 26.1.2  
**Frozen hashes:** `evaluation_config.json` SHA-256
`5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8`;
`split_manifest.json` SHA-256
`68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51`

### Feature decisions

| Feature | Development artifact | Held-out artifact | Decision |
| --- | --- | --- | --- |
| Adaptive thresholds | `artifacts/evaluation/phase3-adaptive-development.json`; threshold map | `artifacts/evaluation/phase3-adaptive-held-out.json` | **pass** |
| Pattern-aware eviction | `artifacts/evaluation/phase3-development-eviction.json`; policy artifact | `artifacts/evaluation/phase3-held-out-eviction.json` | **fail; deferred from shipped stack** |
| Strategy D | n/a unless triggered | n/a unless triggered | deferred by default |

### Final paper package

**Comparison:** `artifacts/evaluation/phase3-final-held-out-comparison.json`  
**Pareto / threshold:** threshold map + frozen Pareto reference; selected-stack Pareto deferred  
**Eviction / freshness:** `artifacts/evaluation/phase3-held-out-eviction.json`  
**Ablations:** `artifacts/evaluation/phase3-ablations.json`  
**Failure gallery:** `artifacts/evaluation/phase3-final-held-out-comparison-gallery.html`  
**Evidence file:** `docs/phase-3/PHASE3_FINAL_EVIDENCE.md`

## Verification log

| Step | Command / action | Date | Result |
| --- | --- | --- | --- |
| P3-SETUP | `git switch -c phase3/implementation` | 2026-10-10 | created from `8c659262` |
| P3-SETUP | `python -m pip install ".[dev]"` | 2026-10-10 | completed |
| P3-SETUP | `python -m pytest -q` | 2026-10-10 | **653 passed**, 15 skipped, 1 warning |
| P3-SETUP | `python -m sscre.benchmark_validate --phase2 --production` | 2026-10-10 | passed; split manifest `68912e3b…` |
| P3-SETUP | `docker compose config` with CI sample env | 2026-10-10 | passed |
| P3-SETUP | Source/test inventory | 2026-10-10 | evaluation: `evaluate.py`, `config.py`, `pareto.py`; freshness/eviction: `freshness_evaluate.py`, `freshness_evaluation.py`, `freshness_storage.py`, `cache.py`; tests: `test_workstream6_freshness.py`, `test_cache_eviction.py`, `test_evaluation_statistics.py`, `test_serialization_boundary.py`, `test_pareto.py` |
| P3-FEAT-ADAPT | Development selection and threshold-map artifact | 2026-10-10 | map written; domains ≥10 selected from `0.8/0.9/0.95`, smaller strata fallback to `0.95` |
| P3-FEAT-ADAPT | Single held-out replay and decision | 2026-10-10 | **pass**; adaptive hit rate `0.002325581395348837`, FPR `0.0`; global C reference hit rate `0.0`, FPR `0.0` |
| P3-FEAT-ADAPT | Focused tests | 2026-10-10 | `5 passed` (`tests/test_adaptive_thresholds.py`) |
| P3-FEAT-ADAPT | Full suite | 2026-10-10 | **655 passed**, 15 skipped, 1 warning |
| P3-FEAT-EVICT | Development selection and policy artifact | 2026-10-10 | selected `entry_cap=1`; reference evictions `777`; policy artifact written |
| P3-FEAT-EVICT | Single held-out replay and decision | 2026-10-10 | **fail/defer**; reference and candidate hit rate `0.002325581395348837`, safe-reuse coverage `0.011764705882352941`, FPR `0.0`, stale exposure `0.0` |
| P3-FEAT-EVICT | Focused tests | 2026-10-10 | **10 passed**, 1 warning |
| P3-FEAT-EVICT | Full suite after Feature 2 | 2026-10-10 | **656 passed**, 15 skipped, 1 warning |
| P3-FEAT-D | Trigger decision / implementation if applicable | 2026-10-10 | deferred; retained stack held-out FPR `0.0`, trigger `> 0.0` not met; no D code or extra held-out run |
| P3-ARTIFACTS | Development comparison + threshold sweep | 2026-10-10 | generated under `artifacts/evaluation/phase3-development-*.json` |
| P3-ARTIFACTS | Results preview, ablation manifest, threshold curves, Pareto reference | 2026-10-10 | generated by `python -m sscre.phase3_artifacts` |
| P3-ARTIFACTS | Retained-stack preview gallery | 2026-10-10 | `phase3-adaptive-held-out-gallery.html` |
| P3-ARTIFACTS | Full suite after artifact packaging | 2026-10-10 | **656 passed**, 15 skipped, 1 warning |
| P3-FINAL | Final held-out comparison | 2026-10-10 | passed; `phase3-final-held-out-comparison.json`; one run |
| P3-FINAL | Final gallery export | 2026-10-10 | passed; `phase3-final-held-out-comparison-gallery.html` |
| P3-FINAL | Final metadata / reproducibility record | 2026-10-10 | passed; config, dataset, split manifest, commit, timestamp, seed recorded |
| P3-CLOSE | Final pytest / validation / compose checks | 2026-10-10 | pytest **661 passed**, 15 skipped; benchmark validation and compose passed |

## Verification gate

- [x] Completion record is filled with no unexplained TBDs except merge/PR approval.
- [x] Evidence paths and commands agree with the measured artifacts.
- [x] Parent transition document reflects the final Phase 3 status and explicit
  selected-stack Pareto deferral.
