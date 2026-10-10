# SSCRE Phase 3 implementation plan

**Status:** `implementation-complete` — final held-out package recorded 2026-10-10;
Feature 2 and Strategy D are deferred by their gates; selected-stack Pareto remains
deferred to avoid an additional held-out run. Authoring closed 2026-10-09 per
[`PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md)
Step 7; implementation was explicitly requested in chat on 2026-10-10.

**Last updated:** 2026-10-10 (Step 6 closure)
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
- Held-out comparison including `compatibility-cache` + D arm (exact CLI flags TBD in evidence)
- Trace examples in failure gallery for validator-blocked vs served cases

---

### Optional features — v1 decision (Step 5)

No optional item receives a full feature card for Phase 3 v1. Each remains **deferred**
until the in-scope stack (Features 1–2, conditional 3) is measured on the final held-out
run. Promoting any row requires a new card (hypothesis + pass/fail) in this document.

| ID | Item | v1 decision | One-line rationale |
| --- | --- | --- | --- |
| **P3-OPT-Q8** | int8 embedding quantization | **Defer (v2)** | Measure float32 **`total_bytes`** / storage pairing baseline first ([`SSCRE_PLAN.md`](../SSCRE_PLAN.md) § Phase 3); quantization does not unblock paper safety/reuse claims. |
| **P3-OPT-LOAD** | Load tests 1K→100K simulated Q/day | **Defer (v2)** | WS8 recorded a 32-request local PostgreSQL run, not this protocol ([`WORKSTREAM_8_EVIDENCE.md`](../phase-2/WORKSTREAM_8_EVIDENCE.md)). Run only after the main Pareto story is stable and a new scale protocol is approved. |
| **P3-OPT-CLUSTER** | Failure clustering from gallery exports | **Defer (code)**; **paper OK (manual)** | Phase 1 gallery export exists ([`benchmarks/README.md`](../../benchmarks/README.md)); v1 may **manually** group `failure_gallery` / category strata for discussion **without** new clustering code or experiment infra. |
| **P3-OPT-TRACK** | Experiment tracking (MLflow/W&B/etc.) | **Defer (v2)** | Manual JSON under `artifacts/evaluation/` + plan verification log sufficient for v1; add tracking only if artifact sprawl blocks reproducibility. |

**Default recommendation (confirmed):** defer **P3-OPT-Q8** and **P3-OPT-LOAD** until the
core safety/reuse narrative is frozen on held-out (transition § 2.3).

---

## Recommended implementation order (confirmed Step 6)

Execution order for Phase 3 code and evaluation (matches P0-P3-ORDER):

| Step | Feature / gate | Plan reference | Ship criterion |
| ---: | --- | --- | --- |
| 1 | Adaptive per-domain thresholds | [Feature 1](#feature-1--adaptive-per-domain-thresholds) | Feature 1 pass/fail on held-out |
| 2 | Pattern-aware eviction | [Feature 2](#feature-2--pattern-aware-eviction) | Feature 2 pass/fail on held-out |
| 3 | Strategy D (cross-encoder) | [Feature 3](#feature-3--strategy-d-cross-encoder-validator) | **Only if** trigger fires; else skip |
| — | Optional infra (quantization, load, tracking) | [Optional features](#optional-features--v1-decision-step-5) | **Deferred** until core story stable |

Do not start step 2 until step 1 evidence is recorded under [Implementation progress](#implementation-progress).
Do not invoke step 3 unless [Feature 3 trigger](#trigger-when-to-build-d) is satisfied on the
**final** Phase 3 stack held-out report.

---

## Paper artifacts (execution outline — Step 6)

Planning complete; **deliverables remain unchecked** until Phase 3 implementation runs.
Each row links to figures/tables in the paper draft.

### 3.1 Tables and figures (deliverables)

| Deliverable | Source artifacts (planned names) | WS5 / Phase 3 command hook |
| --- | --- | --- |
| Main results table (A/B/C + Phase 3 stack) | `phase3-final-held-out-comparison.json` | `sscre.evaluate --baseline all --split held-out --production` (extend config for Phase 3 policies) |
| Development operating point / sweeps | `phase3-development-sweep.json` | `sscre.evaluate` on `benchmarks/development.jsonl` |
| Pareto (coverage vs FPR) | `phase3-held-out-pareto.json` | `sscre.pareto --development-sweep … --held-out-benchmark benchmarks/held_out_test.jsonl` |
| Domain-stratified thresholds | `phase3-adaptive-threshold-map.json` + strata in comparison JSON | Feature 1 tooling (TBD) + statistics attachment |
| Freshness / eviction slice | `phase3-held-out-eviction.json`, WS6 conservative reference | `sscre.freshness_evaluate` with frozen policy + cap (Feature 2) |
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

### 3.3 Reproducibility runbook (planned entry point)

No `make paper-results` target exists yet. **Planned** end-to-end sequence (fill exact flags
when Phase 3 CLIs land; record in `docs/phase-3/PHASE3_EVIDENCE.md` or equivalent):

```powershell
# 0. Gate — from repo root
python -m pip install ".[dev]"
python -m sscre.benchmark_validate --phase2 --production
python -m pytest -q

# 1. Feature 1 — development τ map (TBD module flags)
# python -m sscre.evaluate ... --split development --output artifacts/evaluation/phase3-development-sweep.json
# → artifacts/evaluation/phase3-adaptive-threshold-map.json

# 2. Feature 2 — development eviction selection (TBD)
# python -m sscre.freshness_evaluate ... --output artifacts/evaluation/phase3-development-eviction.json

# 3. Final held-out package (single paper run)
python -m sscre.evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all --split held-out --production `
  --output artifacts/evaluation/phase3-final-held-out-comparison.json

python -m sscre.pareto `
  --development-sweep artifacts/evaluation/phase3-development-sweep.json `
  --held-out-benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --output artifacts/evaluation/phase3-held-out-pareto.json

python -m sscre.freshness_evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --split held-out --production `
  --selected-policy artifacts/evaluation/phase3-development-eviction.json `
  --output artifacts/evaluation/phase3-held-out-eviction.json

python -m sscre.gallery_export `
  artifacts/evaluation/phase3-final-held-out-comparison.json `
  -o artifacts/evaluation/phase3-final-held-out-comparison-gallery.html
```

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

The implementation remains uncommitted. Feature 2 must not start until this evidence
has been reviewed and the Feature 1 slice is accepted.

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
