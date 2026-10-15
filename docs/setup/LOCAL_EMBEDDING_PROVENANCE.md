# Local embedding provenance (Gate A / WS1)

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md) Workstream 1 Step 1.6  
**Evidence:** [`POST_PHASE4_WS1_EVIDENCE.md`](./POST_PHASE4_WS1_EVIDENCE.md)

This note records the **validated local embedding identity** for SSCRE semantic
work. It does not authorize live remote providers (Gate C) or headline
held-out evaluation (Gate D).

## Validated model identity

| Field | Value |
| --- | --- |
| Hugging Face model id | `sentence-transformers/all-MiniLM-L6-v2` |
| Short name | `all-MiniLM-L6-v2` |
| Dimension | **384** |
| License | Apache-2.0 |
| Provider type | `local_sentence_transformer` |
| Vector dtype | `float32` |
| Normalization | L2 unit vectors when `normalize_embeddings` is true (default) |
| Default device in smoke / Phase 4 dev eval | `cpu` |

Registration and runtime checks live in
[`local_embedding.py`](../../src/sscre/local_embedding.py). Frozen evaluation
config: [`experiments/semantic-validity-evaluation-config-v1.json`](../../experiments/semantic-validity-evaluation-config-v1.json).

## Optional dependency (not Gate A)

```powershell
python -m pip install ".[local-embeddings]"
```

From [`pyproject.toml`](../../pyproject.toml): `sentence-transformers>=3.0`
(pulls `torch` transitively). Gate A `pytest -q` does **not** require this
extra.

## Weight provenance and replayability

Weights are fetched from the Hugging Face Hub into the local hub cache when
`SentenceTransformer` loads the model (first smoke load or opt-in tests).

| `weights.state` | Meaning |
| --- | --- |
| `unavailable` | `sentence-transformers` not installed |
| `not_cached_on_disk` | Package installed; no local hub snapshot yet — **do not claim replay** without a successful smoke load |
| `cached_on_disk` | Hub cache already contains a snapshot — replayable when the optional extra is installed |
| `downloaded_during_smoke_load` | Snapshot was absent before `--smoke-load` and smoke passed |

Cache inspection uses the standard hub layout under `HF_HUB_CACHE`, `HF_HOME`,
or the default `~/.cache/huggingface/hub`. No credentials or query text are
written to provenance JSON.

WS1 does **not** pin or download a new model beyond this registered id.

## Fake embeddings (explicit scope)

| Client | Model | Dimension | Authorized use |
| --- | --- | --- | --- |
| `FakeEmbeddingClient` | `fake-embedding` | 8 | Unit tests, benchmarks with injected fakes, synthetic replay |
| Phase 3 / stale B/C JSON | `fake-embedding` | 8 | Historical comparison only — not new semantic claims |

Production / real-provider profiles reject fake embedding clients
([`app.py`](../../src/sscre/app.py)).

## Redacted machine-readable record

Probe + cache only (no download). Use the current checkout on `PYTHONPATH` or
after `pip install` from the repo root:

```powershell
$env:PYTHONPATH = "src"
python scripts/ws1_local_embedding_provenance.py
```

Opt-in smoke load (may download weights):

```powershell
python scripts/ws1_local_embedding_provenance.py --smoke-load
```

Output: [`artifacts/stabilization/local-embedding-provenance.json`](../../artifacts/stabilization/local-embedding-provenance.json).

Phase 4 smoke artifact (same redaction rules, evaluation path):

```powershell
python -m sscre.local_embedding_probe
```

See [`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](../phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md) Step 4 and
[`benchmarks/semantic-validity-local-embedding-gate.json`](../../benchmarks/semantic-validity-local-embedding-gate.json).

## What this step does not do

- Does not run remote embedding APIs (Gate C).
- Does not substitute fake embeddings for real local smoke results.
- Does not read `.env` or print tokens, prompts, or answers.
