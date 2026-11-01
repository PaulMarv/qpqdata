# QPQData — Final MVP functional enhancement

Separate Next.js/TypeScript/Tailwind frontend and FastAPI/SQLAlchemy/Alembic backend, with PostgreSQL. The foundation includes an explicitly enabled local Mailpit verification harness. Phase 2A adds passwordless login, server-side sessions, profiles and one-time welcome credits. Phase 2B adds collection drafts, versioned criteria, public discovery and transactional QC reservations. Phase 2C adds development-only private image submissions and per-image labelling. Phase 2D adds owner/designated review, atomic reservation-funded rewards, rejection reasons, private removal and wallet history. Phase 2E adds explicitly authorised, versioned public datasets and free ZIP downloads.

The final MVP increment adds private Personal collections, zero-QC owner images in Crowdsourced collections and shared rapid capture/one-tap labelling. See [implementation and manual tests](docs/final-mvp-enhancement.md) and [actual verification results](docs/verification.md). Stop for review before Phase 3.

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
- `backend/app/`: separate API routes/dependencies, schemas, services, database, configuration, integrations and job packages; see [the package structure](docs/architecture.md#backend-package-structure).
- `backend/migrations/`: frozen initial schema, including append-only ledger triggers.
- `backend/tests/` and `frontend/tests/`: synthetic health, contract, UI, schema and opt-in PostgreSQL checks.
- `infra/`: infrastructure notes; root Compose orchestrates services.
- `docs/architecture.md`: decisions, model assumptions and deployment limits.
- `docs/authentication.md`: verified-email and organisation eligibility design.
- `docs/verification.md`: actual check results and outstanding verification.

Stop after Phase 2E for review. Payments, credit purchases, general transfers and additional marketplace features remain outside scope.

## Local email verification

Open http://localhost:3000/dev-email and register `student@university.test`; inspect the message at http://localhost:8025, open its link, then click **Verify email**. Other exact `university.test` addresses are supported. This development-only harness grants no session or production eligibility.

See [complete setup and manual testing steps](docs/development-email.md) for required flags, reuse, expiry, rejection tests, safety boundaries and database confirmation. Migration `0002` adds the challenge table; the existing volume and ledger guards are preserved.

## Phase 2A accounts

Set `QPQ_AUTH_ENABLED=true` in the local development `.env`, then run `docker compose up --build -d --wait --wait-timeout 120`. Open http://localhost:3000/signup or /login. Magic links are captured by the existing Mailpit inbox; open them in the browser that requested them and explicitly confirm. Login links expire after 10 minutes. Eligible verified users receive exactly 50 QC once; real institution accounts without current approved membership evidence remain pending.

[Phase 2A specification and manual acceptance](docs/phase-2a.md) · [Authentication decision](docs/authentication.md) · [Executed verification](docs/verification.md)

## Phase 2B collections

Browse http://localhost:3000/projects. Eligible signed-in users can create drafts at `/collections/new` and manage them through My Collections. First publication freezes the definition and reserves its image-count × QC-reward budget from available credits. Pause holds the reservation; close releases it exactly once. Migration `0004` is additive and retains existing accounts, ledger records and Mailpit configuration.

[Phase 2B design, file map and complete manual testing steps](docs/phase-2b.md) · [Actual verification results](docs/verification.md)

## Phase 2C image contributions

Enable `QPQ_UPLOADS_ENABLED=true` alongside the existing local development auth/email flags, then rebuild Compose. New migration `0005` preserves earlier records. A separate private `image_data` volume and `upload-cleaner` worker store sanitized JPEG/PNG/WebP objects and reclaim abandoned upload artifacts. Do not delete either named volume. Uploads fail closed in staging/production; no cloud credentials are required or invented.

Use a different eligible account from the collection owner: published collection → Contribute images → requirements → camera/gallery → per-image labels → review/consent → upload → My Submissions. Maximum 5 per batch, 10 MiB/24 MP per image, 20 images per contributor per collection. Pending submissions retain collection funding and earn no QC until approved. Phase 2D approval pays the configured reward from escrow. Own-image removal requests suppress access immediately; the documented retention policy governs byte deletion.

[Phase 2C architecture, file map, limits and complete manual testing instructions](docs/phase-2c.md) · [Actual verification](docs/verification.md)

### Phase 2D moderation

Collection owners can use **My Collections → Review submissions** (`/reviews`) to review private images. Approved rewards consume reserved QC atomically; contributors see outcomes in My Submissions and reward history in QPQ Wallet. See [the Phase 2D specification and complete two-account testing steps](docs/phase-2d.md). Compose now includes an outcome-notification worker; keep Mailpit available at http://localhost:8025. No dataset exports or public downloads are enabled.

### Phase 2E datasets

Enable `QPQ_DATASETS_ENABLED=true` locally and rebuild Compose. Existing approvals remain private: owner publication, contributor per-image export opt-in and owner per-image export authorisation are required. Use **My Collections → Dataset publication**, then browse `/datasets`. Downloads are always **0 QC**. A separate private `export_data` volume/worker holds expiring ZIPs; never delete existing database/image volumes. See [the complete architecture, limits and manual test steps](docs/phase-2e.md).
