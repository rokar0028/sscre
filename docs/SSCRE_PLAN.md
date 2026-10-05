# Safe Semantic LLM Response Reuse (SSCRE)

**Retrieval-Cached Model-Comparison Answer Engine**

> A reproducible experimental platform that decides when a previously generated LLM response can be **safely reused** for a new query — using semantic retrieval, compatibility validation, model-comparison fallback, and rigorous evaluation of accuracy, cost, latency, freshness, and **storage footprint**.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Identity](#2-project-identity)
3. [Central Research Question](#3-central-research-question)
4. [Objectives & Non-Goals](#4-objectives--non-goals)
5. [Design Principles](#5-design-principles)
6. [High-Level Architecture](#6-high-level-architecture)
7. [Request Pipeline](#7-request-pipeline)
8. [Semantic Cache](#8-semantic-cache)
9. [Cache Safety Engine](#9-cache-safety-engine)
10. [Cache Storage Optimization](#10-cache-storage-optimization)
11. [Token & Cost Model](#11-token--cost-model)
12. [Model-Comparison Fallback](#12-model-comparison-fallback)
13. [Freshness-Aware Caching](#13-freshness-aware-caching)
14. [Benchmark Dataset](#14-benchmark-dataset)
15. [Evaluation Harness](#15-evaluation-harness)
16. [Metrics & Operating Point](#16-metrics--operating-point)
17. [Baselines & Experiments](#17-baselines--experiments)
18. [Failure Analysis](#18-failure-analysis)
19. [Technology Stack](#19-technology-stack)
20. [Phased Roadmap](#20-phased-roadmap)
21. [Data Model & API Sketch](#21-data-model--api-sketch)
22. [Prior Art](#22-prior-art)
23. [Risks & Mitigations](#23-risks--mitigations)
24. [Deliverables & Success Criteria](#24-deliverables--success-criteria)
25. [Further Improvements](#25-further-improvements)

---

## 1. Executive Summary

LLM systems often receive queries that are identical or semantically related to queries already answered. Re-generating every time wastes **tokens**, **money**, and **latency** — but naive semantic caching produces **false positives** when similar queries have different constraints.

**SSCRE** is a B.Tech major project that builds a **wrapper layer** any LLM-backed system can sit behind. It:

1. Retrieves semantically similar cached answers.
2. Validates **compatibility** (not just similarity).
3. Serves cached responses only when **SAFE**.
4. Falls back to generation (optionally dual-model comparison) when **UNSAFE** or **UNCERTAIN**.
5. Measures everything through a **reproducible evaluation harness**.

**Primary outcome:** an evidence-backed operating point — not maximum hit rate — that balances reuse, safety, cost, latency, and **minimal cache storage**.

---

## 2. Project Identity

| Field | Value |
|-------|-------|
| **Working title** | Safe Semantic LLM Response Reuse (SSCRE) |
| **Type** | Final-year B.Tech major project (research + engineering) |
| **Not** | Commercial startup, generic chatbot, browser extension product |

**Demonstrates depth in:** LLM systems, semantic retrieval, vector search, caching, evaluation, backend engineering, performance optimization, system design.

---

## 3. Central Research Question

Large language model systems often process queries that are identical or semantically related to queries they have already answered.

Re-generating an answer for every query causes:

- unnecessary model/API cost (tokens)
- additional latency
- repeated computation
- inconsistent outputs

Semantic caching is a potential solution — but:

> **High embedding similarity ≠ interchangeable queries.**

```text
Query A: "Give me Python code for binary search."
Query B: "Give me Java code for binary search."
→ Semantically close, different constraints → UNSAFE to reuse
```

**Central question:**

> How can a system determine whether a previously generated answer is **safe to reuse**, while minimizing downstream model tokens and latency **without significantly increasing incorrect responses** — and while keeping cache storage bounded?

---

## 4. Objectives & Non-Goals

### Objectives

The cache-decision pipeline will:

1. Receive a user query.
2. Search semantic cache for prior queries.
3. Retrieve top-K candidate answers with scores.
4. Determine compatibility with the new query.
5. Serve cached response when confidence is **SAFE**.
6. Fall back to LLM generation when **UNSAFE** or **UNCERTAIN**.
7. Optionally compare two model outputs on fallback.
8. Record human preference and correctness independently.
9. Store eligible responses for future reuse (compactly).
10. Measure effectiveness via reproducible evaluation.

### Optimization Target (not max hit rate)

```text
Cache Reuse
  + Low False-Positive Rate
  + Lower Downstream Token Cost
  + Lower Latency
  + Acceptable Freshness
  + Bounded Cache Storage
```

### Non-Goals (out of scope)

- Browser search interception / extension as main product
- Prompt marketplace, monetization, social features
- Unnecessary agent frameworks or full RAG pipelines
- Features added only to inflate scope

**Principle:** depth over feature count.

---

## 5. Design Principles

These principles align the project with its role as a **token-reducing wrapper** with **minimal cache footprint**.

### 5.1 Wrapper-First

SSCRE sits between client and LLM provider:

```text
Client → SSCRE (retrieve → validate → serve|generate) → LLM API
```

Downstream tokens are spent **only on cache miss or UNCERTAIN**. Wrapper overhead must stay below savings.

### 5.2 Conservative by Default

When evidence is insufficient → **UNCERTAIN → generate**. Never guess on ambiguous similarity.

### 5.3 Store Decisions, Not Duplicates

Cache stores **one canonical answer per semantic cluster** where possible. Metadata is derived or fingerprinted, not duplicated verbatim.

### 5.4 Measurable Everything

Every strategy (A/B/C/D) must produce comparable metrics. No component without a measurable question.

### 5.5 Bounded Resources

Hard caps on cache size, entry TTL, and validator cost. Eviction is a first-class feature, not an afterthought.

---

## 6. High-Level Architecture

```text
                              USER QUERY
                                  |
                                  v
                         Query Preprocessing
                         (normalize + fingerprint)
                                  |
                                  v
                           Query Embedding
                                  |
                                  v
                          Semantic Cache Search
                                  |
                               Top-K
                                  |
                                  v
                    +---------------------------+
                    |    Cache Safety Engine    |
                    |  Similarity | Intent      |
                    |  Constraints | Freshness  |
                    |  Domain | Format          |
                    +-------------+-------------+
                                  |
                     +------------+------------+
                     |            |            |
                     v            v            v
                   SAFE        UNSAFE      UNCERTAIN
                     |            |            |
                     v            +------+-----+
               Cached Answer            |
               (0 LLM tokens)            v
                               Model A + Model B (parallel)
                                         |
                                         v
                                 Model Comparison
                                         |
                                         v
                           Preference / Correctness
                                         |
                                         v
                           Compact Cache Insert
                                         |
                                         v
                                Semantic Cache

                         Evaluation Harness
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
          Safety            Cost/Tokens        Latency
             |                  |                  |
             +------------------+------------------+
                                |
                                v
                    Failure Analysis + Storage Growth
```

---

## 7. Request Pipeline

### 7.1 Query Processing Layer

| Step | Action | Storage impact |
|------|--------|----------------|
| 1 | Assign `request_id`, timestamp | Log row only |
| 2 | Normalize whitespace, casing (optional) | — |
| 3 | Compute **constraint fingerprint** | Small hash, not full text |
| 4 | Generate embedding | Vector (fixed dim) |
| 5 | Extract lightweight metadata (rules-based MVP) | JSON blob, capped size |

**Extracted metadata (MVP — rule/regex based, no extra LLM call):**

```text
intent          e.g. explain | code | compare | factual
domain          e.g. programming | finance | general
entities        e.g. [Python, binary search]
constraints     e.g. {language: Java, format: code}
temporal_class  stable | semi_dynamic | dynamic
output_format   prose | code | list | json
```

Keep preprocessing **lightweight**. Do not call an LLM for metadata in MVP.

### 7.2 Three-State Decision (canonical naming)

Use consistently everywhere:

| State | Meaning | Action |
|-------|---------|--------|
| **SAFE** | Cached answer is compatible | Serve cache (0 downstream tokens) |
| **UNSAFE** | Cached answer is incompatible | Generate; do not serve cache |
| **UNCERTAIN** | Insufficient evidence | Generate (conservative) |

> Previously mixed "SAFE MISS" / "UNSAFE" — **UNSAFE** means "do not reuse this candidate," not "cache miss." A query can miss cache because no candidates exist *or* because all candidates are UNSAFE.

---

## 8. Semantic Cache

### 8.1 Cache Entry (logical)

```text
CacheEntry
├── id                    UUID
├── query_hash            SHA-256 of normalized query (dedup key)
├── query_text            Original query (optional if hash-hit only)
├── embedding             float[] — consider int8 quantization at scale
├── answer_ref            Pointer to canonical answer blob
├── answer_hash           SHA-256 of answer (dedup identical answers)
├── constraint_fingerprint
├── metadata              Compact JSON (see §7.1)
├── model_source          Which model generated answer
├── preference_label      A | B | tie | null
├── correctness_label     correct | incorrect | uncertain | null
├── validation_status     auto | human | null
├── freshness_class       stable | semi_dynamic | dynamic
├── ttl_expires_at        Timestamp
├── hit_count             Usage counter
├── created_at
└── updated_at
```

### 8.2 Retrieval Flow

```text
New Query → Embedding → Vector Search → Top-K → Per-candidate Safety Score → Best SAFE or Fallback
```

Retain similarity scores. Top-1 is **never** auto-served without safety check.

Example scores:

```text
Candidate 1 → similarity 0.94 → compatibility UNCERTAIN → skip
Candidate 2 → similarity 0.89 → compatibility SAFE     → serve
Candidate 3 → similarity 0.87 → compatibility UNSAFE     → skip
```

---

## 9. Cache Safety Engine

**Core question:** Can this cached answer safely answer the new query?

### 9.1 Strategy Progression

| Strategy | Logic | Purpose |
|----------|-------|---------|
| **A — Exact match** | Normalized query hash equality | Baseline; zero false positives |
| **B — Embedding only** | `similarity ≥ τ → SAFE` | Naïve baseline; measure false positives |
| **C — Embedding + compatibility** | Similarity filter → rule/feature check | **Primary proposed approach** |
| **D — Advanced validator** | Cross-encoder / classifier / LLM judge | Only if C insufficient |

### 9.2 Strategy C — Compatibility Check (MVP rules)

```python
# Pseudocode — no LLM required
def compatibility(query_meta, cache_meta, similarity) -> Literal["SAFE", "UNSAFE", "UNCERTAIN"]:
    if similarity < TAU_LOW:
        return "UNSAFE"
    if query_meta.constraint_fingerprint == cache_meta.constraint_fingerprint:
        if similarity >= TAU_HIGH:
            return "SAFE"
    if mismatched(query_meta.constraints, cache_meta.constraints):  # language, entity, format
        return "UNSAFE"
    if query_meta.temporal_class == "dynamic":
        return "UNCERTAIN"
    if similarity >= TAU_HIGH and query_meta.intent == cache_meta.intent:
        return "UNCERTAIN"  # conservative unless fingerprint matches
    return "UNSAFE"
```

**Compatibility features to check:**

- intent, constraints, entities, output format, domain, temporal class

### 9.3 Strategy D — When to Add

Add advanced validators **only if** Strategy C false-positive rate remains above target after threshold tuning. Measure validator cost vs tokens saved.

---

## 10. Cache Storage Optimization

> Goal: **minimal cache storage** while preserving safe reuse.

### 10.1 Storage Budget (recommended defaults)

```yaml
cache:
  max_entries: 10_000           # MVP; tune in experiments
  max_bytes: 100_000_000        # 100 MB hard cap
  eviction: lru + ttl
  embedding_storage: float32      # MVP; int8 in Phase 3
  store_query_text: false         # hash-only after validation (optional)
  answer_dedup: true              # content-addressable by answer_hash
```

### 10.2 What to Store vs Derive

| Store | Derive on read | Omit |
|-------|----------------|------|
| embedding, answer, fingerprints | metadata from query if needed | duplicate schemas |
| TTL, hit_count | — | full evaluation transcripts |
| compact metadata JSON | — | raw LLM reasoning chains |

### 10.3 Deduplication Strategy

```text
Same answer_hash + compatible fingerprint cluster → increment hit_count, do not duplicate row
Same query_hash → exact hit, no re-embed
Similar embedding + same answer_hash → merge metadata, single canonical entry
```

### 10.4 Growth Controls

- **LRU eviction** when `max_entries` or `max_bytes` exceeded
- **TTL by freshness_class:** stable=30d, semi_dynamic=24h, dynamic=no cache
- **Periodic compaction job:** drop entries with `hit_count=0` past TTL
- **Monitor:** `cache_bytes`, `entries`, `avg_entry_bytes`, `dedup_savings_ratio`

### 10.5 Anti-Patterns (inflates storage)

- Storing full conversation history per entry
- Duplicate embeddings for paraphrased queries with identical answers
- Caching raw dual-model outputs without selecting one canonical answer
- Unbounded metadata blobs from LLM extractors

---

## 11. Token & Cost Model

### 11.1 Per-Request Token Paths

| Path | Downstream LLM tokens | Wrapper cost |
|------|----------------------|--------------|
| Exact hit (A) | 0 | embed + search |
| SAFE semantic hit (C) | 0 | embed + search + rule check |
| UNCERTAIN / UNSAFE | full generation | embed + search + check + generate |
| Dual-model fallback | 2× generation | above + comparison |

**Wrapper overhead budget:** wrapper tokens/cost must be **< 10%** of tokens saved vs no-cache baseline at target operating point.

### 11.2 Cost Formula (evaluation harness)

```text
cost = (n_embed × embed_price)
     + (n_search × search_price)
     + (n_generate × avg_output_tokens × token_price)
     + (n_validator × validator_price)
     + infrastructure_amortized

tokens_saved = baseline_generate_tokens - cached_system_generate_tokens
cost_saved   = baseline_cost - cached_system_cost
```

Track separately: **embedding tokens**, **generation tokens**, **validator tokens**.

### 11.3 Break-Even Hit Rate

```text
hit_rate_break_even ≈ wrapper_cost_per_query / avg_generation_cost_per_query
```

Report this in experiments — caching is worthless below break-even.

---

## 12. Model-Comparison Fallback

When cache cannot safely answer:

```text
Query → Model A ∥ Model B → Comparison UI → Human preference → Canonical answer → Cache insert
```

### 12.1 Label Separation (critical)

| Label | Question |
|-------|----------|
| **Preference** | Which response does the evaluator prefer? |
| **Correctness** | Is the response factually correct? |
| **Compatibility** | Can this answer be reused for a *different* query? |

Preference ≠ correctness. Only **correct + compatible** answers should enter cache with high confidence.

### 12.2 MVP Simplification

**Phase 1:** single-model fallback (cheaper, simpler metrics).

**Phase 2:** dual-model comparison for preference collection and quality analysis.

Dual-model is valuable for **evaluation**, not required to prove caching hypothesis.

---

## 13. Freshness-Aware Caching

| Class | Example | TTL policy |
|-------|---------|------------|
| **Stable** | "What is binary search?" | Long (days–weeks) |
| **Semi-dynamic** | "Latest Python version?" | Short (hours–days) |
| **Dynamic** | "NVIDIA stock price now?" | No cache or seconds |

**MVP:** rule-based temporal class from keywords (`now`, `today`, `current`, `latest` → dynamic).

**Phase 2:** domain-specific TTL tables + explicit invalidation on benchmark.

---

## 14. Benchmark Dataset

Deliberately difficult query relationships. Target **≥500 labeled pairs** for statistical usefulness (Phase 2: 2,000+).

| Category | Example | Expected |
|----------|---------|----------|
| **1 — Exact duplicate** | Same question twice | SAFE |
| **2 — Paraphrase** | "What is binary search?" / "Explain binary search" | SAFE or UNCERTAIN |
| **3 — Different intent** | Time complexity vs space complexity | UNSAFE |
| **4 — Different constraint** | Python vs Java code | UNSAFE |
| **5 — Different context** | TCP for beginners vs congestion control math | UNSAFE |
| **6 — Entity difference** | AWS Lambda vs Azure Functions pricing | UNSAFE |
| **7 — Temporal difference** | Current price vs last year | UNSAFE |
| **8 — Format difference** | Explain vs executable code | UNSAFE |

Each row: `(query_a, query_b, expected_decision, failure_category_if_wrong)`.

---

## 15. Evaluation Harness

Core deliverable. CLI-driven, versioned configs, reproducible outputs.

### 15.1 Experiment Config

```yaml
experiment:
  name: threshold_sweep_v1
  dataset: benchmark_v1
  embedding_model: text-embedding-3-small
  vector_store: pgvector
  top_k: 5
  strategy: C                    # A | B | C | D
  tau_low: 0.80
  tau_high: 0.92
  freshness_policy: default
  model_pair: [gpt-4o-mini, claude-haiku]  # optional Phase 2
  cache_max_bytes: 100000000
```

### 15.2 Run Command

```bash
python -m sscre evaluate --config experiments/threshold_sweep_v1.yaml
```

### 15.3 Output Report

```text
Evaluation Run — threshold_sweep_v1
────────────────────────────────────
Dataset: benchmark_v1 (500 pairs)
Strategy: C | τ_high=0.92 | embed=text-embedding-3-small

Cache Hit Rate:           34.2%
False Positive Rate:      2.1%  (of hits)
Cache Precision:          97.9%
Cache Recall (coverage):  61.3%

P50 Latency Reduction:    820ms
Tokens Saved vs Baseline: 38.4%
Cost Saved:               $0.042/query
Cache Storage:            12.4 MB (847 entries)
Break-even Hit Rate:      8.2%  ✓ exceeded

Top Failure Categories:
  constraint_mismatch (41%)
  entity_mismatch (23%)
  embedding_false_positive (19%)
```

---

## 16. Metrics & Operating Point

### 16.1 Primary Metrics

| Metric | Formula | Notes |
|--------|---------|-------|
| **Hit rate** | `cache_hits / total_queries` | Secondary to safety |
| **False-positive rate (FPR)** | `incorrect_cache_hits / total_cache_hits` | **Most important** |
| **Cache precision** | `correct_cache_hits / total_cache_hits` | = 1 − FPR |
| **Cache recall** | `correct_hits / all_reusable_pairs` | Coverage |
| **F1 (cache decision)** | Harmonic mean of precision & recall | Single summary score |
| **Latency** | p50, p95, p99 vs baselines | Include tail |
| **Tokens saved** | `1 − (gen_tokens_capped / gen_tokens_baseline)` | Downstream only |
| **Cost saved** | See §11.2 | Include embed/search overhead |
| **Storage efficiency** | `bytes_per_entry`, `dedup_ratio` | Must stay bounded |

### 16.2 Operating Point Selection

Do not maximize hit rate. Select τ and strategy where:

```text
FPR ≤ target (e.g. 3%)
AND tokens_saved ≥ target (e.g. 25%)
AND cache_bytes ≤ cap
```

Plot **Pareto frontier:** FPR vs tokens_saved vs latency vs storage.

### 16.3 Threshold Experiment Table

| τ_high | Hit Rate | FPR | Precision | Tokens Saved | P95 Latency | Cache MB |
|--------|----------|-----|-----------|--------------|-------------|----------|
| 0.80 | TBD | TBD | TBD | TBD | TBD | TBD |
| 0.85 | TBD | TBD | TBD | TBD | TBD | TBD |
| 0.90 | TBD | TBD | TBD | TBD | TBD | TBD |
| 0.95 | TBD | TBD | TBD | TBD | TBD | TBD |

---

## 17. Baselines & Experiments

### 17.1 Required Baselines

| # | Name | Description |
|---|------|-------------|
| 1 | **No cache** | Every query → generate |
| 2 | **Exact match** | Hash equality only |
| 3 | **Embedding only** | Strategy B |
| 4 | **Proposed** | Strategy C (+ D if justified) |

### 17.2 Experimental Questions

**Embeddings:** Which model gives best decision quality per dollar?

**Similarity:** How does τ affect FPR? Does top-K > 1 improve recall safely?

**Compatibility:** Which features catch embedding false positives?

**Freshness:** Do TTL classes reduce stale failures?

**Economics:** At what hit rate does caching break even including embed cost?

**Storage:** What is entry growth rate at 10K queries/day with dedup vs without?

**Scaling:** First bottleneck at 100K queries/day — embed, search, DB, or LLM?

---

## 18. Failure Analysis

Every incorrect or UNCERTAIN→SAFE failure must be inspectable:

```text
CACHE FAILURE #1847
─────────────────────
New Query:      "Give me Java code for binary search."
Cached Query:   "Give me Python code for binary search."
Similarity:     0.94
Compatibility:  SAFE (wrong)
Expected:       UNSAFE
Failure Type:   constraint_mismatch (language)
Strategy:       B (embedding only)
```

**Failure categories:** intent, constraint, entity, temporal, stale, format, domain, embedding FP, validator FP.

Build a **failure gallery** — strong viva material.

---

## 19. Technology Stack

| Layer | Recommendation | Rationale |
|-------|----------------|-----------|
| **Backend** | Python 3.12+, FastAPI | Async, Pydantic validation, fits wrapper pattern |
| **DB** | PostgreSQL + pgvector | Relational + vector in one system; simpler ops |
| **Embeddings** | Configurable provider | Avoid hard-coding one vendor |
| **Evaluation** | pandas, matplotlib, custom CLI | Reproducible sweeps |
| **Frontend** | Streamlit (MVP) → optional React | UI secondary to harness |
| **Deploy** | Docker Compose | After local eval succeeds |

**Avoid for MVP:** Qdrant + Postgres + Redis + agent framework — operational overhead without proven benefit.

### 19.1 Wrapper Integration Pattern

```text
POST /v1/query  { "query": "...", "session_id": "..." }
→ SSCRE pipeline
→ { "source": "cache"|"generated", "answer": "...", "metrics": {...} }
```

Drop-in proxy for any client currently calling an LLM API directly.

---

## 20. Phased Roadmap

### Phase 1 — MVP (Weeks 1–6)

#### Foundation

- [x] Create `src/sscre/` package
- [x] Create unit and integration test directories
- [x] Add `pyproject.toml` and development dependencies
- [ ] Add application configuration
- [x] Add `GET /health`
- [x] Add a repeatable local test command

#### Exact-cache vertical slice

- [x] Define query and response schemas
- [x] Normalize query input
- [x] Compute query hashes
- [x] Implement in-memory exact lookup
- [x] Implement mock LLM fallback
- [x] Implement `POST /v1/query`
- [x] Return cache/generated source
- [x] Add request IDs and latency metrics
- [x] Test hit, miss, invalid input, and generation failure

#### Persistence and evaluation

- [x] Add PostgreSQL migration
- [x] Implement cache repository interface
- [x] Implement exact-match PostgreSQL repository
- [ ] Define benchmark JSONL schema
- [ ] Create benchmark v1 with ≥100 reviewed pairs
- [ ] Implement no-cache baseline
- [ ] Implement exact-match baseline
- [ ] Add `evaluate` CLI command
- [ ] Report hit rate, reuse coverage, tokens, cost, and latency

#### Semantic MVP

- [ ] Enable pgvector
- [ ] Add embedding client interface
- [ ] Add deterministic fake embeddings for tests
- [ ] Implement top-K vector retrieval
- [ ] Implement similarity-only Strategy B
- [ ] Implement minimal rule-based Strategy C
- [ ] Add single-model fallback
- [ ] Add answer deduplication
- [ ] Add freshness classification
- [ ] Add TTL checks before every cache hit
- [ ] Add storage cap and LRU eviction

### Phase 2 — Depth (Weeks 7–10)

- [ ] Define and test `SAFE`, `UNSAFE`, and `UNCERTAIN`
- [ ] Add candidate-level decision traces
- [ ] Expand benchmark to ≥500 reviewed pairs
- [ ] Create development and held-out test splits
- [ ] Add threshold sweep configuration
- [ ] Generate Pareto plots
- [ ] Add confidence intervals
- [ ] Add human correctness labels
- [ ] Keep preference and correctness labels separate
- [ ] Add freshness policy experiments
- [ ] Build failure gallery
- [ ] Add failure-category metrics
- [ ] Add dashboard only after reports are stable
- [ ] Add dual-model comparison only for a defined experiment

### Phase 3 — Advanced (Weeks 11–14, if justified)

- [ ] Write a hypothesis and pass/fail criterion
- [ ] Implement cross-encoder validator (D) only if C misses the target
- [ ] Compare validator latency and safety improvement
- [ ] Measure embedding storage before quantization
- [ ] Test int8 embedding quantization
- [ ] Run load tests from 1K to 100K simulated queries/day
- [ ] Identify the first bottleneck
- [ ] Test adaptive thresholds by domain
- [ ] Cluster recurring failures
- [ ] Add experiment tracking only if manual reports are insufficient

**Rule:** Phase 3 features require a written hypothesis + pass/fail criterion before implementation.

---

## 21. Data Model & API Sketch

### 21.1 SQL (minimal)

```sql
CREATE TABLE cache_entries (
  id UUID PRIMARY KEY,
  query_hash CHAR(64) NOT NULL,
  query_text TEXT,
  embedding vector(1536),
  answer_hash CHAR(64) NOT NULL,
  answer_text TEXT NOT NULL,
  constraint_fingerprint CHAR(64),
  metadata JSONB NOT NULL DEFAULT '{}',
  freshness_class TEXT NOT NULL DEFAULT 'stable',
  ttl_expires_at TIMESTAMPTZ,
  hit_count INT NOT NULL DEFAULT 0,
  model_source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cache_embedding ON cache_entries USING ivfflat (embedding vector_cosine_ops);
CREATE UNIQUE INDEX idx_cache_query_hash ON cache_entries (query_hash);
CREATE INDEX idx_cache_answer_hash ON cache_entries (answer_hash);
```

### 21.2 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/query` | Main wrapper endpoint |
| GET | `/v1/cache/stats` | Hit rate, bytes, entries |
| POST | `/v1/evaluate/run` | Trigger harness (admin) |
| GET | `/v1/failures` | Paginated failure gallery |
| DELETE | `/v1/cache/purge` | TTL eviction / manual purge |

---

## 22. Prior Art

| System / Work | Relation to SSCRE |
|---------------|-------------------|
| **GPTCache** | Semantic cache for LLM apps — compare architecture & FPR |
| **CachedBench / research on LLM caching** | Evaluation methodology |
| **Chatbot Arena** | Preference collection — we do **cache safety**, not leaderboards |
| **RAG** | Retrieves external docs — we reuse **generated answers** |
| **Cross-encoders (MS MARCO)** | Reranking — applicable as Strategy D |
| **CDN / HTTP caching** | Exact-match analog — Strategy A baseline |
| **Prompt caching (provider-side)** | Complementary — SSCRE is application-layer semantic reuse |

Related-work section must cite 5–8 papers/products with explicit differentiation.

---

## 23. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Embedding false positives | Wrong answers served | Strategy C rules; conservative UNCERTAIN |
| Cache storage bloat | Cost, slow search | Dedup, caps, LRU, optional query_text omission |
| Dual-model cost in MVP | Budget overrun | Single model Phase 1; dual Phase 2 |
| Benchmark too small | Weak conclusions | ≥500 pairs; report confidence intervals |
| pgvector scale limits | Latency at 100K+ | IVFFlat tuning; Qdrant migration path documented |
| Stale factual answers | User trust | Freshness classes; dynamic = no cache |
| Over-engineering | Miss deadline | Phase gates; hypothesis-driven Phase 3 |

---

## 24. Deliverables & Success Criteria

### Software

- FastAPI wrapper API
- Semantic cache + safety engine
- Evaluation harness (CLI)
- Benchmark dataset with labels
- Streamlit dashboard (metrics + failures)
- Docker Compose deployment

### Documentation

- Problem statement, architecture, schema, API docs
- Methodology, experiment configs, results, failure analysis
- Limitations + honest "when not to cache" section

### Success Criteria

1. Semantic caching reduces downstream generation tokens for a meaningful query subset.
2. Embedding-only caching (B) produces **measurable** false positives on benchmark.
3. Compatibility-aware caching (C) **reduces** FPR vs (B) at comparable or better tokens saved.
4. Cost/latency reduction quantified with wrapper overhead included.
5. Failures categorized and inspectable.
6. Results reproducible from fixed config + dataset version.
7. Cache storage stays within configured cap under load test.
8. Defensible conclusion: **where reuse works, where it fails, and why.**

---

## 25. Further Improvements

Suggestions beyond current scope — prioritize by experiment evidence:

| Improvement | Benefit | Cost |
|-------------|---------|------|
| **Constraint fingerprint via small NER** | Better UNSAFE detection | Dev time |
| **Cross-encoder reranker (D)** | Lower FPR at same hit rate | +latency per candidate |
| **int8 embedding quantization** | ~4× storage reduction | Minimal accuracy loss |
| **Session-aware cache** | Higher safe hit rate in dialogs | Storage ↑ — use sliding window |
| **Cache warming from logs** | Higher initial hit rate | Offline batch embed cost |
| **Multi-tenant isolation** | Production readiness | Schema + auth complexity |
| **Online τ adaptation** | Optimize operating point live | Complexity; needs guardrails |
| **Synthetic benchmark generation** | Scale dataset cheaply | Label quality risk |
| **Provider prompt-cache integration** | Stack savings | Provider lock-in |
| **Formal verification for code queries** | Safe reuse for code | AST parse + language check |

### What Would Make This 10/10

Not more features — **experimental depth:**

1. Four baselines with quantitative comparison
2. Difficult benchmark with failure gallery
3. Pareto operating point with honest trade-offs
4. Storage growth measured, not assumed
5. Load test with identified bottleneck
6. Clear answer: *when should engineers **not** use semantic caching?*

---

## Core Design Principle

> **Do not add a component to look advanced. Add it when it creates a measurable engineering question that can be compared, defended, or rejected with evidence.**

**Central thesis:**

> Safe semantic reuse of previously generated LLM responses under accuracy, cost, latency, freshness, and storage constraints.
