# Post–Phase 4 stabilization — Research track R1 Step 1.1 (Strategy C diagnosis)

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Status:** `closed (diagnosis recorded)` — development-split diagnosis only (not headline); Research track R1 is not closed (Gate C live still deferred)  
**Machine-readable:** [`../../artifacts/stabilization/r1-step11-strategy-c-diagnosis.json`](../../artifacts/stabilization/r1-step11-strategy-c-diagnosis.json)

## Population

| Field | Value |
| --- | --- |
| Split | `benchmarks/development.jsonl` (383 directed-replay pairs after P4 population filter) |
| Held-out used | **No** |
| Purpose | Diagnose Strategy C abstention; **not** fresh headline evidence |

## Reproduce

Aggregate from the frozen Phase 4 development comparison artifact (default):

```powershell
$env:PYTHONPATH = "src"
python scripts/r1_step11_strategy_c_diagnosis.py
```

Optional full replay (slower; requires local embedding deps when configured):

```powershell
$env:PYTHONPATH = "src"
python scripts/r1_step11_strategy_c_diagnosis.py --replay
```

## Verification

- [x] `python -m pytest tests/test_r1_strategy_c_diagnosis.py -q` → **4 passed**
- [x] Diagnosis export written to `artifacts/stabilization/r1-step11-strategy-c-diagnosis.json`

## Dominant findings (development, Strategy C @ threshold 0.9)

- **Low reuse is not primarily empty retrieval:** 383/383 observed `b_to_a` requests had candidates; **1** `semantic_miss` at request level.
- **Rejections are rule- and threshold-driven:** trace reasons dominated by **`similarity_below_threshold`** (1737 traces) and **`missing_*_evidence`** (123 categorized traces), not by absent candidates.
- **Failure categories (request-level):** `all candidates were incompatible` (592) and `no candidate had sufficient compatibility evidence` (171).
- **Exact vs semantic (Strategy A vs C on same replay package):** exact-cache **55** hits vs compatibility-cache **2** SAFE serves on 766 directed requests — semantic path rarely converts retrieval to SAFE under current rules.
- **Unlabeled candidate reuse:** **0** hits recorded.

No compatibility thresholds or safety rules were changed during this step.

## Acceptance (R1.1)

- [x] Dominant abstention causes identified (see JSON `dominant_abstention_causes` and aggregates).
- [x] Report is explicitly non-headline (`headline_population: false`).
- [x] No safety weakening; diagnostic-only note in artifact.
