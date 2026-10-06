# SSCRE Benchmark JSONL Format

Each non-blank line is one reviewed query pair. The format version is stored
inside every record so benchmark files remain interpretable after the schema
changes.

```json
{
  "schema_version": "1.0",
  "id": "pair-0001",
  "query_a": "Give me Python code for binary search.",
  "query_b": "Give me Java code for binary search.",
  "reusable": false,
  "correctness_label": "correct",
  "compatibility_label": "incompatible",
  "reason": "programming language constraint differs"
}
```

## Fields

- `schema_version`: currently `"1.0"`.
- `id`: stable, unique, lowercase hyphen-separated identifier such as
  `pair-0001`. IDs must not be reused for a different pair.
- `query_a`, `query_b`: the original non-empty query text. Whitespace is
  validated using the same normalization rules as request preprocessing.
- `reusable`: ground-truth label for whether the answer may safely be reused.
- `correctness_label`: optional judgment of the recorded reuse decision
  (`correct`, `incorrect`, or `uncertain`). Omitted or null means not
  collected.
- `compatibility_label`: `compatible`, `incompatible`, or `uncertain`.
- `reason`: required for non-reusable pairs and briefly explains the decision.

`correctness_label` and `compatibility_label` are intentionally separate from
`reusable`; evaluation must not infer one label from another.

Run-level evaluation artifacts use the nested label block defined in
[benchmarks/EVALUATION_LABEL_CONTRACT_v1.md](../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
(`sscre.evaluation_labels`).

## Validation

Use `sscre.benchmark.load_benchmark_jsonl(path)` before evaluation. It validates
every record, rejects malformed JSON, reports the source line for failures, and
rejects duplicate IDs.
