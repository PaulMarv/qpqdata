# Phase 1 architecture and decisions

Next.js App Router, strict TypeScript and Tailwind provide the mobile-first presentation layer. FastAPI owns all domain rules. The frontend health route is process liveness only; it contains no business logic. A server-rendered landing page calls FastAPI readiness with a three-second timeout and displays failure without crashing. No accounts, project APIs, uploads, approvals, transfers, searches or downloads are enabled.

Python 3.12 and Node 22 are reproducible container baselines. PostgreSQL 17 is the database. Python dependencies use uv.lock and JavaScript dependencies use package-lock.json. Review lockfile updates. No network calls, configuration reads or database connections occur on Python module import. FastAPI lifespan creates and disposes the engine; synchronous readiness queries run in the thread pool. Future sessions must use explicit transaction ownership.

## API contract

FastAPI generates OpenAPI, committed as frontend/openapi.json. openapi-typescript generates the TypeScript contract; openapi-fetch provides path, method and response typing. Regenerate both after API changes and review the diff. Server-side QPQ_API_INTERNAL_URL is never embedded as a public browser environment variable. No browser API calls or credentialed CORS are required yet. Liveness proves the process responds; readiness checks database connectivity and the expected migration revision, not every schema invariant.

## Data model

Nine initial tables: users, organisations, organisation_domains, organisation_memberships, projects, project_criteria, label_definitions, submissions, credit_ledger_entries. UUID primary keys and timezone-aware creation timestamps are shared conventions. Users are identified by provider issuer plus opaque subject; email is not the identity key. Projects are draft-only and submissions pending-only in this phase, enforced by checks. Criteria describe typed required metadata fields; actual submission metadata validation will require a future backend service. One optional label per submission is the initial assumption; adding multi-label classification requires a reviewed migration. Composite foreign keys prevent labels from a different project. Project names are indexed but need not be unique; search is deferred.

Image storage is private object storage, provider undecided. Only opaque object keys are modelled, never signed URLs. Upload authorisation, original-photo attestations, MIME/decompression validation, malware scanning, EXIF/privacy handling, quotas and short-lived scoped signed URLs require later implementation. No storage dependency, bucket or credentials are invented here.

QC amounts are signed whole integers. There is no stored balance: balances will be derived from SUM(amount). Unique idempotency keys prevent duplicate posting. PostgreSQL triggers reject UPDATE, DELETE and TRUNCATE on the ledger; corrections must append compensating entries. Reversal relationships are modelled but not implemented as a posting workflow; validation of exact amounts, same account and nonnegative balances must be added transactionally before enabling credit operations. Phase 1 has no ledger mutation endpoints. Database owners can bypass triggers; production requires separate migration-owner and restricted backend runtime roles. Development Compose uses a local bootstrap role and is not production provisioning.

## Security and operational limits

Compose binds ports to loopback and requires an explicitly selected password. Database URLs must be URL encoded and secrets never committed. The frontend has no authentication UI or misleading active feature controls. Security response headers are supplied; deployment-specific CSP, HTTPS, rate limiting and trusted-host policy must be reviewed before public hosting. Backend access logging is disabled by default. Never log tokens, signed URLs or submitted image metadata. Production exception logging requires redaction review.

Compose runs migrations once through a separate service before backend startup. Never create tables from ORM metadata at startup. Initial migration is frozen and independent of application models; subsequent changes require new revisions. Downgrade refuses destructive rollback. A named volume persists database state; never use `docker compose down -v` unless explicitly choosing to destroy local data. Local DB port conflicts may be resolved by changing the host-side port and host URL.

Authentication and deployment remain review gates. No real user data is seeded, no external service credentials are needed, and no production readiness is claimed.

## Development email follow-up

The explicitly authorised Mailpit harness adds one challenge table through revision `0002`, with no changes to frozen revision `0001` or ledger guards. The schema now has ten model tables. Production authentication remains disabled. See [development email testing](development-email.md) for exact environment gates, transport and token handling, fixture scope, manual steps and limits. Its activation message records development mailbox verification only; no membership or session is created.

## Phase 2A authentication

The approved passwordless decision and complete requirements are in [phase-2a.md](phase-2a.md). Revision 0003 preserves earlier schema/data while adding session/throttle storage, profile fields, explicit token purposes and welcome-grant uniqueness/checks. There are now 12 model tables. The original append-only ledger triggers remain unchanged. Sessions and backend eligibility, rather than navigation visibility, enforce access. Production deployment remains gated by real transport and membership-review configuration.
