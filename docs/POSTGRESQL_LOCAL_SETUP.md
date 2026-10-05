# Local PostgreSQL setup

Milestone 5 uses Docker Compose to run a development-only PostgreSQL instance.
The database is not started automatically by the API.

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

Connection settings:

```text
host: localhost
port: 5432
database: sscre
user: sscre
```

The `SSCRE_DATABASE_URL` value in `.env` is the connection string used by the
application configuration.

To run the API with PostgreSQL-backed caching, load `.env` through Uvicorn:

```powershell
.\.venv\Scripts\python.exe -m uvicorn sscre.app:app --env-file .env --reload
```

Without `SSCRE_DATABASE_URL`, the application uses the in-memory repository,
which is the default used by unit tests.

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
