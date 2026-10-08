# Benchmark 500+ external source policy (Phase 0)

Recorded **2026-10-08** for the scale-up workstream
([BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md](./BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md)).

## Deployment assumption

This repository is an **open-source evaluation artifact**. Upstream rows committed
here must be **redistributable under documented licenses** and safe for **commercial
reuse** of the benchmark bundle (training/eval tooling shipped with the repo), not
research-only snapshots with restricted subsets.

When a source offers both permissive and restricted rows, **filter first**, register
the filtered family in
[benchmarks/source_inventory.json](../../benchmarks/source_inventory.json), and record
retained/excluded counts in
[BENCHMARK_500_SCALE_UP_EVIDENCE.md](./BENCHMARK_500_SCALE_UP_EVIDENCE.md) once
import work starts (Phase 1).

## Approved families (registered in source inventory)

| Family ID | Upstream | License | Use in this repo |
| --- | --- | --- | --- |
| `hand_authored_v1` | Project | Project-owned | Existing 32-pair baseline |
| `controlled_template_v1` | Project | Project-owned | Template slots filled by reviewers |
| `cacheeval_v1` | [BudEcosystem/CacheEval](https://github.com/BudEcosystem/CacheEval) | CC BY-SA 4.0 | **Filtered** export only; see exclusions below |
| `redis_paraphrase_v1` | [redis/langcache-sentencepairs-v3](https://huggingface.co/datasets/redis/langcache-sentencepairs-v3), [redis/llm-paraphrases](https://huggingface.co/datasets/redis/llm-paraphrases) | Apache-2.0 | Hard negatives / paraphrase supplements after human review |
| `hand_reviewed_v2` | Derived | Project-owned (edited text) | Human-reviewed SSCRE labels applied to imported **candidates** |

Set candidate `source_group` to `{family_id}:{scenario}` (for example
`cacheeval_v1:filtered`, `redis_paraphrase_v1:langcache_v3_batch01`,
`hand_reviewed_v2:cacheeval_batch01`).

## Excluded or not approved without a new decision

| Source / content | Reason |
| --- | --- |
| CacheEval rows tied to **QQP** or other **non-commercial (NC)** upstream tags | Not cleared for commercial redistribution; drop at filter time |
| Unfiltered CacheEval `cachebench.jsonl` committed as-is | Must use `cacheeval_v1:filtered` pipeline and audit counts |
| **SNLI / MNLI / ANLI** (and similar NLI corpora) as direct `reusable` ground truth | Entailment labels ≠ SSCRE compatibility; pair authoring inspiration only |
| **PAWS-QQP** rebuild subsets | QQP lineage; do not import without a separate legal review |
| Production prompts, credentials, API keys, personal data | Existing prohibited content policy |
| Any Hugging Face or web dataset **not** listed above | Requires an inventory update and this policy addendum |

**Direct import** of **PAWS-Wiki**, **Banking77**, or **CLINC OOS** from Hugging Face
(or other hosts) as a **separate** `source_group` family remains **out of scope**
until a follow-on inventory entry and filter plan are recorded.

**Embedded in CacheEval:** filtered `cacheeval_v1` rows may still cite Banking77
(CC BY 4.0) or CLINC (CC BY 3.0) in CacheEval’s `source` field. That is allowed
**only** through the registered `cacheeval_v1` family after
[filter_cacheeval_commercial.py](../../benchmarks/candidates/tools/filter_cacheeval_commercial.py)
and human review—not as a parallel raw corpus import.

## Upstream pin and QQP re-audit

When changing the CacheEval git revision (`upstream_revision` in
[cacheeval_v1_filter_audit.json](../../benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json)):

- Re-read upstream `ATTRIBUTION.md` and re-run the commercial filter.
- Compare **excluded Quora/QQP row count** to CacheEval’s cited QQP total; if
  attribution cites more QQP-derived rows than are excluded by `source`-tag matching,
  scan retained rows (full JSON) for `quora` / `qqp` and extend filter rules or
  document the gap before merge.
- Update [BENCHMARK_500_SCALE_UP_EVIDENCE.md](./BENCHMARK_500_SCALE_UP_EVIDENCE.md)
  with new counts and output SHA-256.

## Human review and labels

Imported duplicate/paraphrase/safety labels are **starting points only**. Rows enter
`benchmarks/candidates/` with `review_status: draft`. Only humans set
`review_status: final` per [ANNOTATION_GUIDE_v1.md](../../benchmarks/ANNOTATION_GUIDE_v1.md).

## Attribution

- **CacheEval (CC BY-SA 4.0):** preserve upstream attribution requirements documented
  in CacheEval `ATTRIBUTION.md` and `LICENSE` when filtered rows are included in the
  merged benchmark. Summarize attribution in the Phase 1+ evidence file.
- **Redis datasets (Apache-2.0):** retain standard Apache-2.0 notice in project
  license materials if substantial excerpts are redistributed; no separate SA share-alike
  obligation.

## Dataset version bumps

Do **not** silently append hundreds of pairs to `reviewed-query-pairs-1.1`.

- **Label or pair-set change at scale:** bump `dataset_version` (target name:
  `reviewed-query-pairs-2.0`) in `reviewed_query_pairs.jsonl`, `split_manifest.json`,
  and evaluation configs that pin version identity.
- **Same version, split-only rebuild:** allowed only when record IDs and reviewed
  labels are unchanged; re-run `freeze-splits` and refresh manifest checksums.
- **New upstream merge:** always bump `dataset_version` when the canonical reviewed
  file gains new final IDs from external families.

## Verification (Phase 0)

- [x] License decision recorded (this document).
- [x] Approved families added to `benchmarks/source_inventory.json` (`inventory_version`
  `1.1.0`).
- [x] Version bump rule documented (above and in [benchmarks/README.md](../../benchmarks/README.md)).
- [x] [benchmarks/README.md](../../benchmarks/README.md) data-policy section updated.
