# SSCRE Phase 3 implementation plan

**Status:** `implementation-complete` — final held-out package recorded 2026-10-10;
Feature 2 and Strategy D are deferred by their gates; selected-stack Pareto remains
deferred to avoid an additional held-out run. Authoring closed 2026-10-09 per
[`PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md)
Step 7; implementation was explicitly requested in chat on 2026-10-10.

**Last updated:** 2026-10-11 (Workstream 1 registry — Features 4–8 cards)
**Owner:** Kartik  
**Parent transition:** [`docs/internal/PHASE3_TRANSITION.md`](../internal/PHASE3_TRANSITION.md)  
**Master scope:** [`docs/SSCRE_PLAN.md`](../SSCRE_PLAN.md) § Phase 3

---

## Goals

Phase 3 must produce **measured**, reproducible evidence for the paper:

- **Reuse vs safety:** Hit rate and false-reuse (unsafe-serve / compatibility false-positive)
  rates at a pre-registered operating point, with uncertainty (bootstrap or documented
  binomial CIs).
- **Trade-offs:** Cost and latency (p50/p95) of cache-hit vs miss paths under
  `synthetic_replay` (see limitations).
- **Advanced policies:** Test whether adaptive thresholds and pattern-aware eviction
  improve the Pareto frontier vs frozen Strategy C at global threshold `0.95`.
- **Conditional validator:** Add Strategy D (cross-encoder) **only if** a pre-written
  held-out safety shortfall is documented for Strategy C.
- **Honest limitations:** Limitations section tied to real gaps (provider, labels, ops),
  not aspirational coverage.

---

## Non-goals (Phase 3 v1)

- Multi-region deployment or geo-distributed cache coordination.
- Unbounded observability stacks, dashboard-first UX, or WS9 dual-model experiments
  (Phase 2 deferrals **P2-DASH**, **P2-DUAL**).
- Full **615-pair** human factual-correctness labeling (**P0-LABELS:** out of scope
  before paper).
- Credentialed **live provider** measurement tables (**P0-PROVIDER:** deferred through
  Phase 3 unless promoted in a new decision record).
- 1K–100K Q/day, multi-host, or production-capacity claims. Bounded local WS8
  PostgreSQL evidence exists
  ([`WORKSTREAM_8_EVIDENCE.md`](../phase-2/WORKSTREAM_8_EVIDENCE.md)) and is
  **not** that protocol. Phase 1 lite remains
  [`WORKSTREAM_8_OPS_LITE_EVIDENCE.md`](../phase-2/WORKSTREAM_8_OPS_LITE_EVIDENCE.md).
  Live container restart is still untested.
- int8 quantization and 1K→100K simulated Q/day load tests until the core safety/reuse
  story is stable (optional cards may defer; see **Deferred** below).

## Resource requirements and timing

The paper should not depend on paid infrastructure unless the claim being made
requires it.

- [x] **Phase 2:** Use local CPU, deterministic fake providers, and synthetic
  replay. A paid LLM API or GPU is not required for the implementation or
  reproducible tests.
- [x] **Phase 3:** Use local CPU and synthetic replay for the final paper
  artifacts. Live provider measurements, large-scale load tests, quantization,
  and GPU-backed inference are deferred.
- [x] **Strategy D:** Do not add another LLM or cross-encoder merely to improve
  the architecture. Add it only after a documented held-out FPR greater than
  `0.0`; the Phase 3 trigger did not fire.
- [ ] **Post-Phase 3 optional validation:** If the paper needs real-world
  provider cost, token, rate-limit, or network-latency claims, run a small
  separately labelled experiment through the target embedding/LLM API. Record
  provider and model versions, token usage, cost, and latency without storing
  credentials.
- [ ] **Post-Phase 3 optional scaling:** Rent a GPU only if self-hosting,
  cross-encoder inference, quantization, or a defined high-volume load test is
  selected and profiling shows CPU/API execution is the bottleneck. This is
  not needed for the current paper result.

Never combine synthetic and live-provider numbers in one results table. Any
future live-provider or GPU experiment requires a new scope/protocol decision
and its own reproducibility metadata.

---

## Baselines frozen (pre–Phase 3)

Do not redefine Strategies A / B / C during Phase 3 execution. Evaluation CLI baseline
keys and paper names:

| Paper / plan name | Evaluate `--baseline` key | Role |
| --- | --- | --- |
| **Strategy A** — no cache | `no-cache` | Every query generates; cost/latency upper bound |
| Exact-match cache | `exact-cache` | Hash equality only (not A/B/C letter, but WS5 held-out package) |
| **Strategy B** — embedding only | `embedding-cache` | Similarity threshold only; `similarity_threshold_met` → serve |
| **Strategy C** — compatibility-aware | `compatibility-cache` | Rules + resolver; primary proposed system |

Narrative and contracts: [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md)
(WS1–5), [`SAFETY_EVALUATION_CONTRACT_v1.md`](../phase-2/SAFETY_EVALUATION_CONTRACT_v1.md).

### Configuration and artifacts (frozen)

| Item | Value / path |
| --- | --- |
| Config file | `experiments/evaluation_config.json` |
| Config SHA-256 (bytes on disk) | `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8` (2026-10-09) |
| Config version | `evaluation-config-1.0` |
| Dataset version | `reviewed-query-pairs-2.0` |
| Splits | 400 development / 215 held-out / 615 source |
| Development threshold sweep | `artifacts/evaluation/workstream5-development-sweep.json` |
| Held-out comparison (`--baseline all`) | `artifacts/evaluation/workstream5-held-out-comparison.json` |
| Held-out Pareto / operating point | `artifacts/evaluation/workstream5-held-out-pareto.json` |
| WS5 evidence (commands, commit) | [`WORKSTREAM_5_EVIDENCE.md`](../phase-2/WORKSTREAM_5_EVIDENCE.md) |
| Measurement environment | `synthetic_replay` |

### Pre–Phase 3 held-out safety snapshot (from artifacts only)

**Pareto / operating point** — `artifacts/evaluation/workstream5-held-out-pareto.json`
(WS5 regeneration 2026-10-08):

- **Selected threshold:** `0.95`
- **Threshold selection split:** `development` (not retuned on held-out labels)
- **Selected constraint:** `max_false_positive_rate` with `limit` `0.0`
- **Observed false-positive rate at selection:** `0.0`
- **Constraint satisfied:** `true` (Strategy C at `0.95` on held-out Pareto replay)

**Held-out comparison report** — `artifacts/evaluation/workstream5-held-out-comparison.json`
(`git_commit` `1beed4de227d00bd3dbbc1b9b57ccaa0f92add02`, `request_count` **430** per
baseline). Top-level `baselines` summary at the frozen WS5 package (do not recompute for
the paper without a new logged run):

| Baseline key | `false_positive_rate` | `hit_rate` | Source field |
| --- | --- | --- | --- |
| `compatibility-cache` (Strategy C) | `0.0` | `0.0` | `baselines.compatibility-cache` |
| `embedding-cache` (Strategy B) | `0.35714285714285715` | `0.09767441860465116` | `baselines.embedding-cache` |

Strategy D is **conditional** — see [Feature 3](#feature-3--strategy-d-cross-encoder-validator).
**Default (2026-10-09): defer implementation** because pre–Phase 3 Strategy C
held-out **`false_positive_rate`** is **`0.0`** and Pareto **`selected_constraint.satisfied`**
is **`true`** at τ = **`0.95`**.

---

## Dataset policy

- **Development split** (`benchmarks/development.jsonl`, 400 pairs): threshold sweeps,
  adaptive threshold tuning, eviction policy knobs, and diagnostic Pareto exploration.
- **Held-out split** (`benchmarks/held_out_test.jsonl`, 215 pairs): **forbidden** for
  tuning or threshold selection; **one** final held-out report for the paper unless the
  protocol is reset in writing (see transition non-negotiables).
- **Operating point:** Global similarity threshold **`0.95`** chosen on development only
  (WS5); Phase 3 adaptive policies must document their own development protocol before
  any held-out evaluation.
- **Seeds / statistics:** `bootstrap_seed` `42`, `bootstrap_iterations` `1000`,
  `confidence_level` `0.95` in evaluation config unless a feature card documents a change.

---

## Working agreements

- Feature branch for Phase 3 work; no commits to `main` without explicit OK.
- No `git push` without explicit OK.
- **No invented numbers** in this plan or the paper — every table/plot traces to a
  recorded command, config version, dataset version, and seed.
- **No Phase 3 implementation** for a feature until its row in **Feature cards** has
  hypothesis + pass/fail criterion completed (Steps 2–4 of the internal authoring plan).
- Promote optional rows and run the pre-code checklist per
  [`WORKSTREAM_1_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_1_IMPLEMENTATION_PLAN.md)
  before Workstreams 5–8 code.
