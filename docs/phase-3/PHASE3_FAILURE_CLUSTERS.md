# Phase 3 failure clustering evidence

**Workstream:** 7 (Feature 4 — `P3-FEAT-CLUSTER`)  
**Plan:** [`WORKSTREAM_7_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_7_IMPLEMENTATION_PLAN.md)  
**Status:** **closed** (Feature 4 pass, 2026-10-11). Workstream 7 Steps 1–5 complete.

Analysis-only on frozen JSON. No held-out replay, policy retuning, or product
code changes.

**Measurement:** `synthetic_replay`, held-out split, final paper stack
([`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md)).

## Pre-code checklist (Step 1)

Recorded before extracting the primary sample (chat: implement Step 1).

- [x] Feature 4 card in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- [x] Implementation ID `P3-FEAT-CLUSTER` matches Workstream 7 in
      [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md).
- [x] Frozen input exists:
      `artifacts/evaluation/phase3-final-held-out-comparison.json`.
- [x] Supplementary input exists:
      `artifacts/evaluation/workstream7-quality-analysis.json` (gallery join,
      Step 2).
- [x] No evaluate rerun, threshold/eviction change, or clustering dependency.

## Step 1 — primary sample (Strategy B)

**Source artifact (read-only):**
`artifacts/evaluation/phase3-final-held-out-comparison.json`

**Path:** `baselines.embedding-cache.false_positive_examples`

### Report provenance (from artifact)

| Field | Value |
| --- | --- |
| `git_commit` | `fe68ce3b3cc6cdc35507e8faebbea5549ce5b50e` |
| `config_sha256` | `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8` |
| `config_version` | `evaluation-config-1.0` |
| `evaluation_split` | `held-out` |
| `execution_timestamp` | `2026-10-10T14:19:09.179172+00:00` |
| `git_worktree_dirty` | `false` |
| Dataset (per baseline block) | `reviewed-query-pairs-2.0` |

Final package context: [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md).

### Strategy B summary

| Metric | Value |
| --- | ---: |
| `false_positive_rate` | `0.48148148148148145` |
| `false_positive_examples` count | **13** |

### Strategy C contrast (same artifact; not part of Step 1 denominator)

| Metric | Value |
| --- | ---: |
| `false_positive_rate` | `0.0` |
| `false_positive_examples` count | **0** |

Clustering in later steps applies only to the Strategy B primary sample above.

### Sanity command (Step 1)

```powershell
$env:PYTHONPATH='src'
python -c "import json; p='artifacts/evaluation/phase3-final-held-out-comparison.json'; d=json.load(open(p,encoding='utf-8')); b=d['baselines']['embedding-cache']; c=d['baselines']['compatibility-cache']; print({'b_examples':len(b.get('false_positive_examples',[])),'b_fpr':b.get('false_positive_rate'),'c_examples':len(c.get('false_positive_examples',[])),'c_fpr':c.get('false_positive_rate'),'git_commit':d.get('git_commit'),'config_sha256':d.get('config_sha256')})"
```

**Output (2026-10-11, current checkout):**

```text
{'b_examples': 13, 'b_fpr': 0.48148148148148145, 'c_examples': 0, 'c_fpr': 0.0, 'git_commit': 'fe68ce3b3cc6cdc35507e8faebbea5549ce5b50e', 'config_sha256': '5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8'}
```

Evidence extraction commit at run time: `e3363cfdebed9d9f0734e3b9458fdfede8ac199c`
(doc-only; artifact bytes unchanged).

### Primary sample inventory

Each row is one `false_positive_examples` record. Identifiers only (no raw
query text).

| # | `id` | `direction` | `similarity` |
| ---: | --- | --- | ---: |
| 1 | `pair-0036` | `b_to_a` | `1.0` |
| 2 | `pair-0066` | `b_to_a` | `1.0` |
| 3 | `pair-0096` | `b_to_a` | `1.0` |
| 4 | `pair-0161` | `b_to_a` | `1.0` |
| 5 | `pair-0276` | `b_to_a` | `1.0` |
| 6 | `pair-0311` | `b_to_a` | `1.0` |
| 7 | `pair-0316` | `b_to_a` | `1.0` |
| 8 | `pair-0356` | `b_to_a` | `1.0` |
| 9 | `pair-0367` | `b_to_a` | `0.9679014703323522` |
| 10 | `pair-0481` | `b_to_a` | `1.0` |
| 11 | `pair-0503` | `b_to_a` | `1.0` |
| 12 | `pair-0543` | `b_to_a` | `0.9707104524260532` |
| 13 | `pair-0601` | `b_to_a` | `0.9999999999999999` |

All 13 examples use direction `b_to_a`.

