# Reviewed benchmark dataset

`reviewed_query_pairs.jsonl` is the Milestone 6 step 2 dataset.

- Schema version: `1.0`
- Records: 24
- Review status: manually reviewed ground-truth pairs
- Reusable pairs: exact duplicates, whitespace-equivalent queries, and
  semantically compatible variants
- Non-reusable pairs: language, format, entity, audience, length, numeric,
  dietary, operation, and other constraint changes

Every non-reusable record includes a short decision reason. Validate the file
before evaluation:

```python
from sscre.benchmark import load_benchmark_jsonl

records = load_benchmark_jsonl("benchmarks/reviewed_query_pairs.jsonl")
```

## Evaluation splits

The split manifest is `split_manifest.json`.

- `development.jsonl` contains 16 pairs for configuration and threshold
  decisions.
- `held_out_test.jsonl` contains 8 disjoint pairs for final reporting only.
- Test labels must not be used when choosing configuration or thresholds.
- Each pair is evaluated in both directions (`a_to_b` and `b_to_a`) where the
  evaluation supports directional replay.

The split files are exact copies of records from the reviewed dataset; their
IDs are disjoint and together cover all 24 reviewed records.

## Threshold sweep and held-out comparison

Run the development threshold sweep first:

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json `
  --baseline embedding-cache `
  --split development `
  --output experiments/embedding_development.json
```

Run the final comparison using a threshold selected from development data:

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all `
  --split held-out `
  --output experiments/embedding_held_out_comparison.json
```

The held-out report includes no-cache, exact-cache, and embedding-only
baselines, latency percentiles, and reviewed false-positive examples. Held-out
labels are used for reporting only, never threshold selection.
