# QPQData — Phase 2A

Separate Next.js/TypeScript/Tailwind frontend and FastAPI/SQLAlchemy/Alembic backend, with PostgreSQL. The foundation includes an explicitly enabled local Mailpit verification harness. Phase 2A adds passwordless login, server-side sessions, profiles and one-time welcome credits. Image uploads, credit transfers and project approval workflows remain unimplemented.

## Start with Docker

Requirements: Docker Engine/Desktop with Compose v2. Start Docker Desktop first.

1. Copy `.env.example` to `.env`.
2. Choose a unique local `POSTGRES_PASSWORD` and replace the password in `QPQ_DATABASE_URL` with its URL-encoded equivalent. Keep the Compose URL hostname `db`. Do not commit `.env`.
3. Run `docker compose config --quiet` to validate without printing secrets.
4. Run `docker compose up --build`.
5. Open http://localhost:3000, API docs http://localhost:8000/docs, liveness http://localhost:8000/api/v1/health/live and readiness http://localhost:8000/api/v1/health/ready.

The migration service must finish before the backend starts. PostgreSQL and API ports bind to loopback. If port 5432 is occupied, set `POSTGRES_HOST_PORT` in `.env` (for example `55432`); the internal Compose URL remains `db:5432`. Stop with `docker compose down`; it preserves the named database volume. No real data is seeded. This is local development configuration, not a production deployment.

## Run applications on the host

Requirements: Python 3.12+, uv 0.13.1, Node.js 22 LTS and npm. Use Node 22 rather than Node 21. Start PostgreSQL with `docker compose up -d db` after configuring root `.env`. If `POSTGRES_HOST_PORT` differs from 5432, use that port in host-side database URLs.

Backend (from `backend/`):

```sh
uv sync --frozen
# Set QPQ_DATABASE_URL in the shell using the host DB port and localhost hostname.
# backend/.env.example shows the shape; .env files are NOT loaded automatically.
export QPQ_DATABASE_URL='postgresql+psycopg://qpqdata:YOUR_URL_ENCODED_PASSWORD@localhost:5432/qpqdata'
uv run --frozen alembic upgrade head
uv run --frozen uvicorn app.main:app --reload --no-access-log
```

Frontend (from `frontend/`, another terminal):

```sh
npm ci
cp .env.local.example .env.local
npm run dev
```

`QPQ_API_INTERNAL_URL` is a server-only setting (default http://localhost:8000). Backend settings require `QPQ_DATABASE_URL`. Browser CORS is restricted to the local frontend origin; server-side communication is used. Never put secrets in NEXT_PUBLIC variables. Changing PostgreSQL initial credentials does not change passwords in an existing volume.

## Checks

Backend, from `backend/`:

```sh
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen alembic upgrade head --sql > /tmp/qpqdata-schema.sql
```

PostgreSQL integration is opt-in: create a **new disposable empty** database, set `TEST_DATABASE_URL` to its URL, then run `uv run --frozen pytest -m postgres`. The test refuses a database containing tables, applies migrations and inserts synthetic records. It leaves the database for inspection; run against a fresh database each time. An explicitly configured connection failure fails the test. Never use a shared, development-with-data or production database. Drop only the disposable database after inspection.

Frontend, from `frontend/`:

```sh
npm run lint
npm run typecheck
npm test
npm run format:check
npm run build
```

Regenerate the API contract after backend changes:

```sh
cd backend
uv run --frozen python -m scripts.export_openapi
cd ../frontend
npm run api:generate
```

Commit both generated files and review changes. Python formatting: `uv run --frozen ruff format .`; frontend formatting: `npm run format`.

## Structure and architecture

- `frontend/src/app/`: mobile-first accessible foundation page, layout, CSS and frontend liveness route.
- `frontend/src/lib/`: generated OpenAPI types and typed FastAPI client.
- `backend/app/`: configuration, engine lifecycle, health API and initial ORM models.
- `backend/migrations/`: frozen initial schema, including append-only ledger triggers.
- `backend/tests/` and `frontend/tests/`: synthetic health, contract, UI, schema and opt-in PostgreSQL checks.
- `infra/`: infrastructure notes; root Compose orchestrates services.
- `docs/architecture.md`: decisions, model assumptions and deployment limits.
- `docs/authentication.md`: verified-email and organisation eligibility design.
- `docs/verification.md`: actual check results and outstanding verification.

Stop after Phase 2A for review. Collection, contribution, upload and transfer features remain outside the implemented scope.

## Local email verification

Open http://localhost:3000/dev-email and register `student@university.test`; inspect the message at http://localhost:8025, open its link, then click **Verify email**. Other exact `university.test` addresses are supported. This development-only harness grants no session or production eligibility.

See [complete setup and manual testing steps](docs/development-email.md) for required flags, reuse, expiry, rejection tests, safety boundaries and database confirmation. Migration `0002` adds the challenge table; the existing volume and ledger guards are preserved.

## Phase 2A accounts

Set `QPQ_AUTH_ENABLED=true` in the local development `.env`, then run `docker compose up --build -d --wait --wait-timeout 120`. Open http://localhost:3000/signup or /login. Magic links are captured by the existing Mailpit inbox; open them in the browser that requested them and explicitly confirm. Login links expire after 10 minutes. Eligible verified users receive exactly 50 QC once; real institution accounts without current approved membership evidence remain pending.

[Phase 2A specification and manual acceptance](docs/phase-2a.md) · [Authentication decision](docs/authentication.md) · [Executed verification](docs/verification.md)
