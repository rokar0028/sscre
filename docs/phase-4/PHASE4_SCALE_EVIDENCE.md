# Phase 4 storage and bounded-scale evidence

**Track:** `P4-SCALE`  
**Date:** 2026-10-10  
**Status:** complete — no optimization trigger  
**Environment:** local Windows CPU, deterministic fake providers, in-memory
storage

## Frozen protocol

- Storage workload: `experiments/storage_controls_development.json`
  - 4 requests
  - `max_entries=10`
  - `max_bytes=100000`
  - synthetic generation latency `100 ms`
- Bounded scale workload:
  `experiments/milestone10_load_v1.json`
  - 8 warmup requests
  - 32 measured requests
  - concurrency `4`
  - `max_entries=8`
  - `max_bytes=10000`
  - cache modes: no-cache, exact, embedding-only, compatibility
- PostgreSQL, live providers, GPUs, and quantization were not used.
- This workload is bounded and synthetic; it does not support a production
  capacity or 1K–100K Q/day claim.

## Commands

```powershell
$env:PYTHONPATH='src'
python -m sscre.storage_evaluation `
  --workload experiments/storage_controls_development.json `
  --dataset-version phase4-storage-profile-v1 `
  --output artifacts/evaluation/phase4-storage-profile.json `
  --max-entries 10 `
  --max-bytes 100000 `
  --generation-latency-ms 100

python -m sscre.load_test `
  --config experiments/milestone10_load_v1.json `
  --output artifacts/evaluation/phase4-scale-profile.json
```

## Storage result

- [x] 4 requests replayed; hit rate: `0.25`
- [x] Deduplicated entries: `2`
- [x] Total storage: `307` bytes
- [x] No-dedup comparison: `339` bytes
- [x] Deduplication savings: `32` bytes
- [x] Average entry size: `153.5` bytes
- [x] Evictions: `0`
- [x] Expirations: `1`
- [x] Storage profile:
  `artifacts/evaluation/phase4-storage-profile.json`

## Bounded-scale result

The existing deterministic load harness reported wrapper overhead as the first
measured component, averaging `1.819 ms`, while synthetic LLM latency was
`0.0 ms`. Compatibility mode measured:

- cold p50/p95: `14.342 / 24.498 ms`
- warm p50/p95: `14.709 / 19.115 ms`
- cold/warm throughput: `252.151 / 258.415 requests/sec`
- final cache storage: `1174` bytes across `5` entries

The run intentionally produced synthetic failure responses (`3` errors per
mode); these are failure-path fixtures, not evidence of a capacity limit.

- [x] Bounded results:
  `artifacts/evaluation/phase4-scale-profile.json`
- [x] Storage, latency, cache-size, concurrency, and failure summaries recorded.
- [x] No reproducible production bottleneck was established.
- [x] No optimization, quantization, GPU, or infrastructure change selected.

## Decision and limitations

The measured wrapper overhead is not actionable as a production bottleneck
because the provider latency is synthetic zero and the harness uses in-memory
storage. The pre-registered stopping rule therefore applies: document the
tested range and defer optimization. A PostgreSQL or live-provider capacity
claim requires a separately approved workload and environment.
