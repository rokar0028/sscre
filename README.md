# SSCRE — Safe Semantic LLM Response Reuse

SSCRE is a FastAPI wrapper that decides when a previous LLM response is safe to reuse. It combines exact matching, semantic retrieval, compatibility checks, freshness controls, and bounded fallbacks so that similarity alone never authorizes a cache hit.

## Why it is different from a normal LLM cache

A basic cache usually reuses an answer when the request text is identical or sufficiently similar. SSCRE treats similarity as retrieval evidence only. A candidate must pass compatibility and cache-control checks before the system returns `SAFE`; otherwise it generates a fresh response or fails closed.

## Architecture

```text
Client
  -> POST /v1/query
  -> normalize and fingerprint request
  -> exact cache lookup
  -> optional embedding + pgvector top-K retrieval
  -> compatibility and freshness safety decision
  -> serve SAFE hit or generate under timeout budget
  -> store only eligible responses
```

## Stack

- Python 3.11+
- FastAPI and Uvicorn
- PostgreSQL 16 with pgvector
- Psycopg 3
- Docker Compose
- Pytest

## Quick start

Prerequisites: Python 3.11+, Git, and Docker Desktop for the database-backed path.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install ".[dev]"
python -m pytest -q
```

To run the API with PostgreSQL and pgvector:

```powershell
Copy-Item .env.example .env
# Change the local password and admin token in .env.
docker compose config
docker compose up --build
```

The API is available at `http://localhost:8000`.

Health check:

```text
GET /health
```

Query endpoint:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/v1/query -Method Post `
  -ContentType 'application/json' `
  -Body '{"query":"What is binary search?"}'
```

The default local profile uses deterministic mock clients. Real provider mode is opt-in and requires explicit credentials and provider configuration; credentials must never be committed.

## Project layout

```text
src/sscre/       Application, API, safety engine, providers, and evaluation code
tests/           Unit and contract tests
migrations/      Ordered PostgreSQL migrations
docs/reference/  Public architecture and contract documentation
benchmarks/      Public benchmark contracts and annotation guidance
demo/            Synthetic example data and local auth fixture
```

## Evaluation and data policy

This public release includes evaluation contracts, tooling, and a synthetic demo fixture. The original research workspace contains larger labeled datasets and experiment artifacts; those are intentionally not included here. They may contain derived upstream data or held-out material that requires separate licensing, attribution, and leakage review.

The project reports compatibility/reuse decisions, not general factual correctness of LLM answers. Aggregate claims should always be read together with the documented limitations.

## Safety and production limitations

- Only `SAFE` decisions may serve cached answers.
- Missing metadata, invalid freshness data, dependency failures, and uncertain compatibility fail closed.
- Rate, budget, and concurrency controls are process-local in this release.
- Multi-worker enforcement and production multi-tenant deployment require additional infrastructure.
- Real-provider latency, cost, and quality are not represented by the default deterministic tests.

## License

Application code is released under the [MIT License](LICENSE). Data and upstream attribution information are described in [LICENSE-DATA](LICENSE-DATA) and [CREDIT.md](CREDIT.md).

