# Local PostgreSQL and pgvector setup

Milestones 5 and 7 use Docker Compose to run a development-only PostgreSQL
instance with the pgvector extension. The database is not started
automatically by the API.

## First-time setup

Copy the example environment file and replace the placeholder password:

```powershell
Copy-Item .env.example .env
```

Keep `.env` local. It is ignored by Git and must not contain production
credentials.

## Start PostgreSQL

```powershell
docker compose up -d postgres
docker compose ps
```

The service is ready when its health status is `healthy`.

On a fresh named volume, Docker creates the base tables through the mounted
files in `docker-compose.yml`. Apply and validate the complete versioned
migration set before starting the API:

```powershell
$env:SSCRE_DATABASE_URL = (Get-Content .env |
  Where-Object { $_ -like 'SSCRE_DATABASE_URL=*' } |
  ForEach-Object { $_ -replace '^SSCRE_DATABASE_URL=', '' })
.\.venv\Scripts\sscre-migrate.exe `
  --database-url $env:SSCRE_DATABASE_URL
```

The command records a SHA-256 checksum for every migration. PostgreSQL-backed
application startup fails closed if a migration is missing, unknown, or has
changed since it was applied. Do not start the API before this command
succeeds.

Verify that pgvector is available:

```powershell
docker compose exec -T postgres psql -U sscre -d sscre -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

The verification must return `vector` before a migration creates vector
columns. If it does not, use the pgvector image above and apply migration 002.

Connection settings:

```text
host: localhost
port: 5432
database: sscre
user: sscre
```

The `SSCRE_DATABASE_URL` value in `.env` is the connection string used by the
application configuration. Code that creates vector columns should call
`ensure_pgvector_available` first; it raises a controlled
`CacheRepositoryError` when the extension is missing.

Semantic retrieval and Strategy C can be configured through `.env`:

```text
SSCRE_SEMANTIC_ENABLED=true
SSCRE_SEMANTIC_STRATEGY=C
SSCRE_SEMANTIC_TOP_K=5
SSCRE_SEMANTIC_SIMILARITY_THRESHOLD=0.95
```

These settings control retrieval only. They do not establish that a cached
answer is compatible or safe for a new query.

To run the API with PostgreSQL-backed caching, load `.env` through Uvicorn:

```powershell
.\.venv\Scripts\python.exe -m uvicorn sscre.app:app --env-file .env --reload
```

Without `SSCRE_DATABASE_URL`, the application uses the in-memory repository,
which is the default used by unit tests.

Run the PostgreSQL integration tests with the connection string loaded:

```powershell
$env:SSCRE_DATABASE_URL = (Get-Content .env |
  Where-Object { $_ -like 'SSCRE_DATABASE_URL=*' } |
  ForEach-Object { $_ -replace '^SSCRE_DATABASE_URL=', '' })
.\.venv\Scripts\python.exe -m pytest -q tests/test_postgres_integration.py
```

Database connection or cache-write failures return HTTP 503 with an
`X-Request-ID` response header. Failed model generations still return HTTP 502
and are never persisted.

## Stop PostgreSQL

Stop the container while preserving its named volume:

```powershell
docker compose stop postgres
```

Remove the container but preserve database data:

```powershell
docker compose down
```

To delete the database volume as well, use `docker compose down -v`. This is
destructive and should only be used when the local database can be recreated.
