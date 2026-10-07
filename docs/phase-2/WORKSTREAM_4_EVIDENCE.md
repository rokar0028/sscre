# Workstream 4 evidence

Completion handoff for real-provider measurement. **Iteration 1 closed** on
2026-10-07 with adapter implementation, tests, unavailable measurement
artifact, and comparison scaffold. This record does not claim a credentialed
provider observation, production capacity, quality, or held-out result.

## Iteration 1 closure (deferral)

- [x] **Decision:** Credentialed live-provider measurement is **deferred to a
  later iteration** (no cloud/local GPU budget in iteration 1; ~4 days into
  Phase 2). WS4 acceptance for this iteration uses the explicit unavailable
  artifact per plan.
- [x] **Next iteration (optional):** Enable `SSCRE_REAL_PROVIDER`,
  `SSCRE_REAL_PROVIDER_LIVE`, `SSCRE_PROVIDER_*`, and run
  `python -m sscre.provider_measure` to produce `status: completed` on the
  development split only.
- [x] **WS5 may proceed** using synthetic baselines and provider-labeled schema;
  do not treat unavailable real-provider fields as zero.

## Evidence status

- [x] The real-provider path is explicit and opt-in.
- [x] The unavailable-provider artifact is redacted and versioned:
  `artifacts/evaluation/workstream4-real-provider-unavailable.json`.
- [x] The synthetic-versus-real comparison is redacted and keeps the
  environments separate:
  `artifacts/evaluation/workstream4-provider-comparison.json`.
- [x] No synthetic values were copied into unavailable real-provider fields.
- [x] Credentialed run **deferred** (not missing implementation): live runner
  exists in `src/sscre/provider_measure.py`; no observation checked in for
  iteration 1.

## Contracts, implementation, and versions

- [x] Provider configuration: `real-provider-config-1.0`.
- [x] Real-provider measurement: `real-provider-measurement-1.0`.
- [x] Comparison artifact: `provider-measurement-comparison-1.0`.
- [x] Frozen safety boundary: `SAFE`, `UNSAFE`, `UNCERTAIN`.
- [x] Frozen serialization boundary: `1.0.0`.
- [x] Provider contract: **OpenAI-compatible HTTP** (`openai-compatible-http-v1`);
  concrete vendor/endpoint is an experiment env value, not a fixed product choice.
- [x] Adapter and measurement files:
  `src/sscre/provider_config.py`, `src/sscre/remote_llm.py`,
  `src/sscre/remote_embedding.py`, `src/sscre/retry.py`,
  `src/sscre/pricing.py`, `src/sscre/provider_measure.py`, and
  `src/sscre/provider_compare.py`.
- [x] The adapters use the Python standard-library `urllib` transport; no
  provider SDK was added.
- [x] Runtime versions observed during verification: Python 3.14.x,
  FastAPI 0.142.x, pytest 9.1.x (see full-suite command below).
  Provider SDK version remains null until a live request runs.
- [x] The unavailable artifact records provider, endpoint, and model fields
  as unavailable rather than inventing them.

## Configuration, workload, and pricing

- [x] Evaluation configuration: `evaluation-config-1.0`,
  `experiments/evaluation_config.json`.
- [x] Dataset: `reviewed-query-pairs-1.1`; development split,
  `benchmarks/development.jsonl`, 21 records.
- [x] Example real-provider pricing file (optional live runs):
  `experiments/real_provider_pricing.json` loaded via
  `SSCRE_PROVIDER_PRICING_JSON` when schedule id matches.
- [x] Redacted configuration boundary only in artifacts; credentials are not
  serialized.

## Commands and results

- [x] Unavailable-provider artifact:

  ```text
  python -m sscre.provider_measure --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --output artifacts/evaluation/workstream4-real-provider-unavailable.json
  ```

  Result: exit 0; status `unavailable`; reason `live_opt_in_missing`.

- [x] Comparison artifact:

  ```text
  python -m sscre.provider_compare --synthetic artifacts/evaluation/workstream3-development.json --real artifacts/evaluation/workstream4-real-provider-unavailable.json --output artifacts/evaluation/workstream4-provider-comparison.json
  ```

  Result: exit 0; synthetic and real-provider rows remain separate.

- [x] Opt-in live-test command (deferred execution in iteration 1):

  ```text
  SSCRE_REAL_PROVIDER_LIVE=true python -m pytest -q -m real_provider
  ```

  Result: skipped without live opt-in and credentials; no remote calls in CI
  default suite.

- [x] Full suite without credentials:

  ```text
  python -m pytest -q
  ```

  Result: **557 passed, 14 skipped**, 1 Starlette/httpx deprecation warning
  (2026-10-07). Default suite makes no remote provider calls.

## Measurement semantics

- [x] Request latency is total request elapsed time.
- [x] Provider latency includes retries/backoff for that operation; wrapper
  latency is local work outside provider calls.
- [x] Token fields: `provider_reported`, `estimated`, `unavailable`.
- [x] Retry cost and total cost become unavailable when failed-attempt billing
  is unknown (`src/sscre/pricing.py`).
- [x] Unavailable run: all provider metrics null/unavailable, not zero.

## Failure-closed and redaction evidence

- [x] Provider/retry failure tests including
  `tests/test_provider_retry_failures.py` (retries do not cache before success).
- [x] Serialization redaction: `validate_redacted_report_payload` on measure
  output; `tests/test_provider_measure.py`,
  `tests/test_provider_accounting_boundary.py`.
- [x] Comparison rules include provider/model match before latency/cost compare.

## Handoff to Workstream 5

- [x] Publish schema versions and comparison artifact paths (this file).
- [x] Publish unavailable rules: null real-provider metrics, separate labels.
- [x] Confirm only `SAFE` remains reusable; provider failures failure-closed.
- [x] Confirm held-out labels were not used for threshold selection in WS4.
- [x] Document limitations: no live latency/token/cost/quality; answer-text
  nondeterminism unmeasured until a completed live run.

## Limitations (iteration 1)

- Real-provider latency, token usage, pricing observations, quality, and
  statistical conclusions are **unavailable** until a credentialed development
  run in a later iteration.
- Provider/API drift and live nondeterminism are **unmeasured**.
- Retry jitter and split connect/read urllib timeouts are **deferred** follow-ups.