- Read [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md) and
  relevant `WORKSTREAM_*_EVIDENCE.md` before changing evaluation or cache code.

---

## Feature cards

Complete every column before implementing that feature.

| Feature | Hypothesis | Pass/fail criterion | Primary metric | Baselines | Effort | Order |
| --- | --- | --- | --- | --- | --- | --- |
| Adaptive per-domain thresholds | Domain-stratified τ increases Strategy C `hit_rate` vs global `0.95` without held-out `false_positive_rate` > `0.0` | Dev-only τ selection; one held-out replay — [Feature 1](#feature-1--adaptive-per-domain-thresholds) | `hit_rate`, `false_positive_rate`, `estimated_cost_usd`, `p95_latency_ms` | A, B, C global vs C adaptive | **M** (2–3 sessions) | 1 |
| Pattern-aware eviction (hits + freshness class) | Pattern eviction ↑ reuse vs WS6 `conservative` at FPR ≤ `0` | Dev knob tuning + one held-out replay — [Feature 2](#feature-2--pattern-aware-eviction) | `stale_exposure_rate`, `hit_rate`, `eviction_count` | C + WS6 `conservative` | **L** (3–4 sessions) | 2 |
| Strategy D cross-encoder validator | **Conditional** — CE validator lowers FPR vs C if trigger fires | Dev threshold + one held-out replay — [Feature 3](#feature-3--strategy-d-cross-encoder-validator) | `false_positive_rate`, validator `p95_latency_ms`, cost | C (same stack, no D) | **L** (4+ sessions); **default defer** | 3 |
| Failure clustering (manual synthesis) | Grouping held-out failures by category/strata yields reproducible paper discussion without new replay | Analysis-only on frozen JSON — [Feature 4](#feature-4--failure-clustering-manual-synthesis) | cluster counts, `false_positive_rate` by category | B vs C from final held-out comparison | **S** (1 session) | 4 |
| Experiment-tracking gate (manual audit) | A structured provenance audit shows whether manual JSON + evidence files suffice | Read-only inventory — [Feature 5](#feature-5--experiment-tracking-gate-manual-audit) | gap count, manifest coverage | n/a (process) | **S** (1 session) | 5 |
| Float32 embedding storage baseline | Measuring development-scale bytes shows whether embeddings dominate cache storage | Development replay only — [Feature 6](#feature-6--float32-embedding-storage-baseline) | `embedding_bytes`, `total_bytes`, embedding share | float32 reference | **M** (1–2 sessions) | 6 |
| int8 embedding quantization | **Conditional** — int8 cuts embedding bytes ≥ 3.5× without worsening dev safety/reuse | Dev compare only — [Feature 7](#feature-7--int8-embedding-quantization-conditional) | byte ratio, `hit_rate`, `false_positive_rate`, similarity drift | float32 vs int8 on development | **M** (2–3 sessions) | 7 |
| Simulated load ladder (1K→100K Q/day) | Time-compressed ladder finds the first reproducible component bottleneck or `not_reached` | Ladder protocol — [Feature 8](#feature-8--simulated-load-ladder-1k100k-qday) | p95 latency, error rate, throughput, `first_bottleneck` | vs Phase 4 / WS8 bounded profiles (not substitutes) | **L** (3–4 sessions) | 8 |

### Feature 1 — Adaptive per-domain thresholds

**Order:** 1 · **Implementation ID:** `P3-FEAT-ADAPT`

#### Hypothesis

Per-domain similarity thresholds (τ) chosen **only** on the development split
increase Strategy C (`compatibility-cache`) **`hit_rate`** versus a single global
τ = **`0.95`**, without raising held-out **`false_positive_rate`** above the
pre-registered limit **`0.0`** (same semantics as `max_false_positive_rate` in
`experiments/evaluation_config.json`).

#### Domain definition

- **Stratum field:** benchmark record `metadata.domain` (schema `1.1`, see
  [`benchmarks/README.md`](../../benchmarks/README.md) § Phase 2 record schema).
- **Missing domain:** `metadata.domain` null or blank → stratum label **`unknown`**
  (do not drop pairs).
- **Split sizes (pairs, 2026-10-09 inventory):**

  | Stratum | Development pairs | Held-out pairs |
  | --- | ---: | ---: |
  | `qa_open` | 97 | 53 |
  | `qa_factual` | 85 | 40 |
  | `conversational` | 83 | 46 |
  | `math` | 53 | 40 |
  | `code` | 50 | 28 |
  | `unknown` | 26 | 6 |
  | other (`general`, `programming`, …) | ≤ 2 each | ≤ 1 each |

  Report overall metrics plus domain strata where held-out **directed request** count
  ≥ **`10`** (430 requests total on held-out = 215 pairs × 2 directions).

#### Development protocol (tuning allowed)

1. **Baseline under test:** Strategy C (`compatibility-cache`) with per-domain τ map.
2. **Candidate grid:** start with `embedding_thresholds` in
   `experiments/evaluation_config.json` (`0.8`, `0.9`, `0.95`); document any extension
   in evidence before use.
3. **Per stratum** with ≥ **`10` development pairs**, select τ that **maximizes**
   stratum `hit_rate` subject to stratum `false_positive_rate` ≤ **`0.0`** on
   development directed requests (same compatibility false-positive definition as WS5).
4. **Small strata** (< **`10`** development pairs): use global τ = **`0.95`** (no
   stratum-specific tuning).
5. **Tie-break:** lowest τ among tied hit rates (more conservative similarity).
6. **Output artifact:** frozen τ map JSON (stratum → τ) + config hash, committed or
   stored under `artifacts/evaluation/` before any held-out run.

Held-out labels and outcomes are **not** used in steps 1–6.

#### Held-out protocol (evaluation only)

1. **Single** held-out replay on `benchmarks/held_out_test.jsonl` with the frozen τ map
   and unchanged WS5 config except documented adaptive-threshold fields.
2. Compare against **reference** Strategy C at global τ = **`0.95`** on the same
   commit and config (regenerate or cite pre-Phase-3 snapshot in
   [`Baselines frozen`](#baselines-frozen-prephase-3) for reference FPR / hit_rate).

#### Pass / fail (pre-registered)

**Pass** (adaptive policy ships in the Phase 3 stack) iff **all** hold:

- Held-out **`false_positive_rate`** ≤ **`0.0`** for adaptive Strategy C (point
  estimate in report JSON).
- Held-out **`hit_rate`** > reference global-τ Strategy C **`hit_rate`**, **or**
  equal `hit_rate` with strictly lower **`estimated_cost_usd`** at the same safety
  constraint.

**Fail / stopping rule:** If any pass condition fails, **do not** ship adaptive τ for
the paper; report global **`0.95`** only and treat Feature 1 as falsified. Do not
retune on held-out.

#### Primary metrics (WS5 report field names)

Report top-level baseline fields and, where implemented, `statistics.by_baseline` /
strata payloads:

| Metric | JSON field(s) |
| --- | --- |
| Reuse | `hit_rate`, `cache_hits`, `cache_misses` |
| Safety | `false_positive_rate`, `false_positive_examples` |
| Cost | `estimated_cost_usd`, token fields |
| Latency | `p50_latency_ms`, `p95_latency_ms`, `p99_latency_ms` |
| Uncertainty | `statistics` → proportion CIs for `hit_rate`, `false_positive_rate` |

#### Baselines (same held-out workload)

| Label | Evaluate baseline | Threshold policy |
| --- | --- | --- |
| Strategy A | `no-cache` | n/a |
| Exact cache | `exact-cache` | n/a |
| Strategy B | `embedding-cache` | global τ = `0.95` |
| Strategy C (reference) | `compatibility-cache` | global τ = `0.95` |
| Strategy C (candidate) | `compatibility-cache` | frozen per-domain τ map |

#### Effort

**M** — about **2–3** focused sessions (τ map selection tooling, evaluation hook,
development + one held-out report, tests, evidence markdown).

#### Evidence (to create at implementation time)

- `artifacts/evaluation/phase3-adaptive-threshold-map.json` (or named in commit message)
- Development diagnostic report + held-out comparison JSON paths recorded in
  **Implementation progress** below.

---

### Feature 2 — Pattern-aware eviction

**Order:** 2 · **Implementation ID:** `P3-FEAT-EVICT`

#### Hypothesis

When a **pre-registered entry cap** forces evictions during Strategy C replay,
evicting lower-**`hit_count`** candidates first within each reviewed
**`freshness_class`** stratum increases **`hit_rate`** (or **`safe_reuse_coverage`**)
versus the Workstream 6 **`conservative`** TTL + default eviction baseline, without
increasing **`stale_exposure_rate`** or compatibility **`false_positive_rate`**
above **`0.0`**.

#### Scope (what this feature changes)

- **In scope:** eviction **priority** under storage pressure using entry
  **`hit_count`** (repository counter) and reviewed pair **`freshness_class`**
  (`stable` | `semi_dynamic` | `dynamic` on benchmark records).
- **Frozen (not retuned in Feature 2 v1):** WS6 selected **`conservative`**
  `CacheControlPolicy` TTLs from
  `artifacts/evaluation/workstream6-development-freshness.json`; Strategy C
  similarity τ from Feature 1 outcome (**adaptive map if Feature 1 passed**, else
  global **`0.95`**).
- **Out of scope:** multi-process eviction, PostgreSQL load tests, public
  invalidation API, retuning the WS6 four-arm TTL matrix.

#### Workloads and WS6 limitations

- **Development (400 pairs):** full freshness mix (391 / 5 / 4 reviewed stable /
  semi-dynamic / dynamic) — use for knob tuning and stale-exposure accounting
  ([`WORKSTREAM_6_EVIDENCE.md`](../phase-2/WORKSTREAM_6_EVIDENCE.md) Step 1).
- **Held-out (215 pairs):** **stable reviewed class only** for freshness claims
  (`held_out_freshness_scope`: semi-dynamic and dynamic **`unavailable`** per
  `experiments/evaluation_config.json` → `freshness_experiment`).
- **Stale exposure definition:** served reviewed stale exposure per
  `src/sscre/freshness_stale_exposure.py` (same as WS6); answer-level stale
  exposure remains **`unavailable`** (`answer_availability: none` on all 615 pairs).

#### Development protocol (tuning allowed)

1. Add a documented **`phase3_eviction_experiment`** block (or equivalent) in
   evaluation config: **`entry_cap`** grid and pattern-eviction rule parameters
   (implementation records exact names in evidence).
2. **Entry cap selection (development only):** choose the **smallest** cap from the
   grid that produces **`eviction_count` ≥ 1** on the development replay for the
   WS6 **`conservative`** reference arm (forces pattern eviction to matter).
3. **Pattern rule selection (development only):** among candidate rules, maximize
   **`safe_reuse_coverage`** (fallback: **`hit_rate`** on Strategy C report) subject
   to:
   - **`stale_exposure_rate` ≤ `0.0`**
   - compatibility **`false_positive_rate` ≤ `0.0`**
   - **`dynamic_reuse_served_rate` ≤ `0.0`** (align with WS6 selection constraints)
4. **Tie-break:** fewer **`eviction_count`** at equal coverage.
5. **Output artifact:** frozen eviction policy JSON + **`entry_cap`** under
   `artifacts/evaluation/` before held-out.

Held-out labels and outcomes are **not** used in steps 1–5.

#### Held-out protocol (evaluation only)

1. **Single** held-out replay on `benchmarks/held_out_test.jsonl` with frozen
   **`conservative`** TTLs, frozen τ map (Feature 1), frozen pattern-eviction rule,
   and frozen **`entry_cap`**.
2. **Reference arm:** repeat replay with the same cap and TTLs but **default**
   eviction ordering (pre-Feature-2 behavior) — must match WS6 conservative metrics
   within the same replay harness, or cite
   `artifacts/evaluation/workstream6-held-out-freshness.json` (`conservative` policy
   arm) as the historical reference and document harness parity in evidence.

#### Pass / fail (pre-registered)

**Pass** iff **all** hold on held-out:

- Strategy C compatibility **`false_positive_rate` ≤ `0.0`**
- **`stale_exposure_rate` ≤ `0.0`** (and not worse than WS6 conservative reference
  point estimate on the same split)
- **`hit_rate`** or freshness-report **`safe_reuse_coverage`** strictly **greater**
  than the conservative reference arm under the **same** **`entry_cap`**

**Fail / stopping rule:** Ship WS6 **`conservative`** + default eviction only; do not
claim pattern-aware eviction in the paper. No held-out retuning.

#### Primary metrics (JSON field names)

| Concern | Field(s) | Typical path |
| --- | --- | --- |
| Stale exposure | `stale_exposure_count`, `stale_exposure_rate` | `sscre.freshness_evaluate` policy arms; `stale_exposure_accounting` |
| Reuse | `hit_rate`, `safe_reuse_coverage`, `cache_hit_rate` | compatibility baseline report; freshness policy metrics (`FRESHNESS_METRIC_FIELDS`) |
| Safety | `false_positive_rate`, `freshness_violation_rate` | WS5 compatibility report + freshness metrics |
| Storage / eviction | `eviction_count`, `entries`, `total_bytes` | `policy_storage_snapshot` / `freshness_storage.build_policy_storage_pairing` (`synthetic_storage_simulation`) |
| Strata | `statistics.by_baseline.*.strata.by_freshness_class` | when compatibility statistics attached |

#### Baselines

| Reference | Description |
| --- | --- |
| **WS6 conservative** | Selected policy in `workstream6-development-freshness.json`; held-out replay in `workstream6-held-out-freshness.json` |
| **Strategy C** | `compatibility-cache` at frozen τ (Feature 1 or `0.95`) with **`conservative`** TTLs |
| **Candidate** | Same as C + pattern-aware eviction under frozen **`entry_cap`** |

Do not introduce a new TTL policy matrix for Feature 2 v1.

#### Effort

**L** — about **3–4** focused sessions (eviction scorer in cache replay path, config
schema, development + held-out freshness/compatibility reports, tests, evidence).

#### Evidence (to create at implementation time)

- `artifacts/evaluation/phase3-pattern-eviction-policy.json` (rule + `entry_cap`)
- `artifacts/evaluation/phase3-development-eviction.json` (development selection log)
- `artifacts/evaluation/phase3-held-out-eviction.json` (single held-out replay)
- Commands mirrored from WS6:
  `python -m sscre.freshness_evaluate` (+ new flags documented in evidence)

---

### Feature 3 — Strategy D (cross-encoder validator)

**Order:** 3 (conditional) · **Implementation ID:** `P3-FEAT-D`  
**Plan status:** **`deferred`** — do **not** implement unless the [trigger](#trigger-when-to-build-d) fires after Features 1–2.

#### Precondition (Step 0 snapshot)

From frozen WS5 artifacts (cited in [Baselines frozen](#baselines-frozen-prephase-3)):

| Check | Source | Value |
| --- | --- | --- |
| Safety target (cap) | `experiments/evaluation_config.json` → `max_false_positive_rate` | **`0.0`** |
| Strategy C held-out FPR | `workstream5-held-out-comparison.json` → `baselines.compatibility-cache.false_positive_rate` | **`0.0`** |
| Pareto constraint at τ = `0.95` | `workstream5-held-out-pareto.json` → `selected_constraint` | **`satisfied`: `true`**, **`observed`: `0.0`** |

**Implication:** Strategy D is **not authorized** on the pre–Phase 3 baseline. Re-check
only after the **single final held-out run** for the best Phase 3 stack (Features 1–2).

**Latest gate re-check (2026-10-11):** Workstream 1 Step 6 — frozen final comparison
still **`false_positive_rate` `0.0`**; trigger not fired; see
[`WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md`](./WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md).

#### Trigger (when to build D)

Implement Strategy D **only if**, on that **final held-out** compatibility report for
the Phase 3 stack (τ map + eviction policy as shipped):

**`false_positive_rate` > `0.0`** (strictly above `max_false_positive_rate`).

Use the same false-positive definition as WS5 Strategy C (`compatibility-cache` report
JSON). Do not use held-out outcomes to tune Features 1–2 and then invoke D on the same
run without a **protocol reset in writing**.

#### Stopping rule (when **not** to build D)

**Do not implement Strategy D** if any of the following hold:

1. **Pre–Phase 3:** Strategy C held-out **`false_positive_rate` ≤ `0.0`** (current state).
2. **Post Features 1–2:** Final held-out **`false_positive_rate` ≤ `0.0`** for the shipped stack.
3. **Cost / latency:** Even if FPR > `0`, defer D if a documented development budget shows
   validator **`p95_latency_ms`** above the [latency budget](#latency-budget) **and** no
   cheaper rule-only fix was attempted on development.

**Default paper path:** Report Strategies A / B / C (+ Phase 3 policies) with Strategy D
listed as **not required** because the zero FPR cap was met.

#### Hypothesis (applies only if trigger fires)

Adding a cross-encoder validation step on Strategy C **SAFE** candidates reduces
held-out **`false_positive_rate`** below the Phase 3 stack without D, while keeping
added **`p95_latency_ms`** within the latency budget and **`estimated_cost_usd`** below
the no-cache baseline at the same split.

#### Development protocol (tuning allowed **only after trigger**)

1. **Validator implementation:** start with a **deterministic fake cross-encoder**
   (mirrors `fake-embedding` replay); document swap to a real model as out of v1 scope
   unless P2-PROV is promoted.
2. **Development split only:** tune validator score threshold and **when** to invoke
   (e.g. all SAFE candidates vs borderline similarity band) to minimize development
   **`false_positive_rate`** subject to development **`hit_rate`** not below C-without-D
   by more than **`0.05`** absolute (5 percentage points).
3. **No held-out tuning** of validator thresholds.
4. **Output artifact:** frozen validator config JSON under `artifacts/evaluation/`.

#### Held-out protocol (evaluation only)

1. **One** held-out replay: Phase 3 stack **with** Strategy D and frozen validator config.
2. Compare to **reference:** same stack **without** D (same τ, TTL, eviction, cap).

#### Pass / fail (pre-registered, only if D is built)

**Pass** (Strategy D included in paper stack) iff **all** hold on held-out:

- **`false_positive_rate`** **<** reference C-stack **`false_positive_rate`** (strict improvement).
- **`false_positive_rate` ≤ `0.0`** (still meets `max_false_positive_rate`).
- Validator **`p95_latency_ms`** ≤ **latency budget** (see below).
- **`estimated_cost_usd`** ≤ reference no-cache arm on the same held-out comparison run
  (or document explicit trade-off failure in limitations).

**Fail:** Omit D from the shipped stack; report C-only results. Do not retune on held-out.

#### Latency budget

- **Default budget:** validator **`p95_latency_ms` ≤ `10.0`** on `synthetic_replay`
  (in-process fake validator; record actual measured p95 in evidence).
- If fake validator p95 exceeds budget on development, **do not** proceed to held-out D;
  defer D and document validator cost in limitations ([`SSCRE_PLAN.md`](../SSCRE_PLAN.md) § 9.3).

#### Primary metrics

| Metric | JSON / report field |
| --- | --- |
| Safety | `false_positive_rate`, `false_positive_examples`, `UNSAFE`/`UNCERTAIN` rates in decision breakdown |
| Validator cost | New report fields: `validator_invocation_count`, `validator_latency_ms` (p50/p95/p99), `validator_tokens` or synthetic cost analogue |
| Reuse trade-off | `hit_rate`, `cache_hits`, `estimated_cost_usd` |
| Uncertainty | `statistics` proportion CIs for `false_positive_rate` where attached |

Field names for validator telemetry must be added to the serialization contract before
implementation (no invented numbers in this plan).

#### Baselines

| Arm | Description |
| --- | --- |
| **Reference** | Phase 3 stack, Strategy C, **no** cross-encoder |
| **Candidate** | Same stack + Strategy D validator on eligible candidates |
| **Context** | Strategies A / B unchanged from WS5 package for discussion only |

#### Effort

**L** — **4+** focused sessions **if triggered** (validator path, traces, evaluate hook,
development tune, one held-out run, tests). **Zero** if deferred (default).

#### Evidence (only if implemented)

- `artifacts/evaluation/phase3-validator-config.json`
- Held-out comparison including `compatibility-cache` + D arm (CLI flags documented
  in evidence **only if** Strategy D is implemented; default path is deferral)
- Trace examples in failure gallery for validator-blocked vs served cases

---

### Feature 4 — Failure clustering (manual synthesis)

**Order:** 4 · **Implementation ID:** `P3-FEAT-CLUSTER` (promoted from `P3-OPT-CLUSTER`,
2026-10-11)

#### Hypothesis

Grouping held-out evaluation failures by **reviewed failure category**, **rule
fired**, **domain**, and **freshness class** using existing comparison and WS7
quality JSON produces a reproducible cluster inventory for the paper **without**
a new benchmark replay or automated clustering pipeline.

#### Scope (what this feature changes)

- **In scope:** manual or scripted **aggregation** over frozen artifacts; named
  recurring patterns; singleton bucket for one-off cases; mitigations labeled
  as rule change, benchmark gap, or no action.
- **Frozen:** final held-out comparison
  `artifacts/evaluation/phase3-final-held-out-comparison.json` (paper stack:
  Feature 1 adaptive thresholds, default eviction); do not retune policies.
- **Supplementary inputs (no replay):**
  - `artifacts/evaluation/workstream7-quality-analysis.json` (Phase 2 category
    strata and aggregates)
  - `artifacts/evaluation/phase3-development-comparison.json` when held-out
    has too few examples in a stratum
  - `artifacts/evaluation/phase3-final-held-out-comparison-gallery.html` for
    human-readable examples
- **Out of scope:** new evaluate runs on held-out; ML clustering libraries;
  unredacted raw query text in published outputs; changing Strategy B/C logic.

#### Analysis protocol (no development / held-out tuning)

1. **Primary sample:** Strategy B (`embedding-cache`) **`false_positive_examples`**
   and **`failure_examples`** from the final held-out comparison JSON.
2. **Contrast sample:** Strategy C + Feature 1 false positives (expect empty at
   FPR `0.0`); record **`UNSAFE`** / **`UNCERTAIN`** examples where present for
   discussion only.
3. **Cluster key (deterministic):** concatenate, in order:
   `failure_category` (or `expected_decision` mismatch type),
   `metadata.domain` if present, `freshness_class`, and primary compatibility
   **rule** or reason code from trace when available. Normalize missing fields
   to **`unknown`**.
4. **Named recurring pattern:** assign a human-readable cluster label only when
   **≥ 2** examples share the same cluster key on the primary sample; otherwise
   mark **`singleton`**.
5. **Counts:** every cluster **`count`** must equal the number of example records
   grouped under that key in the source JSON (sum of counts equals primary-sample
   false-positive count).
6. **Mitigation note:** one line per named cluster — `rule`, `benchmark`, or
   `none`.

No labels or outcomes from this step may be used to change thresholds, eviction,
or validator settings.

#### Pass / fail (pre-registered)

**Pass** iff **all** hold:

- Every Strategy B held-out **`false_positive_examples`** entry appears in exactly
  one cluster or singleton row in the evidence document.
- Each cluster **`count`** is derivable from
  `phase3-final-held-out-comparison.json` (or cited WS7
  `quality_analysis.by_failure_category` where used for cross-check only).
- Output uses the project redaction conventions (no secrets; no unapproved raw
  query text — pair IDs and categories preferred).

**Fail / stopping rule:** If pass conditions are met with manual grouping,
**do not** add clustering code or a new metrics pipeline for Phase 3 v1. If
manual grouping cannot be reproduced from the frozen JSON fields, document the
gap and only then author a minimal export script in a follow-up workstream
(with a new card if behavior changes).

#### Primary metrics

| Concern | Source field / artifact |
| --- | --- |
| False positives (B) | `baselines.embedding-cache.false_positive_rate`, `false_positive_examples` |
| Safety (C) | `baselines.compatibility-cache.false_positive_rate` |
| Category strata | `statistics.by_baseline.*.strata.by_failure_category` (when attached) |
| WS7 aggregates | `workstream7-quality-analysis.json` → `quality_analysis.by_failure_category` |
| Cluster inventory | `docs/phase-3/PHASE3_FAILURE_CLUSTERS.md` (counts + keys) |

#### Baselines (discussion context)

| Arm | Role |
| --- | --- |
| Strategy B (`embedding-cache`) | Primary false-positive set to cluster |
| Strategy C + Feature 1 (`compatibility-cache` + adaptive map) | Contrast — safety at FPR `0.0` |
| WS7 consolidated quality analysis | Aggregate cross-check, not a second ground truth |

#### Effort

**S** — about **1** focused session (read JSON, write cluster table, cross-check
counts).

#### Evidence (to create at implementation time)

- [`docs/phase-3/PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md)
- Optional machine-readable export:
  `artifacts/evaluation/phase3-failure-clusters.json` (if a script is added later;
  not required for pass)

Implementation plan:
[`WORKSTREAM_7_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_7_IMPLEMENTATION_PLAN.md).

---

### Feature 5 — Experiment-tracking gate (manual audit)

**Order:** 5 · **Implementation ID:** `P3-FEAT-TRACK` (promoted from `P3-OPT-TRACK`,
2026-10-11)

#### Hypothesis

A **read-only provenance audit** of Phase 3 and Phase 4 paper artifacts can
determine whether manual JSON under `artifacts/evaluation/`, feature evidence
markdown, and the Phase 4 manifest are **sufficient** for reproducibility—
without adding MLflow, Weights & Biases, or another experiment-tracking service.

#### Scope (what this feature changes)

- **In scope:** inventory of paper-relevant results; check for required
  provenance fields; manifest path resolution; gap count; written **keep manual**
  vs **add tracker** decision.
- **Frozen:** no changes to evaluation behavior, cache code, or held-out data.
- **Audit corpus (minimum):**
  - Phase 3 final package:
    [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md),
    `artifacts/evaluation/phase3-final-held-out-comparison.json`,
    `artifacts/evaluation/phase3-paper-artifact-manifest.json` (preview manifest)
  - Phase 3 feature evidence:
    `PHASE3_FEATURE_1_EVIDENCE.md`, `PHASE3_FEATURE_2_EVIDENCE.md`,
    `PHASE3_FEATURE_3_EVIDENCE.md`, `PHASE3_ARTIFACTS_EVIDENCE.md`
  - Phase 4 manifest and tracks:
    `artifacts/evaluation/phase4-paper-artifact-manifest.json` and each
    `tracks.*.artifacts[].path` entry that exists on disk
  - Plan verification logs in
    [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) and
    [`../internal/PHASE4_IMPLEMENTATION_PLAN.md`](../internal/PHASE4_IMPLEMENTATION_PLAN.md)
- **Out of scope:** installing or configuring a tracker; rewriting historical
  artifacts; clean-checkout replay (may remain explicitly deferred).

#### Audit protocol (read-only)

For each **paper result** (held-out comparison, Pareto follow-up, provider
unavailable record, storage/scale profiles, consolidated previews):

1. Locate **command** (or generator module + documented CLI) in an evidence file
   or artifact `provenance` / report header.
2. Locate **git commit** (or explicit dirty-worktree note).
3. Locate **config** path and **SHA-256** (or `config_version` + cited hash in evidence).
4. Locate **dataset_version** and **split_manifest_sha256** (or equivalent split proof).
5. Locate **seed** / statistics block (`bootstrap_seed`, `bootstrap_iterations`,
   `confidence_level`) when the result includes uncertainty.
6. Confirm artifact **path** resolves from repo root (file exists).
7. Classify gaps:
   - **`manifest_fixable`** — missing field can be added to
     `phase4-paper-artifact-manifest.json` or evidence without new infra.
   - **`repro_blocked`** — command, commit, or config hash missing and not
     recoverable from sibling artifacts.

No tuning, no new evaluations, no held-out access.

#### Pass / fail (pre-registered)

**Audit pass (keep manual tracking)** iff **all** hold:

- Every artifact path listed in `phase4-paper-artifact-manifest.json` **tracks**
  resolves on disk (or is explicitly marked deferred with reason).
- **`repro_blocked` gap count = 0** for the audit corpus above.
- Phase 3 **final held-out** result has command, commit, config hash, dataset
  version, split-manifest hash, and seed recorded in
  [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md) and/or the comparison JSON.

**Audit fail (tracker or manifest escalation)** iff **`repro_blocked` ≥ 1** and
the gap cannot be closed by a manifest-only or evidence-only fix within one
session.

**Stopping rule:** If audit **passes**, record decision **`keep_manual`** in
this section and in evidence—**do not** add MLflow/W&B or similar dependencies
for Phase 3 v1. If audit **fails**, document the gap list and either (a) a
manifest/evidence fix plan or (b) a named tracker choice in a new decision
record—still no tracker install without explicit user OK.

#### Primary metrics

| Metric | Meaning |
| --- | --- |
| `artifacts_in_manifest` | Count of listed artifact paths |
| `artifacts_missing_on_disk` | Paths that do not resolve |
| `results_audited` | Paper results in scope |
| `manifest_fixable_gaps` | Missing provenance fixable without tracker |
| `repro_blocked_gaps` | Missing provenance not fixable without new process |
| **Decision** | `keep_manual` \| `manifest_fix_only` \| `tracker_required` |

#### Baselines

| Reference | Role |
| --- | --- |
| Phase 3 preview manifest | Historical preview; may lag final package—note in audit |
| Phase 4 manifest | Primary machine-readable index for post-Phase 3 validation |
| WS5 / internal verification logs | Cross-check commands already recorded |

#### Effort

**S** — about **1** focused session (read manifests and evidence; tabulate gaps).

#### Evidence (to create at implementation time)

- [`docs/phase-3/WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) (audit table +
  decision; not Phase 2 PostgreSQL ops WS8)
- Decision summary appended to **Feature 5 decision** subsection below after audit
- Optional: `artifacts/evaluation/phase3-tracking-audit.json` if a small script
  is added later; **not required** for pass

Implementation plan:
[`WORKSTREAM_8_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_8_IMPLEMENTATION_PLAN.md).

#### Feature 5 decision (fill after audit)

| Field | Value |
| --- | --- |
| Audit date | _pending_ |
| Decision | _pending_ (`keep_manual` expected if Phase 3/4 evidence complete) |
| `repro_blocked_gaps` | _pending_ |
| Tracker dependency added? | **no** unless audit fail + user OK |

---

### Feature 6 — Float32 embedding storage baseline

**Order:** 6 · **Implementation ID:** `P3-FEAT-EMBED-BASE` (promoted from
`P3-OPT-Q8` baseline gate, 2026-10-11)

#### Hypothesis

Replay over the **full development split** (`benchmarks/development.jsonl`) with
deterministic fake embeddings produces a float32 storage breakdown where
**embedding byte share** is measurable and sufficient to decide whether int8
quantization is worth engineering effort.

#### Scope

- **In scope:** per-entry and aggregate `embedding_bytes`, `answer_bytes`
  (or canonical answer bytes when dedup is on), metadata/query bytes,
  `total_bytes`, `entries`, embedding dimension, dtype **`float32`**
  (`4` bytes per dimension).
- **Harness:** extend or wrap [`src/sscre/storage_evaluation.py`](../src/sscre/storage_evaluation.py)
  and/or a development Strategy C replay that uses the same byte accounting as
  [`src/sscre/cache.py`](../src/sscre/cache.py) `_entry_size` (do not invent a
  second formula).
- **Workload:** development directed requests derived from development pairs
  (800 directed requests = 400 pairs × 2); record exact workload definition in
  evidence.
- **Frozen:** no held-out access; no PostgreSQL schema change in this feature;
  no quantization.
- **Out of scope:** Phase 4 four-request storage profile (too small for
  benchmark-scale claim); live-provider embeddings; production capacity claims.

#### Development protocol (measurement only)

1. Run float32 storage/replay at development scale with caps disabled or set
   high enough not to dominate the measurement (document `max_entries` /
   `max_bytes`).
2. Write `artifacts/evaluation/phase3-embedding-storage-baseline.json` including:
   `embedding_bytes`, `answer_bytes`, `metadata_bytes`, `query_bytes`,
   `total_bytes`, `embedding_share` (= `embedding_bytes / total_bytes`),
   `embedding_dimensions`, `measurement_environment`, config hash, git commit,
   dataset version, split name **`development`**.
3. Compute **`embedding_share`** at aggregate level and optionally mean per entry.

Held-out labels are not used.

#### Pass / fail (baseline complete)

**Baseline complete** iff the artifact exists and fields above are populated from
a reproducible command recorded in evidence.

**Quantization gate (authorizes Feature 7)** iff:

- **`embedding_share` ≥ `0.20`** (embeddings are at least 20% of measured
  `total_bytes`).

**Stop / defer quantization** iff **`embedding_share` < `0.20`**: record baseline
only; Feature 7 remains **not authorized** (storage win unlikely to matter).

Pre-registered thresholds (confirm before Feature 7 code; change only via written
protocol update):

| Parameter | Value |
| --- | --- |
| Dominance gate | `embedding_share` ≥ **0.20** |
| Quantization byte reduction (Feature 7) | ≥ **3.5×** vs float32 embeddings |
| Safety (Feature 7) | development `false_positive_rate` ≤ **0.0** |
| Reuse (Feature 7) | development `hit_rate` ≥ float32 reference |

#### Primary metrics

| Field | Source |
| --- | --- |
| `embedding_bytes`, `total_bytes`, `embedding_share` | baseline JSON |
| `entries`, `average_entry_bytes` | baseline JSON |
| `hit_rate`, `false_positive_rate` | optional attached dev compatibility report |

#### Baselines

| Arm | Role |
| --- | --- |
| float32 in-memory | Reference for Feature 7 |
| Phase 4 storage profile | Bounded cross-check only; not substitute for Feature 6 |

#### Effort

**M** — **1–2** sessions (harness extension if needed, one development run, tests).

#### Evidence

- [`docs/phase-3/PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md)
- `artifacts/evaluation/phase3-embedding-storage-baseline.json`

Implementation plan:
[`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md).

#### Limitation (fake embeddings)

Deterministic fake embeddings do not represent real provider vector
distributions. Feature 6–7 support **storage methodology** claims, not general
embedding accuracy, until a separately labelled real-provider embedding run exists.

---

### Feature 7 — int8 embedding quantization (conditional)

**Order:** 7 (conditional) · **Implementation ID:** `P3-FEAT-Q8`  
**Plan status:** **`not authorized`** until Feature 6 reports
**`embedding_share` ≥ `0.20`**.

#### Trigger (when to build)

Implement int8 quantize/dequantize on the embedding path **only if** Feature 6
baseline JSON satisfies the dominance gate above.

#### Stopping rule (when **not** to build)

- Feature 6 **`embedding_share` < `0.20`**
- Development **`false_positive_rate` > `0.0`** after int8 on any compared arm
- Development **`hit_rate`** below float32 reference
- Byte reduction **< 3.5×** on embedding storage
- No held-out tuning to recover a failed development compare

Default path if trigger false: report float32 baseline only ([`SSCRE_PLAN.md`](../SSCRE_PLAN.md)
§ Phase 3 quantization deferred).

#### Hypothesis (only if trigger fires)

Symmetric per-vector int8 quantization (scale derived per vector on write;
dequantize before similarity) reduces **`embedding_bytes`** by at least **3.5×**
versus float32 while preserving Strategy C **development** decisions and safety
(`false_positive_rate` ≤ **0.0**, `hit_rate` not lower than float32).

#### Scope

- **In scope:** in-memory / replay path first; quantize at store, dequantize at
  search; report max and p95 absolute cosine-similarity drift vs float32 on
  development pairs.
- **Out of scope:** pgvector schema migration in v1; custom int8 column if
  **`halfvec`** (float16) is the later PostgreSQL path; held-out evaluation for
  quantization tuning.

#### Development protocol (tuning allowed **only after trigger**)

1. Implement int8 round-trip with tests for dimension preservation and malformed
   vector failure-closed behavior.
2. Replay **development** split with float32 vs int8 embedding storage on the
   same workload as Feature 6.
3. Record decision agreement, `hit_rate`, `false_positive_rate`, similarity
   drift, and byte counts.
4. Write `artifacts/evaluation/phase3-quantization-development.json`.

#### Pass / fail (pre-registered)

**Pass** iff **all** on development:

- `embedding_bytes_int8` ≤ `embedding_bytes_float32 / 3.5`
- `false_positive_rate` ≤ **0.0** (int8 arm)
- `hit_rate` ≥ float32 reference `hit_rate`
- Documented max/p95 similarity drift (informational; no extra pass threshold
  beyond safety/reuse above)

**Fail:** keep float32; do not ship int8 in the paper stack.

#### Primary metrics

| Metric | Notes |
| --- | --- |
| `embedding_bytes`, byte ratio | vs Feature 6 baseline |
| `hit_rate`, `false_positive_rate` | Strategy C development replay |
| `similarity_drift_max`, `similarity_drift_p95` | pairwise or candidate-level sample |
| `decision_agreement_rate` | same SAFE/UNSAFE/UNCERTAIN as float32 |

#### Baselines

| Arm | Description |
| --- | --- |
| float32 (Feature 6) | Reference |
| int8 candidate | Same workload and τ policy |

#### Effort

**M** — **2–3** sessions **if triggered**; **zero** if dominance gate fails.

#### Evidence

- Same [`PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md)
- `artifacts/evaluation/phase3-quantization-development.json` (if built)

---

### Feature 8 — Simulated load ladder (1K→100K Q/day)

**Order:** 8 · **Implementation ID:** `P3-FEAT-LOAD` (promoted from
`P3-OPT-LOAD`, 2026-10-11)

#### Hypothesis

Running a **time-compressed** query ladder at **1K**, **10K**, and **100K**
simulated queries per day against Strategy C (`compatibility-cache`) identifies
the **first reproducible resource bottleneck** (embed, search, compatibility,
repository, or generation path) on local hardware—or shows **`not_reached`**
through 100K/day without claiming production capacity.

#### Scope

- **In scope:** extend [`src/sscre/load_test.py`](../src/sscre/load_test.py);
  new workload config (e.g. `experiments/phase3_load_ladder_v1.json`); in-memory
  run first, then PostgreSQL + pgvector with the **same** logical workload when
  `SSCRE_DATABASE_URL` is available.
- **Query mix:** sample from `benchmarks/development.jsonl` with a recorded
  **repeat ratio** (default **0.30**) so hits and misses are both observed.
- **Cache mode:** `compatibility-cache` at τ **0.95** or the frozen Feature 1
  adaptive map (document which arm in evidence).
- **Caps:** use configured `max_entries` / `max_bytes`; verify storage stays
  within cap at each ladder step (master-plan success criterion 7).
- **Out of scope:** multi-host, geo, 1M Q/day, production SLA, GPU; held-out
  benchmark replay; optimization work triggered by results.

#### Not substitutes (prior bounded runs)

| Prior artifact | Why not sufficient |
| --- | --- |
| [`phase4-scale-profile.json`](../phase-4/PHASE4_SCALE_EVIDENCE.md) | 32 requests, in-memory only |
| [`WORKSTREAM_8_EVIDENCE.md`](../phase-2/WORKSTREAM_8_EVIDENCE.md) `ws8-pg-load-v1` | 32 requests, bounded ops protocol |

#### Ladder definition (pre-registered)

Simulated rate → fixed **measured request count** per step (wall-clock duration
recorded; not a capacity guarantee):

| Step | Simulated Q/day | Measured requests | Default concurrency |
| --- | ---: | ---: | ---: |
| L1 | 1,000 | 200 | 4 |
| L2 | 10,000 | 2,000 | 4 |
| L3 | 100,000 | 20,000 | 8 |

Warmup requests per step: **10%** of measured count (minimum **20**). Document
actual duration, compression factor, and worker/process count in evidence.

#### Budgets (pre-registered — change only via written protocol update)

**Non-fixture errors** exclude items labeled `embedding_failure`,
`generation_failure`, or other intentional failure fixtures in the workload
config.

| Storage backend | Metric | Budget |
| --- | --- | --- |
| In-memory | `p95_end_to_end_latency_ms` | ≤ **500** |
| In-memory | `non_fixture_error_rate` | ≤ **0.01** |
| PostgreSQL | `p95_end_to_end_latency_ms` | ≤ **3000** |
| PostgreSQL | `non_fixture_error_rate` | ≤ **0.01** |
| Both | `timeout_rate` | ≤ **0.01** |
| Both | cache `total_bytes` | ≤ configured `max_cache_bytes` |

#### Bottleneck rule

At the **lowest** ladder step where a budget is **exceeded**, attribute p95 time
to components reported by the harness (`embed`, `vector_search`,
`compatibility_check`, `repository`, `generation`, `wrapper_other`). The
**first bottleneck** is the component with the largest p95 share on that step.

**Reproducibility:** two consecutive runs at the failing step must name the
**same** first bottleneck (or both conclude `not_reached` at L3).

**Stopping rule:** stop after the first reproducible bottleneck is recorded, or
after L3 with **`not_reached`** — do not add infrastructure or optimize in this
feature.

#### Protocol (no held-out tuning)

1. Implement or extend ladder config and harness fields for component timings.
2. Run L1 → L2 → L3 in-memory; write
   `artifacts/operations/phase3-load-ladder-memory.json`.
3. Repeat on PostgreSQL when available; else write
   `artifacts/operations/phase3-load-ladder-postgres.json` with
   **`status`: `unavailable`** and reason (no URL, skip, etc.).
4. Record environment: OS, CPU model, Python version, PostgreSQL version,
   process/worker counts, `measurement_environment`: **`synthetic_replay`**.

#### Pass / fail (pre-registered)

**Pass (protocol complete)** iff:

- All three in-memory ladder steps executed and artifact written.
- PostgreSQL arm **executed or explicitly marked unavailable**.
- **`first_bottleneck`** or **`not_reached`** recorded with reproducibility note.
- Every step documents cap compliance (`total_bytes` ≤ `max_cache_bytes`).
- Evidence file lists commands, config path, git commit, and budgets used.

**Fail:** incomplete ladder without documented abort reason; do not claim
bottleneck or capacity.

#### Primary metrics

| Metric | JSON / report field (harness-defined) |
| --- | --- |
| Throughput | `requests_per_second` |
| Latency | `p50_latency_ms`, `p95_latency_ms`, `p99_latency_ms` |
| Errors | `error_count`, `non_fixture_error_rate`, `timeout_count` |
| Storage | `entries`, `total_bytes`, `eviction_count` |
| Bottleneck | `first_bottleneck`, `bottleneck_step`, `component_p95_share` |

Field names must match emitted artifacts; add harness fields before claiming
numbers in the paper.

#### Baselines

| Reference | Use |
| --- | --- |
| Phase 4 in-memory profile | Context only |
| WS8 PostgreSQL 32-request load | Context only |
| Strategy C at frozen τ | Arm under test |

#### Effort

**L** — **3–4** sessions (config, harness extension, two backends, two-run
bottleneck check, evidence).

#### Evidence

- [`docs/phase-3/PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md)
- `artifacts/operations/phase3-load-ladder-memory.json`
- `artifacts/operations/phase3-load-ladder-postgres.json`

Implementation plan:
[`WORKSTREAM_6_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_6_IMPLEMENTATION_PLAN.md).

**Limitation:** Results describe **local synthetic replay** on the tested
request counts; they are **not** 1K–100K Q/day production capacity or SLA
evidence.

---

### Optional features — v1 decision (Step 5)

All former **`P3-OPT-*`** rows are **promoted** or superseded by Features 4–8.

| ID | Item | v1 decision | One-line rationale |
| --- | --- | --- | --- |
| ~~**P3-OPT-Q8**~~ | int8 embedding quantization | **Promoted** → Features 6–7 | Baseline-first gate and conditional int8. |
| ~~**P3-OPT-LOAD**~~ | Load tests 1K→100K simulated Q/day | **Promoted** → [Feature 8](#feature-8--simulated-load-ladder-1k100k-qday) | Ladder card with pre-registered budgets added 2026-10-11. |
| ~~**P3-OPT-CLUSTER**~~ | Failure clustering | **Promoted** → [Feature 4](#feature-4--failure-clustering-manual-synthesis) | Manual synthesis card added 2026-10-11; automated clustering still out of scope unless pass fails. |
| ~~**P3-OPT-TRACK**~~ | Experiment tracking | **Promoted** → [Feature 5](#feature-5--experiment-tracking-gate-manual-audit) | Manual audit gate added 2026-10-11; MLflow/W&B only if audit fails and user approves. |

**Registry (2026-10-11):** Workstream 1 optional promotions complete (Features 4–8).

---

## Recommended implementation order (confirmed Step 6)

Execution order for Phase 3 code and evaluation (matches P0-P3-ORDER):

| Step | Feature / gate | Plan reference | Ship criterion |
| ---: | --- | --- | --- |
| 1 | Adaptive per-domain thresholds | [Feature 1](#feature-1--adaptive-per-domain-thresholds) | Feature 1 pass/fail on held-out |
| 2 | Pattern-aware eviction | [Feature 2](#feature-2--pattern-aware-eviction) | Feature 2 pass/fail on held-out |
| 3 | Strategy D (cross-encoder) | [Feature 3](#feature-3--strategy-d-cross-encoder-validator) | **Only if** trigger fires; else skip |
| 4 | Failure clustering (manual) | [Feature 4](#feature-4--failure-clustering-manual-synthesis) | Analysis pass on frozen JSON |
| 5 | Experiment-tracking gate | [Feature 5](#feature-5--experiment-tracking-gate-manual-audit) | Audit pass → `keep_manual` |
| 6 | Float32 embedding storage baseline | [Feature 6](#feature-6--float32-embedding-storage-baseline) | Baseline JSON + dominance gate |
| 7 | int8 quantization | [Feature 7](#feature-7--int8-embedding-quantization-conditional) | **Only if** Feature 6 gate ≥ 20% share |
| 8 | Simulated load ladder | [Feature 8](#feature-8--simulated-load-ladder-1k100k-qday) | Bottleneck or `not_reached` at L3 |

Extended features 4–8 follow the v1 stack (Features 1–3); see Workstream 1 registry in [`WORKSTREAM_1_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_1_IMPLEMENTATION_PLAN.md).

Do not start step 2 until step 1 evidence is recorded under [Implementation progress](#implementation-progress).
Do not invoke step 3 unless [Feature 3 trigger](#trigger-when-to-build-d) is satisfied on the
**final** Phase 3 stack held-out report.

---

## Paper artifacts (execution outline — Step 6)

**v1 status:** Step 4 preview and Step 5 final held-out package recorded 2026-10-10
([`PHASE3_ARTIFACTS_EVIDENCE.md`](./PHASE3_ARTIFACTS_EVIDENCE.md),
[`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md)). Extended registry
(Features 4–8) closed 2026-10-11 per
[`WORKSTREAM_1_STEP7_CLOSE.md`](./WORKSTREAM_1_STEP7_CLOSE.md). Each row below links
to figures/tables in the paper draft.

### 3.1 Tables and figures (deliverables)

| Deliverable | Source artifacts (planned names) | WS5 / Phase 3 command hook |
| --- | --- | --- |
| Main results table (A/B/C + Phase 3 stack) | `phase3-final-held-out-comparison.json` | `sscre.evaluate --baseline all --split held-out --production` (extend config for Phase 3 policies) |
| Development operating point / sweeps | `phase3-development-sweep.json` | `sscre.evaluate` on `benchmarks/development.jsonl` |
| Pareto (coverage vs FPR) | `phase3-held-out-pareto.json` | `sscre.pareto --development-sweep … --held-out-benchmark benchmarks/held_out_test.jsonl` |
| Domain-stratified thresholds | `phase3-adaptive-threshold-map.json` + strata in comparison JSON | `sscre.evaluate --adaptive-threshold-map-output` (development) + `--adaptive-threshold-map` (held-out) — [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md) |
| Freshness / eviction slice | `phase3-held-out-eviction.json`, WS6 conservative reference | `sscre.phase3_eviction` (Feature 2 candidate; not in shipped stack) — [`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md) |
| Ablations (C @ 0.95, +F1, +F2, +F1+F2, +D if built) | One JSON per ablation under `artifacts/evaluation/phase3-ablation-*.json` | Repeated held-out evaluate with feature flags documented in evidence |
| Failure discussion gallery | `phase3-final-held-out-comparison-gallery.html` | `sscre.gallery_export` ([`benchmarks/README.md`](../../benchmarks/README.md)) |

### 3.2 Statistics and protocol (deliverables)

| Requirement | Record in final evidence |
| --- | --- |
| Bootstrap / Wilson CIs | `statistics.by_baseline.*` in comparison JSON; `bootstrap_seed` **`42`**, `bootstrap_iterations` **`1000`**, `confidence_level` **`0.95`** from config unless feature card documents a change |
| Single final held-out run | One row in evidence: `git_commit`, config SHA-256 (`experiments/evaluation_config.json`), `dataset_version`, `split_manifest_sha256` from validate, UTC timestamp |
| Limitations paragraph | Pull from [Limitations (source material)](#limitations-source-material) + Feature pass/fail outcomes (D deferred, OPT deferrals, WS6 held-out scope) |

**Held-out discipline:** one **final** held-out comparison for the paper stack after Features
1–2 (and D if built). Development splits used for all tuning and ablation exploration only.

### 3.3 Reproducibility runbook (recorded commands)

No `make paper-results` target exists. Canonical v1 commands live in feature
evidence files; summary below (from repo root, `$env:PYTHONPATH='src'` on Windows):

```powershell
# 0. Gate
python -m pip install ".[dev]"
python -m sscre.benchmark_validate --phase2 --production
python -m pytest -q

# 1. Feature 1 — development map + held-out replay
python -m sscre.evaluate --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --baseline compatibility-cache --split development --production --adaptive-threshold-map-output artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-adaptive-development.json

python -m sscre.evaluate --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --baseline compatibility-cache --split held-out --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-adaptive-held-out.json

# 2. Feature 2 — eviction candidate (deferred from shipped stack; optional replay)
python -m sscre.phase3_eviction --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --split development --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-development-eviction.json --policy-output artifacts/evaluation/phase3-pattern-eviction-policy.json

python -m sscre.phase3_eviction --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --split held-out --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --selected-policy artifacts/evaluation/phase3-pattern-eviction-policy.json --output artifacts/evaluation/phase3-held-out-eviction.json

# 3. Final held-out package (single paper stack — include conservative freshness + frozen map)
python -m sscre.evaluate --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --baseline all --split held-out --production --freshness-policy conservative --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-final-held-out-comparison.json

python -m sscre.gallery_export artifacts/evaluation/phase3-final-held-out-comparison.json -o artifacts/evaluation/phase3-final-held-out-comparison-gallery.html
```

Full provenance (commit, config hash, protocol reset):
[`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md).
Preview manifest generator: `python -m sscre.phase3_artifacts` — [`PHASE3_ARTIFACTS_EVIDENCE.md`](./PHASE3_ARTIFACTS_EVIDENCE.md).

Baseline WS5 regeneration commands remain documented in
[`WORKSTREAM_5_EVIDENCE.md`](../phase-2/WORKSTREAM_5_EVIDENCE.md) for pre–Phase 3 comparison
only; do not substitute for the final `phase3-final-*` artifacts in the paper.

### 3.4 Execution checklist (gate before paper draft)

- [ ] **Main results table** — per strategy: hit rate, false-reuse rate, estimated cost
  savings, p50/p95 latency (development vs held-out clearly labeled).
- [ ] **Threshold sweeps / Pareto curves** — overall and by domain where adaptive
  thresholds apply.
- [ ] **Freshness / eviction slice** — stale exposure vs reuse if eviction policy changes.
- [ ] **Ablations** — each Phase 3 feature alone vs full stack vs Strategy C at `0.95`.
- [ ] **Statistics** — bootstrap (or documented binomial) CIs; fixed seeds recorded.
- [ ] **Single final held-out run** — config hash, git commit, dataset version logged once.
- [ ] **Reproducibility runbook** — commands above verified exit 0; copied into evidence file.
- [ ] **Outputs** under `artifacts/evaluation/` with `phase3-*` names tied to this plan version.

### Headline numbers (do not check until final held-out artifacts exist)

- [ ] Held-out hit rate at selected operating point (Strategy C or best Phase 3 stack).
- [ ] Held-out false-reuse / false-positive rate with 95% CI.
- [ ] Estimated token or cost savings vs no-cache at same quality constraint.
- [ ] p95 latency delta cache-hit vs miss (`synthetic_replay` unless P2-PROV promoted).

---

## Limitations (source material)

Draft paper limitations from evidence, not placeholders:

- **Provider:** `synthetic_replay` only — [`WORKSTREAM_5_EVIDENCE.md`](../phase-2/WORKSTREAM_5_EVIDENCE.md) § provider limitations.
- **Labels:** Human factual-correctness sparse / `not_collected` where applicable —
  **P0-LABELS**; compatibility-focused safety claims.
- **Ops:** Bounded local WS8 package
  ([`WORKSTREAM_8_EVIDENCE.md`](../phase-2/WORKSTREAM_8_EVIDENCE.md)):
  simulated failure-closed; two processes both generate; load bottleneck
  `not_reached`. Live restart and capacity remain unsupported. Phase 1 lite:
  [`WORKSTREAM_8_OPS_LITE_EVIDENCE.md`](../phase-2/WORKSTREAM_8_OPS_LITE_EVIDENCE.md).
- **Freshness held-out:** WS6 semi/dynamic held-out scope unavailable — see WS6 evidence.

---

## Frozen baseline inventory (Step 0 record)

Authoring branch and read-only verification (2026-10-09). Metric values in this section
cite artifact paths only.

| Item | Record |
| --- | --- |
| Authoring branch | `phase2/phase3-plan` (from `phase1/carryovers` tip) |
| Branch base commit | `17e117f4eb2492c36bafe2b3f52a06777cefd042` |
| Benchmark validate | `python -m sscre.benchmark_validate --phase2 --production` → passed; `split_manifest_sha256=68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51` |
| Phase 0 decisions | [`PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md`](../internal/PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md) — P0-P3-ORDER, P0-PROVIDER (defer live), P0-LABELS (out of scope), P0-PHASE3-DOC |
| Phase 1 carryovers | [`PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md`](../internal/PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md) — closed; P2-CI GitHub green may remain push-gated |
| WS6 context (eviction card) | [`WORKSTREAM_6_EVIDENCE.md`](../phase-2/WORKSTREAM_6_EVIDENCE.md) |
| Gallery / clustering optional | [`benchmarks/README.md`](../../benchmarks/README.md) (`sscre.gallery_export`) |

**Phase 0 constraints embedded in this plan:** P0-PROVIDER and P0-LABELS under **Non-goals**
and **Limitations**; P2-DASH, P2-DUAL, and 1K–100K / capacity claims under
**Non-goals**. Bounded WS8 PostgreSQL evidence is cited, not treated as Phase 3
load.

---

## Implementation progress

### Feature 1 — adaptive per-domain thresholds

**Status:** implemented and passed pre-registered evaluation on 2026-10-10.

- Implementation: `src/sscre/baseline.py`, `src/sscre/evaluate.py`
- Tests: `tests/test_adaptive_thresholds.py`
- Evidence: [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md)
- Development map: `artifacts/evaluation/phase3-adaptive-threshold-map.json`
- Development report: `artifacts/evaluation/phase3-adaptive-development.json`
- Held-out report: `artifacts/evaluation/phase3-adaptive-held-out.json`
- Decision: **pass** — adaptive held-out `hit_rate=0.002325581395348837` and
  `false_positive_rate=0.0`; frozen global Strategy C reference was
  `hit_rate=0.0` and `false_positive_rate=0.0`.

See [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md) for the git commit
and dirty-worktree state at run time.

### Feature 2 — pattern-aware eviction

**Status:** implemented and evaluated; **failed pass criterion and deferred from the
shipped stack** on 2026-10-10.

- Implementation: `src/sscre/cache.py`, `src/sscre/baseline.py`,
  `src/sscre/phase3_eviction.py`
- Tests: `tests/test_cache_eviction.py`
- Development policy: `artifacts/evaluation/phase3-pattern-eviction-policy.json`
- Development report: `artifacts/evaluation/phase3-development-eviction.json`
- Held-out report: `artifacts/evaluation/phase3-held-out-eviction.json`
- Decision: **fail/defer** — FPR and stale exposure were `0.0`, but pattern-aware
  eviction did not improve hit rate or safe-reuse coverage over default eviction at
  the same `entry_cap=1`.

The paper stack retains the Feature 1 adaptive threshold map with default/WS6
conservative eviction. No held-out retuning was performed.

### Feature 3 — Strategy D conditional validator

**Status:** deferred on 2026-10-10; the pre-registered trigger did not fire.

- Evidence: [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md)
- Retained stack held-out FPR: `0.0`
- Trigger: held-out FPR `> 0.0`
- Decision: no cross-encoder implementation, protocol reset, or additional held-out
  run.

### Step 4 — paper artifact preview package

**Status:** generated on 2026-10-10; final selected-stack held-out package remains
Step 5.

- Evidence: [`PHASE3_ARTIFACTS_EVIDENCE.md`](./PHASE3_ARTIFACTS_EVIDENCE.md)
- Generator: `src/sscre/phase3_artifacts.py`
- Outputs: `artifacts/evaluation/phase3-paper-artifact-manifest.json`,
  `phase3-results-preview.json`, `phase3-ablations.json`,
  `phase3-domain-threshold-curves.json`, and `phase3-pareto-reference.json`.
- Preview gallery: `artifacts/evaluation/phase3-adaptive-held-out-gallery.html`
- The selected-stack Pareto and final results table are intentionally deferred
  until the single Step 5 held-out run.

### Step 5 — final held-out package

**Status:** completed on 2026-10-10.

- Evidence: [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md)
- Final comparison: `artifacts/evaluation/phase3-final-held-out-comparison.json`
- Final gallery: `artifacts/evaluation/phase3-final-held-out-comparison-gallery.html`
- Retained stack: Feature 1 adaptive thresholds with default/WS6 conservative
  eviction; Feature 2 and Strategy D deferred.
- The final run recorded commit, dirty-worktree state, config hash, dataset version,
  split-manifest hash, UTC timestamp, and evaluation statistics configuration.
