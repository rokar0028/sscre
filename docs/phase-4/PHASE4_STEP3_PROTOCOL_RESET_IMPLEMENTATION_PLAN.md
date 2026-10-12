# Phase 4 Step 3 — Protocol reset implementation plan

## Goal

Execute parent Step 3 of
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md):
freeze a new evaluation protocol/config identity, define headline populations and
denominators, decide context-stripped pair handling, and record the held-out
manifest decision before any real-embedding development run or threshold selection.

This step authorizes protocol JSON and gate documentation only. It does not
authorize a real embedding provider, development or held-out A/B/C execution,
artifact regeneration for headline claims, or roadmap close.

**Status:** `closed (Step 3 protocol)` — frozen config and held-out gate on
2026-10-12.  
**Evidence:**
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md)
§ Step 3.  
**Parent:**
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md)
§ 10 Step 3.  
**Card:** `P4-SEMVALID` (parent § 5).

## Learning objectives

- [ ] Explain why `evaluation-config-1.0` remains historical and must not be
      overwritten for the semantic-validity claim.
- [ ] Distinguish development threshold selection from a fresh held-out headline
      gate.
- [ ] Describe how `context_required` pairs differ from the primary headline
      population.

## Prerequisites

- [x] Step 1 audit closed.
- [x] Step 2 candidate attribution closed.
- [x] Parent hypothesis, pass/fail, and stopping rules (`P4-SEMVALID`).
- [x] Linked paths in **Implementation corpus** exist in the checkout.

## Gates and stopping rules

**Gate A — authoring.** Closed when this plan exists and lists deliverables.

**Gate B — protocol freeze.** Mirror parent § 5 and § 9:

- Do not overwrite `experiments/evaluation_config.json` identity.
- Do not relabel the existing 215-record `held_out_test` split as fresh.
- If no fresh held-out population exists, record `held-out-deferred` or
  `held-out-unavailable`; do not imply a headline gate can run.
- Development records remain the only authorized split for threshold selection.
- Mark reuse of historical held-out artifacts as debug/historical only.

**Gate C — Step 3 close.** Close when frozen config, held-out gate record,
context-required policy, metric denominators, and evidence § Step 3 match.

## Implementation corpus

- [`../../experiments/semantic-validity-evaluation-config-v1.json`](../../experiments/semantic-validity-evaluation-config-v1.json)
- [`../../benchmarks/semantic-validity-held-out-gate.json`](../../benchmarks/semantic-validity-held-out-gate.json)
- [`../../benchmarks/split_manifest.json`](../../benchmarks/split_manifest.json)
- [`../../experiments/evaluation_config.json`](../../experiments/evaluation_config.json)
  (historical; unchanged)
- [`../phase-2/SAFETY_EVALUATION_CONTRACT_v1.md`](../phase-2/SAFETY_EVALUATION_CONTRACT_v1.md)
- [`../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
- [`../../src/sscre/baseline.py`](../../src/sscre/baseline.py) (threshold tie-break)
- [`../../src/sscre/evaluation_statistics.py`](../../src/sscre/evaluation_statistics.py)
  (sample FPR denominators)

## Open baseline gaps (after Step 3)

- [ ] Select and validate an approved real fixed-dimension embedding model
      (parent Step 4).
- [ ] Run development A/B/C under the frozen protocol (parent Step 5).
- [ ] Obtain a fresh held-out population and freeze
      `benchmarks/semantic-validity-split-manifest.json` (parent Step 3/6).
- [x] Apply `context_required` exclusions in `sscre.evaluate` after split
      validation (`evaluation_protocol.py`; legacy `evaluation-config-1.0`
      unchanged).
- [ ] Implement zero-denominator FPR unavailable reporting in development
      artifacts (parent Step 5; rule frozen in config §
      `zero_denominator_reporting`).

## Implementation steps

### Step 1 — New config identity

- [x] Add
      [`../../experiments/semantic-validity-evaluation-config-v1.json`](../../experiments/semantic-validity-evaluation-config-v1.json)
      with `config_version` `semantic-validity-evaluation-config-1.0`.
- [x] Reference superseded `evaluation-config-1.0` without editing
      [`../../experiments/evaluation_config.json`](../../experiments/evaluation_config.json).
- [x] Freeze threshold grid `[0.8, 0.9, 0.95]`, `embedding_top_k` 5,
      `max_false_positive_rate` 0.0, `max_abstention_rate` 0.5, statistics
      settings, cost/latency reporting rules, and threshold tie-break order
      matching `select_embedding_threshold` in baseline replay.

### Step 2 — Populations and denominators

- [x] Document primary headline population (authorized fresh held-out when
      gate permits; excludes `context_required_pair_ids`).
- [x] Document hit rate, safe-reuse coverage, FPR, precision, recall, and
      abstention denominators aligned with `baseline.py` and
      `evaluation_statistics.summarize_request_samples`.
- [x] Document `unlabeled_candidate_reuse` exclusion from headline FPR and pass
      rule (Step 2 behavior).

### Step 3 — Context-stripped identical-text pairs

- [x] Policy: retain in dataset; exclude 27 identified pair IDs from primary
      headline population; report under `context_required` stratum in later
      artifacts.
- [x] Identification matches CacheEval anaphoric rows with identical normalized
      query text and `insufficient_evidence` labeling (see config list).

### Step 4 — Held-out manifest decision

- [x] Inventory: no fresh licensed held-out package in repo beyond the already-used
      215-record split.
- [x] Record
      [`../../benchmarks/semantic-validity-held-out-gate.json`](../../benchmarks/semantic-validity-held-out-gate.json)
      with status `held-out-deferred`.
- [x] Document historical contamination artifacts; forbid relabeling existing
      held-out as fresh.

### Step 5 — Development-only threshold selection

- [x] Authorize threshold selection only on `benchmarks/development.jsonl` under
      the new config.
- [x] Document legacy held-out and fake-embedding artifacts as
      debug/historical-only.

## Verification

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_evaluation_protocol.py
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
```

Record results in evidence § Step 3. Do not run `sscre.evaluate` development or
held-out commands in this step.

## Acceptance criteria

### Goal / Exit — authoring gate

- [x] This plan exists at
      `docs/phase-4/PHASE4_STEP3_PROTOCOL_RESET_IMPLEMENTATION_PLAN.md`.
- [x] Deliverables link parent Step 3 and `P4-SEMVALID`.

### Verification — Step 3 close

- [x] New protocol config exists; historical `evaluation-config-1.0` unchanged.
- [x] Threshold grid, top-K, FPR cap, abstention ceiling, latency/cost rules,
      and tie-break rules are frozen in config JSON.
- [x] Primary population and metric denominators are documented.
- [x] Context-stripped pairs use `context_required` exclusion policy.
- [x] Held-out gate status is `held-out-deferred` with explicit reasoning.
- [x] Evidence § Step 3 and parent Step 3 checkboxes updated.
- [x] No real-provider run, no development/held-out artifact for headline claim.
