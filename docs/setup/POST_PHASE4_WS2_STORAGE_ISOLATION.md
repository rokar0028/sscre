# Workstream 2 — storage isolation (Step 2.4)

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Boundary:** [`POST_PHASE4_WS2_API_AUTH_BOUNDARY.md`](./POST_PHASE4_WS2_API_AUTH_BOUNDARY.md)  
**Evidence:** [`POST_PHASE4_WS2_EVIDENCE.md`](./POST_PHASE4_WS2_EVIDENCE.md)  
**Machine-readable:** [`../../artifacts/stabilization/ws2-storage-isolation.json`](../../artifacts/stabilization/ws2-storage-isolation.json)

## Scope part representation

| Field | Storage type | Rules |
| --- | --- | --- |
| `tenant_id` | `TEXT NOT NULL` | 1–128 chars; trimmed in app via `normalize_scope_part`; no `\\n` or `\\r`; case-sensitive |
| `namespace_id` | `TEXT NOT NULL` | Same rules as `tenant_id` |
| `content_query_hash` | `CHAR(64) NOT NULL` | Lowercase SHA-256 hex of normalized query text (v1 fingerprint) |
| `query_hash` | `VARCHAR(64) UNIQUE` | Versioned scoped storage key (`CACHE_KEY_VERSION=v2`) |

Trusted-local development uses `tenant_id=trusted-local` and `namespace_id=default`
(from authenticated context). Legacy rows backfilled in migration 012 use
`legacy-unscoped` / `legacy-unscoped` and must not be treated as an external
tenant without operator reassignment.

## Migrations

| File | Purpose |
| --- | --- |
| [`migrations/012_cache_tenant_namespace.sql`](../../migrations/012_cache_tenant_namespace.sql) | Add columns; backfill legacy scope; tenant/namespace index |
| [`migrations/013_cache_scoped_identity.sql`](../../migrations/013_cache_scoped_identity.sql) | Length checks; unique `(tenant_id, namespace_id, content_query_hash)`; semantic scope index |

**Backfill policy:** Existing rows receive `legacy-unscoped` tenant and namespace
and `content_query_hash = query_hash` (historical v1 content key). No row is
mapped to a live external tenant automatically.

**Rollback:** Restore a pre-012 snapshot or reverse migrations in a maintenance
window; dropping scoped columns loses tenant metadata. Do not downgrade
production without an explicit data migration plan.

**Least privilege:** Application role needs `SELECT/INSERT/UPDATE/DELETE` on
`cache_entries` and `canonical_answers`, not `CREATE` on public schema after
migrations. Migration role remains separate (see WS1 PostgreSQL setup).

**Row-level security:** Not enabled. Connection pooling uses a single application
role; RLS is deferred until role-per-tenant boundaries are measured.

## Canonical answers

Canonical answers remain **content-addressed** (`answer_hash`) and may be
referenced by multiple cache rows. Reads always join through `cache_entries`
filtered by authenticated `tenant_id` / `namespace_id`. Unreferenced canonical
rows are deleted only when **no** cache row references the hash (any tenant).

## Caps, eviction, and statistics

| Operation | Default external contract |
| --- | --- |
| Eviction on insert | **Per tenant + namespace** (in-memory and PostgreSQL) |
| `storage_stats()` | Platform-wide (admin) |
| `storage_stats(tenant_id=..., namespace_id=...)` | Scoped entry/byte counts (PostgreSQL and in-memory) |
| Hit counters | Per `query_hash` row (already scoped via storage key) |

Global lifecycle counters (`cache_lifecycle_counters`) remain process-wide
observability; they are not tenant quotas.

## Verification

- Unit: [`tests/test_cache_scope.py`](../../tests/test_cache_scope.py)
- Step 2.5 enforcement: [`tests/test_cache_scope_enforcement.py`](../../tests/test_cache_scope_enforcement.py)
- PostgreSQL (Gate B, opt-in): [`tests/test_postgres_cache_scope.py`](../../tests/test_postgres_cache_scope.py)

Run Step 2.8 verification (migrations + Gate B when `SSCRE_DATABASE_URL` is set):

```powershell
$env:PYTHONPATH = "src"
python scripts/ws2_step28_verify.py
```
