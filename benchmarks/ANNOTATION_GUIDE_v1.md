# Benchmark annotation guide (v1.0.0)

**Version:** `1.0.0`
**Schema:** benchmark JSONL `1.1`
**Related:** [EVALUATION_LABEL_CONTRACT_v1.md](./EVALUATION_LABEL_CONTRACT_v1.md), [README.md](./README.md)

This guide is for human reviewers authoring or adjudicating query pairs. You do
not need to read the SSCRE implementation to apply it.

## Core question: compatibility

**Compatibility:** Can the cached answer from query A answer query B under the
active reuse policy (constraints, entities, intent, format, freshness)?

That is separate from:

- **Observed safety decision** — what Strategy C emits (`SAFE`, `UNSAFE`,
  `UNCERTAIN`) when the pair is replayed.
- **Correctness** — whether an answer is factually or instructionally acceptable.
- **Preference** — which of two acceptable answers a reviewer prefers.

Record reviewed expectations in `reusable`, `compatibility_label`, and
`failure_category`. Evaluation compares those to observed decisions later.

## Decision vocabulary for reviewed pairs

| Reviewed label | Meaning for the pair | Typical `reusable` |
|---|---|---|
| Compatible | Reuse is permitted under policy | `true` |
| Incompatible | Known mismatch; do not reuse | `false` |
| Uncertain | Evidence insufficient to justify reuse | `false` |

Map to expected safety decisions (see
[EVALUATION_LABEL_CONTRACT_v1.md](./EVALUATION_LABEL_CONTRACT_v1.md)):

- compatible + reusable → expected `SAFE`
- incompatible → expected `UNSAFE`
- uncertain → expected `UNCERTAIN`

### When to mark `UNSAFE` (incompatible)

Use **incompatible** when a **known** policy mismatch exists, for example:

- different programming language or explicit constraint;
- different entity, product, API, or version;
- different requested output format or structure;
- different user intent or task;
- dynamic or time-sensitive query where reuse would be wrong.

Set `failure_category` to the **primary** reason (one value). Put secondary
detail in `reason` or bounded `metadata`.

### When to mark `UNCERTAIN`

Use **uncertain** when reviewers cannot establish reuse safely:

- missing constraint or entity evidence on one side;
- ambiguous or underspecified wording;
- policy requires abstention rather than guessing.

Set `failure_category` to `insufficient_evidence`, `ambiguity`, or `other`.
Do not use uncertain to avoid labeling a clear mismatch.

## Coverage category vs failure category

- **`coverage_category`** — why this pair is in the benchmark (dataset design).
  See inclusion rules in `sscre.benchmark_coverage.CATEGORY_INCLUSION_RULES`.
- **`failure_category`** — primary incompatibility reason when reuse is not
  allowed (or `none` when reusable).

Assign **one** primary value for each. Do not infer either field from model
output after evaluation.

### Approved examples (working baseline)

| ID | `coverage_category` | Notes |
|---|---|---|
| `pair-0001` | `exact_duplicate` | Identical queries |
| `pair-0003` | `whitespace_variant` | Normalization-only difference |
| `pair-0005` | `paraphrase` | Same task, reworded |
| `pair-0023` | `low_overlap_compatible` | Compatible with low lexical overlap |
| `pair-0010` | `high_similarity_incompatible` | Similar templates, different stack |
| `pair-0017` | `intent_change` | Different task on same topic |
| `pair-0009` | `constraint_change` | Language constraint differs |
| `pair-0013` | `entity_change` | Different city entity |
| `pair-0011` | `format_change` | JSON vs table output |

## Freshness and stale answers

Set `freshness_class` on each record:

| Class | Use when |
|---|---|
| `stable` | Conceptual or durable answers |
| `semi_dynamic` | Version- or policy-sensitive content |
| `dynamic` | Current-state or live data queries |

Mark **`coverage_category`: `stale_answer`** when the pair tests outdated cached
content. Use **`failure_category`: `stale_answer`** or **`temporal_mismatch`**
when reuse is blocked for freshness reasons while compatibility is otherwise
partial.

## Metadata fields

Populate bounded `metadata` when it helps analysis (optional but recommended
for new pairs):

- `intent` — e.g. code generation, explanation, factual lookup
- `domain` — e.g. programming, general
- `entities` — stable identifiers (not raw secrets)
- `constraints` — key/value such as `language: python`
- `temporal_class` — aligns with freshness semantics when relevant
- `output_format` — e.g. code, json, prose

Use the same size limits as operational trace metadata.

## Correctness labels

Correctness is **independent** of compatibility.

| Value | When to use |
|---|---|
| `correct` | Reviewed answer meets factual and instructional requirements |
| `incorrect` | Reviewed answer is wrong or harmful |
| `uncertain` | Reviewers disagree or evidence is insufficient |
| omitted / `null` | No answer was reviewed |

Rules:

- Set `answer_availability` to `query_a`, `query_b`, or `both` before any
  correctness label on schema `1.1`.
- Do not use correctness to mean preference or compatibility.
- **`SAFE` compatibility does not prove correctness.**

## Preference labels

Use `preference_label` (`A`, `B`, `tie`) only when two **reviewed acceptable**
answers are compared. Requires `answer_availability` other than `none`.

Map winners in reports to cached/generated when applicable; `A`/`B` refer to
query-side answers in the pair.

**A preferred answer is not automatically more factually correct.** Report
preference and correctness separately.

## Annotator identity and provenance

- Set `annotation_source` to a stable pseudonym or process id (e.g.
  `human_review`, `reviewer-alpha`, `adjudication-board`). Do not use real
  names, email, or credentials in checked-in files.
- Set `review_status` to `draft`, `final`, or `disputed`.
- Set `annotator_count` to the number of independent reviews contributing to
  the final label.
- Set `adjudication_status` to `final`, `draft`, or `disputed` when
  adjudication applies.

## Disagreements and adjudication

When two reviewers disagree:

1. Keep both judgments in review notes or revision history (do not silently
   overwrite the first review in git without a dataset version bump).
2. Set `review_status` to `disputed` and `adjudication_status` to `disputed`
   until resolved.
3. Record the adjudicator decision in `reason` or project revision notes with
   **annotation guide version** and date.
4. Only project maintainers (or delegated lead reviewers) may set `final`
   after adjudication.

**Mandatory second review** for:

- any disputed pair;
- high-impact domains (medical, legal, financial, safety-critical instructions);
- pairs intended for the **held-out** split before freeze.

## Redaction

Do not commit:

- API keys, tokens, passwords, or authorization headers;
- personal data or private URLs;
- unrestricted production prompts or full provider transcripts;
- proprietary third-party text without permission.

Query pairs should be authored or redacted for the repository.

## Review policy summary

| Rule | Enforcement |
|---|---|
| Every **final** pair has at least one review | `annotation_source` required; optional `annotator_count` |
| Disputed / high-impact pairs get two reviews | `annotator_count >= 2` before `final` (recommended) |
| Adjudication preserves guide version | Document in commit message or revision log |
| Draft or disputed pairs not in held-out | `validate_review_policy` on held-out evaluation |
| Label changes bump dataset version | New `dataset_version` or auditable revision; never silent ID reuse |

Dataset version changes are recorded in `split_manifest.json` and evaluation
configuration (`dataset_version` in `experiments/evaluation_config.json`).
