# SSCRE — System Design Document

**Safe Semantic LLM Response Reuse**

Companion to [SSCRE_PLAN.md](./SSCRE_PLAN.md). This document specifies *how* to build the system: components, interfaces, data flows, storage, deployment, and scaling.

---

## Table of Contents

1. [System Context](#1-system-context)
2. [Architecture Overview](#2-architecture-overview)
3. [Container Diagram](#3-container-diagram)
4. [Core Components](#4-core-components)
5. [Request Flows](#5-request-flows)
6. [Cache Decision State Machine](#6-cache-decision-state-machine)
7. [Data Model](#7-data-model)
8. [API Design](#8-api-design)
9. [Module Structure](#9-module-structure)
10. [Configuration](#10-configuration)
11. [Deployment](#11-deployment)
12. [Non-Functional Requirements](#12-non-functional-requirements)
13. [Observability](#13-observability)
14. [Security](#14-security)
15. [Scaling & Bottlenecks](#15-scaling--bottlenecks)
16. [Failure Handling](#16-failure-handling)
17. [Phase Mapping](#17-phase-mapping)

---

## Diagram Legend

All architecture diagrams in this document use the same visual language:

| Color | Meaning | Hex |
|-------|---------|-----|
| **Purple** | Application services (FastAPI, orchestrator, engines) | `#4B4497` |
| **Green** | Data store (PostgreSQL + pgvector, tables) | `#004D40` |
| **Grey** | External systems (client, LLM provider, embedding API) | `#444444` |
| **Black boxes** | Database tables / collections inside a data store | `#1a1a1a` |

Containers use **dashed white borders** for application boundaries and **solid green borders** for data stores.

---

## 1. System Context

SSCRE is an **application-layer wrapper** placed between clients and LLM providers. It does not replace the LLM — it decides whether to call one.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    Client["Client app<br/><sub>API consumer</sub>"]
    EvalCLI["Evaluation CLI<br/><sub>Benchmark runner</sub>"]

    subgraph fastapi["FastAPI container"]
        API["API layer<br/><sub>REST + JSON schemas</sub>"]
        ORCH["Orchestrator<br/><sub>Pipeline coordinator</sub>"]
    end

    subgraph postgres["Postgres + pgvector"]
        DB["cache_entries · request_logs<br/>cache_failures · experiment_runs"]
    end

    Embed["Embedding provider<br/><sub>External API</sub>"]
    LLM["LLM provider<br/><sub>External API</sub>"]

    Client -->|query| API
    EvalCLI -->|evaluate| API
    API --> ORCH
    ORCH -->|lookup + write| postgres
    ORCH -->|embed query| Embed
    ORCH -->|generate on miss| LLM

    classDef external fill:#444444,stroke:#888888,color:#ffffff
    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff
    classDef table fill:#1a1a1a,stroke:#555555,color:#ffffff

    class Client,EvalCLI,Embed,LLM external
    class API,ORCH app
    class DB table

    style fastapi fill:#000000,stroke:#ffffff,stroke-dasharray:8 4
    style postgres fill:#004D40,stroke:#ffffff
```

### Boundaries

| Inside SSCRE | Outside SSCRE |
|--------------|---------------|
| Query preprocessing & fingerprinting | Client UI logic |
| Semantic retrieval & safety decisions | LLM training / fine-tuning |
| Cache storage & eviction | Provider-side prompt caching |
| Metrics, logging, evaluation runs | Full RAG document pipelines |
| Optional comparison UI (Phase 2) | Browser extensions |

### Primary Actors

| Actor | Interaction |
|-------|-------------|
| **End client** | Sends queries via `/v1/query` |
| **Evaluator** | Runs benchmark via CLI / admin API |
| **Admin** | Purges cache, views failures, configures thresholds |
| **Embedding API** | Returns query vectors |
| **LLM API** | Generates answers on cache miss |

---

## 2. Architecture Overview

### Design Goals

1. **Zero downstream tokens** on SAFE cache hits
2. **FPR ≤ 3%** at chosen operating point (configurable)
3. **Cache storage ≤ 100 MB** (MVP cap, configurable)
4. **Wrapper overhead < 10%** of tokens saved vs no-cache baseline
5. **Reproducible** experiments from versioned configs

### Layered Architecture

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    subgraph presentation["Presentation layer"]
        PRES["FastAPI routes<br/><sub>Streamlit dashboard · Phase 2</sub>"]
    end

    subgraph application["Application layer"]
        APP["QueryOrchestrator · EvaluationRunner<br/><sub>CacheAdminService</sub>"]
    end

    subgraph domain["Domain layer"]
        DOM["SafetyEngine · FreshnessPolicy<br/><sub>ConstraintFingerprinter · Strategy A/B/C/D</sub>"]
    end

    subgraph infrastructure["Infrastructure layer"]
        INF["CacheRepository · EmbeddingClient · LLMClient<br/><sub>MetricsCollector · ExperimentStore</sub>"]
    end

    subgraph datalayer["Data layer"]
        DATA["PostgreSQL + pgvector<br/><sub>optional local embed cache</sub>"]
    end

    PRES --> APP --> DOM --> INF --> DATA

    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff

    class PRES,APP,DOM,INF app
    class DATA data

    style presentation fill:#000000,stroke:#ffffff,stroke-dasharray:8 4
    style application fill:#000000,stroke:#ffffff,stroke-dasharray:8 4
    style domain fill:#000000,stroke:#ffffff,stroke-dasharray:8 4
    style infrastructure fill:#000000,stroke:#ffffff,stroke-dasharray:8 4
    style datalayer fill:#004D40,stroke:#ffffff
```

---

## 3. Container Diagram

![SSCRE container architecture](./assets/sscre-container-architecture.png)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    Client["Client app<br/><sub>API consumer</sub>"]
    EvalCLI["Evaluation CLI<br/><sub>Offline benchmark</sub>"]
    Dashboard["Streamlit dashboard<br/><sub>Phase 2 · metrics UI</sub>"]

    subgraph fastapi["FastAPI container"]
        API["API layer<br/><sub>REST + JSON schemas</sub>"]
        ORCH["Orchestrator<br/><sub>Pipeline coordinator</sub>"]
        EvalRun["Evaluation runner<br/><sub>Experiment sweeps</sub>"]

        PRE["Preprocessor<br/><sub>Embed query</sub>"]
        CACHE["Cache repo<br/><sub>Lookup + write</sub>"]
        SAFE["Safety engine<br/><sub>Safety decision</sub>"]
        LLMClient["LLM client<br/><sub>Miss fallback</sub>"]
    end

    subgraph postgres["Postgres + pgvector"]
        T1["cache_entries"]
        T2["request_logs"]
        T3["cache_failures"]
        T4["experiment_runs"]
    end

    Embed["Embedding provider<br/><sub>External API</sub>"]
    LLM["LLM provider<br/><sub>External API</sub>"]
    LLM2["LLM provider B<br/><sub>Phase 2 · comparison</sub>"]

    Client --> API
    EvalCLI --> EvalRun
    Dashboard --> API
    API --> ORCH
    ORCH --> PRE
    ORCH --> CACHE
    ORCH --> SAFE
    ORCH --> LLMClient
    EvalRun --> CACHE
    PRE --> Embed
    CACHE <--> postgres
    LLMClient <--> LLM
    LLMClient -.-> LLM2

    classDef external fill:#444444,stroke:#888888,color:#ffffff
    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef table fill:#1a1a1a,stroke:#555555,color:#ffffff

    class Client,EvalCLI,Dashboard,Embed,LLM,LLM2 external
    class API,ORCH,EvalRun,PRE,CACHE,SAFE,LLMClient app
    class T1,T2,T3,T4 table

    style fastapi fill:#000000,stroke:#ffffff,stroke-dasharray:8 4
    style postgres fill:#004D40,stroke:#ffffff
```

### Container Responsibilities

| Container | Responsibility | Tech |
|-----------|----------------|------|
| **API Gateway** | Auth (optional), routing, request validation | FastAPI + Pydantic |
| **Query Orchestrator** | End-to-end query pipeline | Python async |
| **Safety Engine** | Strategy selection, compatibility scoring | Pure Python (testable) |
| **Evaluation Runner** | Offline benchmark sweeps | Click/Typer CLI |
| **PostgreSQL** | Cache entries, logs, experiments | pgvector extension |
| **Streamlit** | Metrics + failure gallery (Phase 2) | Streamlit |

---

## 4. Core Components

### 4.1 Query Orchestrator

Central coordinator. Single entry point for live queries.

```python
class QueryOrchestrator:
    async def handle(self, request: QueryRequest) -> QueryResponse:
        ctx = self.preprocessor.process(request)
        ctx = await self.exact_match_lookup(ctx)          # Strategy A fast path
        if ctx.decision == SAFE:
            return self.build_cache_response(ctx)

        ctx = await self.embedder.embed(ctx)
        candidates = await self.cache_repo.search(ctx.embedding, top_k=config.top_k)
        ctx = self.safety_engine.evaluate(ctx, candidates)

        if ctx.decision == SAFE:
            await self.cache_repo.increment_hit(ctx.selected_entry_id)
            return self.build_cache_response(ctx)

        ctx = await self.llm_client.generate(ctx)         # single model MVP
        if ctx.cache_eligible:
            await self.cache_writer.insert(ctx)
        return self.build_generated_response(ctx)
```

**Rules:**
- Exact hash hit bypasses embedding (saves cost + latency)
- Never serve top-1 vector result without safety check
- Log every decision with full candidate trace

---

### 4.2 Query Preprocessor

| Function | Input | Output |
|----------|-------|--------|
| `normalize()` | raw query string | trimmed, collapsed whitespace |
| `fingerprint()` | normalized query | `constraint_fingerprint: str` (SHA-256 of structured constraints) |
| `extract_metadata()` | normalized query | `QueryMetadata` (rule-based, no LLM) |
| `hash_query()` | normalized query | `query_hash: str` |

**Constraint fingerprint inputs (MVP — regex/rules):**

```python
@dataclass
class QueryMetadata:
    intent: Literal["explain", "code", "compare", "factual", "unknown"]
    domain: Literal["programming", "finance", "general", "unknown"]
    entities: list[str]           # max 10
    constraints: dict[str, str]   # e.g. {"language": "python"}
    temporal_class: Literal["stable", "semi_dynamic", "dynamic"]
    output_format: Literal["prose", "code", "list", "json", "unknown"]
```

Fingerprint = `sha256(json.dumps(constraints, sort_keys=True) + intent + output_format)`

---

### 4.3 Safety Engine

Pluggable strategies via registry:

```python
class SafetyStrategy(Protocol):
    def evaluate(
        self,
        query: ProcessedQuery,
        candidates: list[CacheCandidate],
    ) -> SafetyResult: ...

class SafetyEngine:
    strategies: dict[str, SafetyStrategy]  # "A", "B", "C", "D"
    active: str  # from config
```

**Candidate evaluation order:** iterate top-K by similarity descending; return first **SAFE**; if all UNSAFE → miss; if any UNCERTAIN and none SAFE → **UNCERTAIN → generate**.

**SafetyResult:**

```python
@dataclass
class SafetyResult:
    decision: Literal["SAFE", "UNSAFE", "UNCERTAIN"]
    selected_entry_id: UUID | None
    similarity: float | None
    reason: str
    strategy: str
    candidate_traces: list[CandidateTrace]  # for debugging / failures
```

---

### 4.4 Cache Repository

| Method | Description |
|--------|-------------|
| `get_by_query_hash(hash)` | Exact match lookup |
| `search(embedding, top_k)` | pgvector cosine similarity |
| `insert(entry)` | Dedup-aware insert |
| `increment_hit(id)` | Atomic hit_count += 1 |
| `evict_lru()` | Called when over cap |
| `purge_expired()` | TTL sweep |
| `stats()` | entries, bytes, hit_rate aggregates |

**Vector search SQL (pgvector):**

```sql
SELECT id, query_hash, query_text, answer_text, metadata,
       constraint_fingerprint, freshness_class, ttl_expires_at,
       1 - (embedding <=> $1::vector) AS similarity
FROM cache_entries
WHERE ttl_expires_at IS NULL OR ttl_expires_at > now()
ORDER BY embedding <=> $1::vector
LIMIT $2;
```

---

### 4.5 Cache Writer (Insert Pipeline)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart LR
    NEW["New LLM answer<br/><sub>from miss path</sub>"]
    HASH["Compute answer_hash<br/><sub>content fingerprint</sub>"]
    DEDUP{"answer_hash<br/>exists?"}
    LINK["Link + increment<br/><sub>skip duplicate blob</sub>"]
    QHASH{"query_hash<br/>exists?"}
    UPDATE["Update TTL / hit_count"]
    CAP{"Storage cap<br/>exceeded?"}
    EVICT["Evict LRU entry<br/><sub>bounded cache</sub>"]
    INSERT["Insert cache row<br/><sub>Postgres + pgvector</sub>"]

    NEW --> HASH --> DEDUP
    DEDUP -->|yes| LINK
    DEDUP -->|no| QHASH
    QHASH -->|yes| UPDATE
    QHASH -->|no| CAP
    CAP -->|yes| EVICT --> INSERT
    CAP -->|no| INSERT

    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff
    classDef decision fill:#444444,stroke:#888888,color:#ffffff

    class NEW,HASH,LINK,UPDATE,EVICT app
    class INSERT data
    class DEDUP,QHASH,CAP decision
```

**Cache eligibility gates (before insert):**

- `temporal_class != "dynamic"`
- `correctness_label != "incorrect"` (when labeled)
- answer length ≤ max_answer_bytes (e.g. 32 KB)
- strategy experiment mode may disable insert

---

### 4.6 LLM Client

Abstract provider interface:

```python
class LLMClient(Protocol):
    async def generate(self, query: str, model: str) -> LLMResult: ...

@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
```

Phase 1: one provider. Phase 2: parallel `asyncio.gather` for Model A + B.

---

### 4.7 Evaluation Runner

Offline batch processor — does **not** share live request path code blindly; reuses `SafetyEngine` + `CacheRepository` for consistency.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    CLI["Evaluation CLI<br/><sub>External runner</sub>"]
    RUN["Evaluation runner<br/><sub>Batch coordinator</sub>"]
    DS["Benchmark dataset<br/><sub>labeled query pairs</sub>"]
    CACHE["Cache repo<br/><sub>fresh or replay state</sub>"]
    SAFE["Safety engine<br/><sub>strategy A/B/C/D</sub>"]
    MET["Metrics aggregator<br/><sub>FPR · recall · tokens saved</sub>"]
    EXP["experiment_runs<br/><sub>Postgres table</sub>"]
    OUT["report.json + stdout<br/><sub>reproducible output</sub>"]

    CLI --> RUN
    RUN --> DS
    RUN --> CACHE
    DS --> SAFE
    CACHE --> SAFE
    SAFE --> MET --> EXP --> OUT

    classDef external fill:#444444,stroke:#888888,color:#ffffff
    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff
    classDef table fill:#1a1a1a,stroke:#555555,color:#ffffff

    class CLI external
    class RUN,SAFE,MET app
    class DS data
    class EXP table
    class OUT external
```

Supports **reset cache between runs** for fair comparison.

---

## 5. Request Flows

### 5.1 Cache Hit (SAFE) — Flow

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    C["Client app<br/><sub>POST /v1/query</sub>"]
    API["API layer<br/><sub>REST + JSON schemas</sub>"]
    ORCH["Orchestrator<br/><sub>Pipeline coordinator</sub>"]
    PRE["Preprocessor<br/><sub>normalize · fingerprint</sub>"]
    CACHE["Cache repo<br/><sub>hash lookup · vector search</sub>"]
    SAFE["Safety engine<br/><sub>compatibility check</sub>"]
    PG["Postgres + pgvector<br/><sub>cache_entries</sub>"]
    RESP["QueryResponse<br/><sub>source = cache · 0 LLM tokens</sub>"]

    C --> API --> ORCH --> PRE --> CACHE
    CACHE <--> PG
    CACHE --> SAFE
    SAFE -->|SAFE| CACHE
    CACHE -->|increment_hit| PG
    ORCH --> RESP --> C

    classDef external fill:#444444,stroke:#888888,color:#ffffff
    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff

    class C external
    class API,ORCH,PRE,CACHE,SAFE app
    class PG data
    class RESP app
```

**Latency budget (target):** p50 < 150ms (embed + search + rules, no LLM)

---

### 5.2 Cache Miss — Generate + Insert

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    ORCH["Orchestrator<br/><sub>Pipeline coordinator</sub>"]
    SAFE["Safety engine<br/><sub>UNSAFE or UNCERTAIN</sub>"]
    LLM["LLM client<br/><sub>Miss fallback</sub>"]
    PROV["LLM provider<br/><sub>External API</sub>"]
    WRITER["Cache writer<br/><sub>dedup · evict · insert</sub>"]
    CACHE["Cache repo<br/><sub>Lookup + write</sub>"]
    PG["Postgres + pgvector<br/><sub>cache_entries</sub>"]
    RESP["QueryResponse<br/><sub>source = generated</sub>"]

    ORCH --> SAFE
    SAFE -->|no safe candidate| LLM
    LLM <--> PROV
    LLM --> ORCH
    ORCH --> WRITER
    WRITER --> CACHE
    CACHE -->|dedup + evict| PG
    ORCH --> RESP

    classDef external fill:#444444,stroke:#888888,color:#ffffff
    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff

    class PROV external
    class ORCH,SAFE,LLM,WRITER,CACHE,RESP app
    class PG data
```

---

### 5.3 Evaluation Run — Flow

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    CLI["Evaluation CLI<br/><sub>run config.yaml</sub>"]
    RUN["Evaluation runner<br/><sub>Batch coordinator</sub>"]
    CACHE["Cache repo<br/><sub>optional reset</sub>"]
    SAFE["Safety engine<br/><sub>predict vs expected</sub>"]
    LOOP["For each benchmark query<br/><sub>labeled pairs</sub>"]
    MET["Metrics aggregator<br/><sub>FPR · recall · tokens saved</sub>"]
    DB["experiment_runs<br/><sub>Postgres table</sub>"]
    OUT["report.json + stdout<br/><sub>reproducible output</sub>"]

    CLI --> RUN
    RUN --> CACHE
    RUN --> LOOP
    LOOP --> SAFE
    SAFE --> MET
    MET --> DB --> OUT --> CLI

    classDef external fill:#444444,stroke:#888888,color:#ffffff
    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff
    classDef table fill:#1a1a1a,stroke:#555555,color:#ffffff

    class CLI,OUT external
    class RUN,CACHE,SAFE,LOOP,MET app
    class DB table
```

---

## 6. Cache Decision State Machine

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    START(["Incoming query"])
    PRE["Preprocessor<br/><sub>normalize · fingerprint</sub>"]
    EXACT["Exact hash lookup<br/><sub>Strategy A fast path</sub>"]
    EMBED["Embed query<br/><sub>Preprocessor → provider</sub>"]
    SEARCH["Vector search top-K<br/><sub>Cache repo · pgvector</sub>"]
    EVAL["Safety engine<br/><sub>evaluate candidates</sub>"]
    SAFE["SAFE hit<br/><sub>return cached answer</sub>"]
    NOCAND["No candidates<br/><sub>empty result set</sub>"]
    GEN["LLM client<br/><sub>generate answer</sub>"]
    CHECK{"Cache eligible?<br/><sub>freshness · correctness</sub>"}
    INSERT["Cache writer<br/><sub>dedup insert</sub>"]
    DONE(["Response to client"])

    START --> PRE --> EXACT
    EXACT -->|hash match| SAFE --> DONE
    EXACT -->|miss| EMBED --> SEARCH
    SEARCH -->|empty| NOCAND --> GEN
    SEARCH -->|top-K| EVAL
    EVAL -->|first SAFE| SAFE
    EVAL -->|all UNSAFE or UNCERTAIN| GEN
    GEN --> CHECK
    CHECK -->|yes| INSERT --> DONE
    CHECK -->|no · dynamic query| DONE

    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff
    classDef decision fill:#444444,stroke:#888888,color:#ffffff
    classDef terminal fill:#1a1a1a,stroke:#ffffff,color:#ffffff

    class PRE,EXACT,EMBED,SEARCH,EVAL,SAFE,GEN,INSERT app
    class NOCAND decision
    class CHECK decision
    class START,DONE terminal
```

### Decision Truth Table (Strategy C)

| Similarity | Fingerprint match | Constraint conflict | Temporal | Result |
|------------|-------------------|---------------------|----------|--------|
| < τ_low | * | * | * | UNSAFE |
| ≥ τ_high | yes | no | stable/semi | **SAFE** |
| ≥ τ_high | no | yes | * | UNSAFE |
| ≥ τ_high | no | no | dynamic | UNCERTAIN |
| mid band | no | no | stable | UNCERTAIN |
| * | * | * | expired TTL | UNSAFE (treat as miss) |

Default: `τ_low = 0.80`, `τ_high = 0.92` (tune via experiments)

---

## 7. Data Model

### 7.1 Entity Relationship

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    subgraph postgres["Postgres + pgvector"]
        CE["cache_entries<br/><sub>id · query_hash · embedding · answer</sub>"]
        RL["request_logs<br/><sub>request_id · decision · tokens · latency</sub>"]
        CF["cache_failures<br/><sub>failure_type · expected vs actual</sub>"]
        ER["experiment_runs<br/><sub>config · metrics · report_path</sub>"]
    end

    CE -->|selected_entry FK| RL
    CE -->|wrong_entry| CF
    RL -->|request_id FK| CF
    ER -.->|reads during eval| CE

    classDef table fill:#1a1a1a,stroke:#555555,color:#ffffff
    class CE,RL,CF,ER table
    style postgres fill:#004D40,stroke:#ffffff
```

### 7.2 Full SQL Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE cache_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash          CHAR(64) NOT NULL,
    query_text          TEXT,
    embedding           vector(1536) NOT NULL,
    answer_hash         CHAR(64) NOT NULL,
    answer_text         TEXT NOT NULL,
    constraint_fingerprint CHAR(64) NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}',
    freshness_class     TEXT NOT NULL DEFAULT 'stable'
                        CHECK (freshness_class IN ('stable', 'semi_dynamic', 'dynamic')),
    ttl_expires_at      TIMESTAMPTZ,
    hit_count           INT NOT NULL DEFAULT 0,
    model_source        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_cache_query_hash ON cache_entries (query_hash);
CREATE INDEX idx_cache_answer_hash ON cache_entries (answer_hash);
CREATE INDEX idx_cache_ttl ON cache_entries (ttl_expires_at) WHERE ttl_expires_at IS NOT NULL;
CREATE INDEX idx_cache_lru ON cache_entries (last_accessed_at);
CREATE INDEX idx_cache_embedding ON cache_entries
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE request_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id          UUID NOT NULL UNIQUE,
    query_text          TEXT NOT NULL,
    query_hash          CHAR(64) NOT NULL,
    decision            TEXT NOT NULL CHECK (decision IN ('SAFE', 'UNSAFE', 'UNCERTAIN', 'EXACT_HIT')),
    outcome             TEXT NOT NULL CHECK (outcome IN ('cache_hit', 'cache_miss', 'generated')),
    strategy            TEXT NOT NULL,
    cache_entry_id      UUID REFERENCES cache_entries(id) ON DELETE SET NULL,
    similarity          REAL,
    candidate_count     INT NOT NULL DEFAULT 0,
    embed_latency_ms    INT,
    search_latency_ms   INT,
    safety_latency_ms   INT,
    llm_latency_ms      INT,
    llm_input_tokens    INT NOT NULL DEFAULT 0,
    llm_output_tokens   INT NOT NULL DEFAULT 0,
    total_latency_ms    INT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_logs_created ON request_logs (created_at);
CREATE INDEX idx_logs_outcome ON request_logs (outcome);

CREATE TABLE cache_failures (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id          UUID REFERENCES request_logs(request_id) ON DELETE CASCADE,
    new_query           TEXT NOT NULL,
    cached_query        TEXT,
    similarity          REAL,
    expected_decision   TEXT,
    actual_decision     TEXT NOT NULL,
    failure_type        TEXT NOT NULL,
    strategy            TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_failures_type ON cache_failures (failure_type);

CREATE TABLE experiment_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    config              JSONB NOT NULL,
    metrics             JSONB NOT NULL,
    report_path         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 7.3 Storage Size Estimate

| Field | Approx size |
|-------|-------------|
| embedding (1536 × float32) | ~6 KB |
| answer_text (avg 2 KB) | ~2 KB |
| metadata + indexes overhead | ~1 KB |
| **Total per entry** | **~9–12 KB** |

At 10,000 entries → **~100 MB** (matches cap). Dedup on `answer_hash` reduces real growth.

---

## 8. API Design

### 8.1 POST `/v1/query`

**Request:**

```json
{
  "query": "Explain binary search in Python",
  "session_id": "optional-uuid",
  "options": {
    "strategy": "C",
    "skip_cache": false,
    "force_generate": false
  }
}
```

**Response (cache hit):**

```json
{
  "request_id": "uuid",
  "source": "cache",
  "answer": "...",
  "decision": "SAFE",
  "cache_entry_id": "uuid",
  "similarity": 0.94,
  "strategy": "C",
  "metrics": {
    "total_latency_ms": 87,
    "llm_input_tokens": 0,
    "llm_output_tokens": 0,
    "embed_latency_ms": 45,
    "search_latency_ms": 12
  }
}
```

**Response (generated):**

```json
{
  "request_id": "uuid",
  "source": "generated",
  "answer": "...",
  "decision": "UNCERTAIN",
  "strategy": "C",
  "metrics": {
    "total_latency_ms": 2340,
    "llm_input_tokens": 120,
    "llm_output_tokens": 450,
    "llm_model": "gpt-4o-mini"
  }
}
```

---

### 8.2 GET `/v1/cache/stats`

```json
{
  "entries": 847,
  "bytes_estimate": 12400000,
  "max_bytes": 100000000,
  "hit_rate_24h": 0.342,
  "false_positive_rate_24h": 0.021,
  "dedup_savings_ratio": 0.18,
  "eviction_count_24h": 12
}
```

---

### 8.3 GET `/v1/failures?limit=50&offset=0`

Paginated failure gallery for dashboard / viva demo.

---

### 8.4 POST `/v1/evaluate/run` (admin)

Triggers async or sync evaluation job from YAML config. Returns `experiment_run_id`.

---

### 8.5 DELETE `/v1/cache/purge`

Query params: `expired_only=true` | `all=false`. Admin-only.

---

### 8.6 Pydantic Models (shared)

```python
class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None
    options: QueryOptions = QueryOptions()

class QueryOptions(BaseModel):
    strategy: Literal["A", "B", "C", "D"] = "C"
    skip_cache: bool = False
    force_generate: bool = False

class QueryResponse(BaseModel):
    request_id: UUID
    source: Literal["cache", "generated"]
    answer: str
    decision: str
    strategy: str
    cache_entry_id: UUID | None = None
    similarity: float | None = None
    metrics: RequestMetrics
```

---

## 9. Module Structure

```text
major/
├── docs/
│   ├── SSCRE_PLAN.md
│   └── SSCRE_SYSTEM_DESIGN.md
├── src/
│   └── sscre/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app factory
│       ├── config.py               # pydantic-settings
│       ├── api/
│       │   ├── routes/
│       │   │   ├── query.py
│       │   │   ├── cache.py
│       │   │   └── evaluate.py
│       │   └── deps.py             # DI: db session, clients
│       ├── domain/
│       │   ├── models.py           # QueryMetadata, SafetyResult, etc.
│       │   ├── preprocessor.py
│       │   ├── fingerprint.py
│       │   ├── freshness.py
│       │   └── safety/
│       │       ├── engine.py
│       │       ├── strategy_a.py
│       │       ├── strategy_b.py
│       │       ├── strategy_c.py
│       │       └── strategy_d.py     # Phase 3
│       ├── services/
│       │   ├── orchestrator.py
│       │   ├── cache_writer.py
│       │   └── eviction.py
│       ├── infra/
│       │   ├── db/
│       │   │   ├── session.py
│       │   │   └── cache_repository.py
│       │   ├── embedding_client.py
│       │   └── llm_client.py
│       ├── eval/
│       │   ├── runner.py
│       │   ├── metrics.py
│       │   └── datasets/
│       └── observability/
│           ├── logging.py
│           └── metrics.py
├── experiments/
│   └── threshold_sweep_v1.yaml
├── benchmarks/
│   └── v1/
│       └── pairs.jsonl
├── scripts/
│   ├── migrate.sql
│   └── seed_benchmark.py
├── tests/
│   ├── unit/
│   └── integration/
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## 10. Configuration

`pydantic-settings` from environment + `.env`:

```yaml
# config defaults
app:
  name: sscre
  env: development
  log_level: INFO

cache:
  max_entries: 10000
  max_bytes: 100000000
  top_k: 5
  store_query_text: true          # false in production for storage savings
  default_strategy: C
  tau_low: 0.80
  tau_high: 0.92

freshness:
  stable_ttl_days: 30
  semi_dynamic_ttl_hours: 24
  dynamic_cache_enabled: false

embedding:
  provider: openai
  model: text-embedding-3-small
  dimensions: 1536
  timeout_seconds: 10

llm:
  provider: openai
  model: gpt-4o-mini
  max_output_tokens: 2048
  timeout_seconds: 60

database:
  url: postgresql+asyncpg://sscre:sscre@localhost:5432/sscre

eval:
  results_dir: ./experiments/results
```

---

## 11. Deployment

### 11.1 Deployment Topology

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    USER["Client app · Eval CLI<br/><sub>External consumers</sub>"]

    subgraph docker["Docker Compose · local / demo"]
        subgraph api_container["api service"]
            FAST["FastAPI container<br/><sub>uvicorn :8000</sub>"]
        end
        subgraph db_container["postgres service"]
            PG["Postgres + pgvector<br/><sub>:5432 · pgdata volume</sub>"]
        end
    end

    EMB["Embedding provider<br/><sub>External API</sub>"]
    LLM["LLM provider<br/><sub>External API</sub>"]

    USER -->|HTTP| FAST
    FAST <-->|SQL + vector| PG
    FAST --> EMB
    FAST --> LLM

    classDef external fill:#444444,stroke:#888888,color:#ffffff
    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff

    class USER,EMB,LLM external
    class FAST app
    class PG data

    style docker fill:#000000,stroke:#ffffff,stroke-dasharray:8 4
    style api_container fill:#000000,stroke:#ffffff,stroke-dasharray:8 4
    style db_container fill:#004D40,stroke:#ffffff
```

### 11.2 Docker Compose (MVP)

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres]
    command: uvicorn sscre.main:app --host 0.0.0.0 --port 8000

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: sscre
      POSTGRES_PASSWORD: sscre
      POSTGRES_DB: sscre
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/migrate.sql:/docker-entrypoint-initdb.d/01_schema.sql
    ports: ["5432:5432"]

  # Phase 2
  # dashboard:
  #   build: .
  #   command: streamlit run dashboard/app.py
  #   ports: ["8501:8501"]

volumes:
  pgdata:
```

### 11.3 Environment Separation

| Env | Purpose | Cache cap | LLM |
|-----|---------|-----------|-----|
| **local** | dev | 10 MB | mock or cheap model |
| **eval** | benchmark runs | reset per run | fixed model version |
| **demo** | viva / presentation | 100 MB | single provider |

---

## 12. Non-Functional Requirements

| NFR | MVP Target | Measurement |
|-----|------------|-------------|
| **p50 latency (cache hit)** | < 150 ms | request_logs |
| **p50 latency (generate)** | dominated by LLM | request_logs |
| **FPR** | ≤ 3% at operating τ | evaluation harness |
| **Cache storage** | ≤ 100 MB | stats endpoint |
| **Availability** | best-effort (academic) | — |
| **Throughput** | 10 req/s local | load test Phase 3 |
| **Reproducibility** | same config → ±1% metrics | experiment_runs |

---

## 13. Observability

### 13.1 Per-Request Metrics (stored in `request_logs`)

- `embed_latency_ms`, `search_latency_ms`, `safety_latency_ms`, `llm_latency_ms`
- `llm_input_tokens`, `llm_output_tokens`
- `decision`, `outcome`, `similarity`, `strategy`

### 13.2 Aggregates (computed for dashboard)

- Hit rate, FPR, precision, recall (rolling 24h + all-time)
- Tokens saved vs baseline (counterfactual: assume all misses → generate)
- Cache bytes, entries, eviction rate
- Failure breakdown by `failure_type`

### 13.3 Logging

Structured JSON logs:

```json
{
  "event": "cache_decision",
  "request_id": "...",
  "decision": "SAFE",
  "similarity": 0.91,
  "strategy": "C",
  "candidate_count": 5,
  "latency_ms": 94
}
```

Do **not** log full API keys or complete answers in production logs (storage + privacy).

---

## 14. Security

| Concern | MVP Approach |
|---------|--------------|
| **API keys** | Environment variables only; never in DB |
| **Admin endpoints** | API key header `X-Admin-Key` (Phase 1 simple) |
| **Input validation** | Pydantic max length 8000 chars |
| **SQL injection** | Parameterized queries / SQLAlchemy |
| **Cache poisoning** | Only insert from trusted LLM path; no user-supplied cache writes |
| **PII** | Out of scope; document as limitation |

---

## 15. Scaling & Bottlenecks

### Expected Bottleneck Order (validate in Phase 3 load test)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart TB
    REQ["Incoming queries<br/><sub>load test · 1K–100K/day</sub>"]
    B1["1 · LLM API rate limits<br/><sub>cache miss path</sub>"]
    B2["2 · Embedding throughput<br/><sub>every non-exact query</sub>"]
    B3["3 · pgvector search latency<br/><sub>grows with entries</sub>"]
    B4["4 · Postgres write contention<br/><sub>insert + increment_hit</sub>"]
    B5["5 · Safety rule CPU<br/><sub>negligible at MVP scale</sub>"]

    REQ --> B1 --> B2 --> B3 --> B4 --> B5

    classDef external fill:#444444,stroke:#888888,color:#ffffff
    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff

    class REQ external
    class B1,B2,B3,B4,B5 app
```

### Scaling Levers

| Bottleneck | Mitigation |
|------------|------------|
| Embedding | Batch embed in eval; optional local model (e.g. sentence-transformers) |
| Vector search | Tune IVFFlat `lists`; HNSW index; migrate to Qdrant if >1M vectors |
| LLM cost | Higher hit rate via better compatibility (not lower τ blindly) |
| Storage | int8 embeddings, omit query_text, aggressive dedup |
| Read load | Read replicas (Postgres) — only if needed |

### Horizontal Scaling (future)

- Stateless API containers behind load balancer
- Shared PostgreSQL
- Sticky sessions **not** required (cache is global, not per-instance)

---

## 16. Failure Handling

| Failure | Behavior |
|---------|----------|
| Embedding API down | Return 503; do not serve stale unsafe cache |
| LLM API down | Return 503 with partial trace; log miss reason |
| DB down | Return 503; optional degrade: passthrough to LLM without cache (config flag) |
| Vector search timeout | Treat as miss → generate |
| Storage cap reached | Evict LRU then retry insert once |
| Safety engine exception | Fail closed → UNCERTAIN → generate |

**Fail-closed principle:** when in doubt, generate. Never serve cache on infrastructure errors.

---

## 17. Phase Mapping

| Component | Phase 1 (MVP) | Phase 2 | Phase 3 |
|-----------|---------------|---------|---------|
| QueryOrchestrator | ✓ | ✓ | ✓ |
| Strategies A, B, C | ✓ | ✓ | ✓ |
| Strategy D (cross-encoder) | — | — | if justified |
| Single LLM fallback | ✓ | ✓ | ✓ |
| Dual LLM comparison | — | ✓ | ✓ |
| Streamlit dashboard | — | ✓ | ✓ |
| Failure gallery API | basic | full | + clustering |
| LRU + TTL eviction | ✓ | ✓ | ✓ |
| Evaluation CLI | ✓ | + sweeps | + load test |
| int8 embeddings | — | — | ✓ |

---

## Summary

SSCRE is a **single-service FastAPI application** backed by **PostgreSQL + pgvector**, with a pluggable **Safety Engine** at its core. The critical path is:

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'background': '#000000', 'lineColor': '#ffffff'}}}%%
flowchart LR
    A["Preprocessor<br/><sub>fingerprint</sub>"]
    B["Exact lookup<br/><sub>Strategy A</sub>"]
    C["Embed query<br/><sub>external API</sub>"]
    D["Vector search<br/><sub>pgvector</sub>"]
    E["Safety engine<br/><sub>Strategy C</sub>"]
    F["Serve cache<br/><sub>0 LLM tokens</sub>"]
    G["LLM client<br/><sub>miss fallback</sub>"]
    H["Cache writer<br/><sub>dedup insert</sub>"]

    A --> B
    B -->|miss| C --> D --> E
    E -->|SAFE| F
    E -->|UNSAFE / UNCERTAIN| G --> H

    classDef app fill:#4B4497,stroke:#ffffff,color:#ffffff
    classDef data fill:#004D40,stroke:#ffffff,color:#ffffff
    classDef external fill:#444444,stroke:#888888,color:#ffffff

    class A,B,E,F,G,H app
    class D data
    class C external
```

Build the **evaluation harness** in parallel with the live path — the project's value is proven through measured trade-offs, not through UI complexity.

**Next implementation step:** scaffold `src/sscre/` per module structure, run `migrate.sql`, implement Strategy A+C with mock LLM, then wire real providers.
