# Phase 1 verification — 30 October 2026

## Passed locally

- Backend, Python 3.12.13, locked uv environment: 10 tests passed; 1 PostgreSQL integration test intentionally skipped without TEST_DATABASE_URL.
- Ruff lint and formatting checks passed.
- Alembic initial upgrade rendered PostgreSQL SQL offline successfully; schema comparison against ORM metadata passed using SQLite for portable DDL. This does not establish PostgreSQL trigger execution.
- Committed OpenAPI contract matches FastAPI output.
- Frontend, isolated Node 22: ESLint, strict TypeScript, Prettier and production Next.js webpack build passed.
- Vitest 5.0.5: 4 tests passed across typed API success/failure handling and accessible foundation-page content.
- npm installation audit after upgrading Vitest and compatible Vite: zero reported vulnerabilities. This is a point-in-time registry check, not a security certification.
- Docker Compose configuration validated with synthetic placeholder values using config --quiet; no credentials were printed.

## Not verified

Docker is installed but its daemon was not running. No Docker images were built, no Compose services were started, and no database was migrated locally. PostgreSQL-only trigger behaviour and end-to-end container startup remain unverified. The opt-in PostgreSQL test applies the migration to an explicitly selected empty disposable database and checks ledger UPDATE, DELETE and TRUNCATE rejection. It must pass before accepting database integrity as verified.

The backend test client emits an upstream Starlette/httpx deprecation warning; tests pass. Real browser/device accessibility, deployment security, identity-provider integration and object storage remain outside this phase's verification. No real data or external credentials were used.

## Review boundary

Phase 1 implementation only. Authentication is architecture and schema preparation, not an active login system. No uploads, credit transfers, approval workflows or dataset APIs were implemented. See architecture.md and authentication.md for assumptions and unresolved production decisions.
