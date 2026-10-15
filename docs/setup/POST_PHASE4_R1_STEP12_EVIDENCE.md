# Post–Phase 4 stabilization — Research track R1 Step 1.2 (bounded Gate C provider)

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [`POST_PHASE4_R1_STEP11_EVIDENCE.md`](./POST_PHASE4_R1_STEP11_EVIDENCE.md)  
**Status:** `deferred (Gate C live not authorized)` — unavailable artifact recorded; live-run tasks unchecked  
**Machine-readable:** [`../../artifacts/stabilization/r1-step12-provider-measurement.json`](../../artifacts/stabilization/r1-step12-provider-measurement.json)

## Gate C authorization

| Check | Result |
| --- | --- |
| Operator approval on file | **Deferred** — [`r1-step12-gate-c-approval.json`](../../artifacts/stabilization/r1-step12-gate-c-approval.json) |
| Live opt-in (`SSCRE_REAL_PROVIDER_LIVE`) | **Not set** in verification environment |
| Credentials | **Not configured** (fail-closed) |

No synthetic or fake-provider measurements were substituted.

## Reproduce (default — deferred unavailable record)

```powershell
$env:PYTHONPATH = "src"
$env:SSCRE_PROVIDER_PRICING_JSON = "experiments/real_provider_pricing.json"
python scripts/r1_step12_provider_measure.py
```

Bounded live run when Gate C is authorized (secrets out of band):

```powershell
$env:PYTHONPATH = "src"
$env:SSCRE_REAL_PROVIDER = "true"
$env:SSCRE_REAL_PROVIDER_LIVE = "true"
$env:SSCRE_R1_GATE_C_APPROVED = "true"
$env:SSCRE_PROVIDER_CREDENTIAL = "<secret>"
# ... SSCRE_PROVIDER_* per docs/setup/PROVIDER_BOUNDARY.md
$env:SSCRE_PROVIDER_PRICING_JSON = "experiments/real_provider_pricing.json"
python scripts/r1_step12_provider_measure.py --max-records 5
```

Use `--full-development` only with explicit quota approval (measures all filtered development pairs).

## Verification

- [x] `python -m pytest tests/test_r1_provider_run.py tests/test_provider_measure.py -q` → **7 passed** (2026-10-15)
- [x] Artifact written with `headline_population: false` and inner `live_opt_in_missing` unavailable measurement

## Population

- **Split:** `benchmarks/development.jsonl` (383 pairs after P4 population filter)
- **Default bound:** 5 records (10 remote calls: embed + generate each) when live is enabled
- **Not** fresh held-out headline evidence

## Acceptance (R1.2)

- [x] Reproducible checked-in command and configuration; secrets out of band
      (unavailable path; live run still unchecked).
- [x] Provider/cost fields present on unavailable path (`null` / `unavailable`, not fabricated)
- [x] Results kept separate from R1.1 diagnosis and WS5 headline gate (explicit flags in JSON)
- [ ] Live measurement complete enough to decide that a fresh evaluation can
      proceed (Gate C live still required for that decision)
