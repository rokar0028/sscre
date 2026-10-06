# Evaluation label contract (v1.0.0)

**Status:** frozen for Phase 2 Workstreams 2–9  
**Related:** [SAFETY_EVALUATION_CONTRACT_v1.md](../docs/phase-2/SAFETY_EVALUATION_CONTRACT_v1.md),
[SSCRE_BENCHMARK_FORMAT.md](../docs/SSCRE_BENCHMARK_FORMAT.md)

## Separation rules

| Label | Question | Not the same as |
|---|---|---|
| Compatibility | Can the cached answer serve the new query under policy? | Correctness, preference, similarity |
| Correctness | Is an answer factually / instructionally acceptable? | Compatibility, preference |
| Preference | Which acceptable answer is preferred? | Correctness (A/B/tie ≠ correct/incorrect) |

- `SAFE` compatibility does **not** prove factual correctness.
- `null` means **not collected or not applicable** — never treat as incorrect.

## Canonical evaluation artifact block

Used in run reports (`evaluation_labels` on failure examples) and tooling:

```json
{
  "compatibility": {
    "expected_decision": "SAFE",
    "observed_decision": "UNSAFE"
  },
  "correctness": {
    "cached_answer": null,
    "generated_answer": null
  },
  "preference": {
    "winner": null,
    "applicable": false
  }
}
```

Optional provenance (when collected):

```json
{
  "annotation": {
    "source": "human_review",
    "adjudication_status": "final"
  }
}
```

Implementation: `sscre.evaluation_labels.EvaluationLabelRecord`.

## Allowed values

| Field | Allowed | Nullable |
|---|---|---|
| `compatibility.expected_decision` | `SAFE`, `UNSAFE`, `UNCERTAIN` | no |
| `compatibility.observed_decision` | `SAFE`, `UNSAFE`, `UNCERTAIN` | no |
| `correctness.cached_answer` | `correct`, `incorrect`, `uncertain` | yes |
| `correctness.generated_answer` | `correct`, `incorrect`, `uncertain` | yes |
| `preference.winner` | `cached`, `generated`, `tie` | yes |
| `preference.applicable` | boolean | no (default `false`) |
| `annotation.source` | free string | yes |
| `annotation.adjudication_status` | `final`, `draft`, `disputed` | yes |

**Rejected:** preference tokens (`A`, `B`, `tie`, `cached`, `generated`) in
`correctness.*` fields.

## Benchmark JSONL (schema 1.0)

Flat fields remain for reviewed pairs:

- `compatibility_label`: `compatible` | `incompatible` | `uncertain`
- `correctness_label`: optional `correct` | `incorrect` | `uncertain`;
  omitted or null means not collected
- `preference_label`: optional `A` | `B` | `tie`
- `annotation_source`, `adjudication_status`: optional provenance

Ground-truth reuse expectation is still `reusable`; expected safety decisions
for evaluation are derived via `expected_compatibility_decision()` in code.

## Report sections

Strategy C baseline reports expose `label_sections` with three keys —
`compatibility`, `correctness`, `preference` — so metrics never merge label
families.
