# Phase 4 provider validation evidence

**Track:** `P4-PROVIDER`  
**Date:** 2026-10-10  
**Status:** unavailable — no credentialed provider request was made  
**Measurement environment:** `real_provider` status artifact only

## Scope decision

Step 2 was executed through the repository's existing provider-measurement
boundary. The project has no configured provider credential or checked-in
provider SDK/transport target for this workspace. The measurement command
therefore followed its fail-closed unavailable path. Synthetic replay was not
substituted.

No real-world cost, token, rate-limit, or network-latency claim is supported by
this run.

## Command

```powershell
$env:SSCRE_REAL_PROVIDER_LIVE='false'
$env:SSCRE_REAL_PROVIDER='false'
$env:SSCRE_PROVIDER_PRICING_JSON='experiments/real_provider_pricing.json'
$env:PYTHONPATH='src'
python -m sscre.provider_measure `
  --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json `
  --output artifacts/evaluation/phase4-provider-validation.json
```

Result: exit `0`; artifact status `unavailable`; reason
`live_opt_in_missing`.

## Artifact

`artifacts/evaluation/phase4-provider-validation.json`

- [x] Provider credentials were not written to source, logs, or artifacts.
- [x] No raw prompts, answers, or provider payloads were serialized.
- [x] Synthetic measurements were not copied into the real-provider artifact.
- [x] Unavailable metrics remain `null`/unavailable rather than fabricated
  zeroes.
- [x] The artifact records the dataset/config paths, commit, runtime metadata,
  redaction flags, and limitations.
- [ ] A credentialed live-provider observation was completed.

## Decision

The track is **deferred**, not passed. The unavailable artifact preserves the
evidence boundary and confirms that the current checkout cannot support a live
provider claim without an explicitly approved provider, credential, endpoint,
model configuration, pricing schedule, and bounded workload.

The retained Phase 3 cache policy is unchanged.