## Step 2 — cluster keys

**Join source (read-only):**
`artifacts/evaluation/workstream7-quality-analysis.json` →
`failure_gallery.embedding_only_false_positives[]`

**Join key:** `(id, direction)` on the Step 1 primary sample.

**Deterministic cluster key** (Feature 4 order, `|` separator):

`failure_category` · `metadata.domain` · `freshness_class` · rule/reason code

Missing fields → `unknown`. Gallery rows for these false positives expose
`failure_category` and `mitigation` only; `metadata.domain`, `freshness_class`,
and explicit rule codes are absent, so those key segments are `unknown` for
all 13 rows. Rule codes were not inferred from free-text `reason` fields.

**Key granularity note:** Clusters stratify by reviewed `failure_category`
only on this artifact. Finer keys (domain, freshness, rule) would require those
fields on the joined gallery or comparison rows, not a new held-out replay.

**Join outcome:** 13 / 13 primary examples matched; 0 missing or duplicate
joins.

Evidence extraction commit: `e3363cfdebed9d9f0734e3b9458fdfede8ac199c`.

### Per-example assignment

| `id` | `direction` | Cluster key | Label |
| --- | --- | --- | --- |
| `pair-0036` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0066` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0096` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0161` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0276` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0311` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0316` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0356` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0481` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0601` | `b_to_a` | insufficient_evidence · unknown · unknown · unknown | recurring |
| `pair-0367` | `b_to_a` | intent_mismatch · unknown · unknown · unknown | recurring |
| `pair-0503` | `b_to_a` | intent_mismatch · unknown · unknown · unknown | recurring |
| `pair-0543` | `b_to_a` | constraint_mismatch · unknown · unknown · unknown | singleton |

### Named clusters (≥ 2 examples) and singletons

| Human label | Cluster key | Count | Mitigation | Source rationale |
| --- | --- | ---: | --- | --- |
| Reviewed: insufficient evidence | insufficient_evidence · unknown · unknown · unknown | 10 | `rule` | `compatibility_validator` (gallery) |
| Reviewed: intent mismatch | intent_mismatch · unknown · unknown · unknown | 2 | `rule` | `compatibility_validator` (gallery) |
| Reviewed: constraint mismatch (singleton) | constraint_mismatch · unknown · unknown · unknown | 1 | `rule` | `compatibility_validator` (gallery) |

Mitigation mapping: gallery value `compatibility_validator` → paper bucket
**`rule`** (compatibility / validator path). Not retuned from this analysis.

## Step 3 — cross-check counts

**Date:** 2026-10-11  
**Evidence commit:** `e3363cfdebed9d9f0734e3b9458fdfede8ac199c` (read-only checks).

### One-to-one assignment

| Check | Result |
| --- | --- |
| Primary `false_positive_examples` length | **13** |
| Unique `(id, direction)` in primary | **13** |
| Rows in Step 2 assignment table | **13** |
| Each primary example in exactly one cluster/singleton | **pass** (13 / 13) |

### Cluster sum vs Strategy B denominator

| Cluster (Step 2) | Count |
| --- | ---: |
| insufficient_evidence · unknown · unknown · unknown | 10 |
| intent_mismatch · unknown · unknown · unknown | 2 |
| constraint_mismatch · unknown · unknown · unknown | 1 |
| **Sum** | **13** |

Sum equals `len(baselines.embedding-cache.false_positive_examples)` and
Strategy B `false_positive_rate` denominator for listed examples (**13**).

### Gallery join cross-check

| Check | Result |
| --- | --- |
| `failure_gallery.embedding_only_false_positives` length | **13** |
| Unique gallery `(id, direction)` | **13** |
| Primary keys missing from gallery | **0** |
| Duplicate gallery keys | **0** |
| Gallery keys not in primary sample | **0** |

Gallery `failure_category` totals on the **same 13 keys**: insufficient_evidence
**10**, intent_mismatch **2**, constraint_mismatch **1** — matches cluster
counts.

### WS7 / statistics (cross-check only)

Do **not** treat these as a second false-positive inventory:

| Source | Field | Note |
| --- | --- | --- |
| `workstream7-quality-analysis.json` → `quality_analysis.by_failure_category.*.sample_count` | stratum size (all directed requests with that reviewed category) | e.g. insufficient_evidence **11**, intent_mismatch **56** — not FP counts |
| `phase3-final-held-out-comparison.json` → `statistics.by_baseline.embedding-cache.strata.by_failure_category.*.proportions.false_positive_rate.n` | Wilson/binomial **n** for FPR within stratum | e.g. intent_mismatch **7**, constraint_mismatch **4** — not equal to FP example rows in that category (**2** and **1**) |

For this workstream, the authoritative FP list remains
`baselines.embedding-cache.false_positive_examples`; category totals for
clustering are derived by grouping that list (via gallery join), not from
aggregate stratum `n` fields.

**Category agreement:** grouped primary sample counts match gallery category
counts on `(id, direction)` (**10 / 2 / 1**).

### Strategy C (separate denominator)

| Metric | Value |
| --- | ---: |
| `baselines.compatibility-cache.false_positive_examples` | **0** |
| `false_positive_rate` | **0.0** |

No Strategy C examples were included in Step 2–3 cluster sums.

### Verification command (Step 3)

```powershell
$env:PYTHONPATH='src'
python -c "import json; from collections import Counter; f=json.load(open('artifacts/evaluation/phase3-final-held-out-comparison.json',encoding='utf-8')); q=json.load(open('artifacts/evaluation/workstream7-quality-analysis.json',encoding='utf-8')); fps=f['baselines']['embedding-cache']['false_positive_examples']; gal={ (e['id'],e['direction']):e for e in q['failure_gallery']['embedding_only_false_positives']}; keys=[(e['id'],e['direction']) for e in fps]; miss=[k for k in keys if k not in gal]; cat=Counter(gal[k]['failure_category'] for k in keys); print({'primary':len(fps),'cluster_sum':sum(cat.values()),'missing_joins':len(miss),'by_category':dict(cat),'strategy_c_fps':len(f['baselines']['compatibility-cache']['false_positive_examples'])})"
```

**Output:**

```text
{'primary': 13, 'cluster_sum': 13, 'missing_joins': 0, 'by_category': {'insufficient_evidence': 10, 'intent_mismatch': 2, 'constraint_mismatch': 1}, 'strategy_c_fps': 0}
```

## Step 4 — published cluster inventory

**Date:** 2026-10-11  
**Evidence commit:** `e3363cfdebed9d9f0734e3b9458fdfede8ac199c`.

This section is the paper-facing inventory. Counts trace to
`phase3-final-held-out-comparison.json` (Strategy B false positives) and Step 3
reconciliation. Every listed example uses direction **`b_to_a`**.

### Strategy B clusters (primary sample)

| Cluster key | Count | Mitigation | Example pair IDs |
| --- | ---: | --- | --- |
| insufficient_evidence · unknown · unknown · unknown | 10 | `rule` | `pair-0036`, `pair-0066`, `pair-0096`, `pair-0161`, `pair-0276`, `pair-0311`, `pair-0316`, `pair-0356`, `pair-0481`, `pair-0601` |
| intent_mismatch · unknown · unknown · unknown | 2 | `rule` | `pair-0367`, `pair-0503` |
| constraint_mismatch · unknown · unknown · unknown | 1 | `rule` | `pair-0543` |

**Total clustered false positives (Strategy B):** **13** (10 + 2 + 1).

Mitigation **`rule`** maps from gallery rationale `compatibility_validator`
(compatibility / validator path). No policy retuning from this analysis.

### Strategy C contrast (Feature 4 protocol; discussion only)

Strategy C + Feature 1 (`compatibility-cache` with adaptive thresholds) on the
frozen final comparison. **Not** included in cluster denominators.

| Metric | Value | JSON path |
| --- | ---: | --- |
| `false_positive_rate` | `0.0` | `baselines.compatibility-cache` |
| `false_positive_examples` | **0** | same |
| `decision_counts` | `SAFE` **1**, `UNCERTAIN` **261**, `UNSAFE` **168** | same |
| `failure_examples` | **171** rows | same (compatibility mismatches / abstentions, not B-style FPs) |

Strategy B primary path also lists `failure_examples`; on this artifact the
embedding arm has **`failure_examples`: null** — clustering used
`false_positive_examples` only (**13**).

**`failure_examples` on Strategy C (171 rows, counts only):**

| `predicted_decision` | Count |
| --- | ---: |
| `UNCERTAIN` | **133** |
| `UNSAFE` | **38** |

| Top `failure_category` | Count |
| --- | ---: |
| `unnecessary_abstention` | **87** |
| `false_negative` | **84** |

Expected vs observed (from `evaluation_labels.compatibility` on each row):
`(SAFE → UNCERTAIN)` **46**, `(UNSAFE → UNCERTAIN)` **77**, `(SAFE → UNSAFE)`
**38**, `(UNCERTAIN → UNCERTAIN)` **10**. No pair-ID listing for this slice
(171 rows); aggregates only.

These failures are **embedding-only (Strategy B)** false reuses in the primary
cluster table; Strategy C blocked unsafe **serves** at FPR `0.0` while still
recording abstentions and non-serve decisions on the held-out workload.

### Reproducibility (read-only)

Canonical sanity check (also Step 1):

```powershell
$env:PYTHONPATH='src'
python -c "import json; p='artifacts/evaluation/phase3-final-held-out-comparison.json'; d=json.load(open(p,encoding='utf-8')); b=d['baselines']['embedding-cache']; c=d['baselines']['compatibility-cache']; print({'b_examples':len(b.get('false_positive_examples',[])),'b_fpr':b.get('false_positive_rate'),'c_examples':len(c.get('false_positive_examples',[])),'c_fpr':c.get('false_positive_rate'),'git_commit':d.get('git_commit'),'config_sha256':d.get('config_sha256')})"
```

**Output (2026-10-11):**

```text
{'b_examples': 13, 'b_fpr': 0.48148148148148145, 'c_examples': 0, 'c_fpr': 0.0, 'git_commit': 'fe68ce3b3cc6cdc35507e8faebbea5549ce5b50e', 'config_sha256': '5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8'}
```

Cluster sum check (Step 3): see § Step 3 verification command; output confirms
`primary` 13, `missing_joins` 0, `strategy_c_fps` 0.

Contrast aggregate check (Step 4):

```powershell
$env:PYTHONPATH='src'
python -c "import json; from collections import Counter; d=json.load(open('artifacts/evaluation/phase3-final-held-out-comparison.json',encoding='utf-8')); c=d['baselines']['compatibility-cache']; fe=c.get('failure_examples') or []; print({'primary_b_fps':len(d['baselines']['embedding-cache']['false_positive_examples']),'strategy_c_fps':len(c.get('false_positive_examples',[])),'c_decision_counts':c.get('decision_counts'),'c_failure_examples':len(fe),'c_predicted':dict(Counter(e.get('predicted_decision') for e in fe))})"
```

**Output (2026-10-11):**

```text
{'primary_b_fps': 13, 'strategy_c_fps': 0, 'c_decision_counts': {'SAFE': 1, 'UNCERTAIN': 261, 'UNSAFE': 168}, 'c_failure_examples': 171, 'c_predicted': {'UNSAFE': 38, 'UNCERTAIN': 133}}
```

**Frozen inputs (not modified):**

- `artifacts/evaluation/phase3-final-held-out-comparison.json`
- `artifacts/evaluation/workstream7-quality-analysis.json`

Optional human-readable gallery (not required for counts):
`artifacts/evaluation/phase3-final-held-out-comparison-gallery.html`.

### Redaction

Published content in this file includes:

- Pair IDs, directions, similarity scores, cluster keys, counts, mitigations
- Report provenance (`git_commit`, config hash, timestamps)

Excluded on purpose (per Feature 4 and project redaction conventions):

- Raw query or answer text from benchmark rows
- Free-text `reason` strings from JSON (even though they are review labels,
  not live user content — IDs and categories suffice for the paper inventory)
- Credentials, tokens, or environment secrets

## Step 5 — close (Feature 4 pass/fail)

**Date:** 2026-10-11  
**Decision:** **pass**  
**Clustering code added:** **no** (stopping rule: manual grouping reproduced from
frozen JSON; no export script required).

### Pre-registered criteria ([`PHASE3_PLAN.md`](./PHASE3_PLAN.md) Feature 4)

| Criterion | Result | Evidence |
| --- | --- | --- |
| Every Strategy B held-out `false_positive_examples` entry in exactly one cluster or singleton | **pass** | § Step 2 assignment (13 rows); § Step 3 one-to-one check |
| Each cluster `count` derivable from `phase3-final-held-out-comparison.json` (gallery join for category) | **pass** | § Step 3 cluster sum and gallery category cross-check |
| Redaction: no secrets; no unapproved raw query text | **pass** | § Step 4 redaction; pair IDs and categories only |

### Workstream acceptance (plan-level)

| Check | Result |
| --- | --- |
| Strategy C kept separate from B denominator | **pass** (0 C false positives) |
| Feature 4 contrast slice recorded (C decisions / `failure_examples`; not clustered) | **pass** | § Step 4 Strategy C contrast |
| Provenance and sanity commands recorded | **pass** (§ Step 1, Step 4) |
| No held-out replay, retuning, dependency, or product code | **pass** (analysis-only) |

### Outcome summary

- **13** Strategy B false positives → **3** cluster keys (2 recurring, 1 singleton).
- Dominant pattern: **insufficient_evidence** (**10** / 13) — embedding-only reuse
  on context-dependent or underspecified rows; Strategy C blocked these at FPR `0.0`.
- No `artifacts/evaluation/phase3-failure-clusters.json` (optional; not required
  for pass).
