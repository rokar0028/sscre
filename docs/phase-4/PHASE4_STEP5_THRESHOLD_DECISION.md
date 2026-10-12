# Phase 4 Step 5 — Development threshold decision (`P4-SEMVALID`)

**Artifact:**
[`artifacts/evaluation/phase4-semantic-validity-development.json`](../../artifacts/evaluation/phase4-semantic-validity-development.json)  
**Config:** `semantic-validity-evaluation-config-1.0` (`cf238079…`)  
**Population:** development primary headline (383 pair records after `context_required` exclusion)  
**Embedding:** `sentence-transformers/all-MiniLM-L6-v2`, 384-dim, CPU, L2-normalized  
**Held-out influence:** none (`held_out_influence: none`)

## Threshold grid and rule

- Grid: `0.8`, `0.9`, `0.95` (frozen protocol).
- Cap: `max_false_positive_rate = 0.0` on labeled `b_to_a` reuse.
- Rule: maximize safe-reuse coverage among eligible thresholds; if none eligible,
  fall back to least labeled FPR, then higher safe-reuse coverage, then higher
  threshold (`select_embedding_threshold`). Thresholds with unknown labeled FPR
  (`no_labeled_reuse_hits`) are **ineligible** for the cap (fail-closed).

## Development sweep outcome

- `threshold_selection.constraint_satisfied`: **false** (no grid point met FPR ≤ 0.0 on
  labeled embedding-cache reuse).
- **Selected operating threshold:** **0.9** (fallback diagnostic point for replay
  arms B and C in the development artifact).
- This selection is **not** a safety approval; it records the frozen rule outcome on
  development data only.

## Development arm snapshot (primary population)

| Arm | hit_rate (approx) | safe_reuse_coverage | labeled FPR | unlabeled reuse hits |
| --- | --- | --- | --- | --- |
| exact-cache (A) | 0.072 | 0.033 | 0.0 (5 labeled safe) | 12 |
| embedding-cache (B) | 0.240 | 0.473 | 0.349 | 22 |
| compatibility-cache (C) | 0.003 | 0.000 | 1.0 (2 unsafe labeled) | 0 |

## Implications

- Development replay with real embeddings shows B/C behavior unlike fake-embedding
  history; C is highly abstaining/conservative on this population at τ=0.9.
- Pre-registered headline gate remains on a **fresh held-out** population (deferred).
- Do not tune τ using held-out outcomes; any revision requires a protocol version bump.
