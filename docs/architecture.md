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

## Phase 2B collections (current behavior)

The historical Phase 1 limitations above are superseded for authentication and collections only. [Phase 2B](phase-2b.md) documents versioned immutable definition snapshots, lifecycle permissions, public discovery and transactional ledger reservations. Revision 0004 adds two tables (14 total), project discovery/version columns and exact reservation/release guards; it preserves the original ledger immutability and prior data. Available QC is SUM(ledger.amount), reserved QC is the sum of unreleased reservations, and total QC is their sum. No separate mutable balance is stored. Published definitions are frozen permanently; changes require a new project. No submission/upload/payout workflow is enabled.

## Phase 2C private images (current behavior)

[Phase 2C](phase-2c.md) supersedes the earlier deferred-submission limitations for local development only. Migration 0005 binds new image submissions to immutable project definition versions, preserves consent and labels, and adds capacity/lifecycle/history guards and a removal queue. Original Phase 1 submission records retain their old values and are not reinterpreted. There are 15 model tables. Binaries are stored outside PostgreSQL in a backend-only private volume via an object-store port; only decoded/re-encoded pixel content is persisted. No owner moderation access, decisions, credit payout or dataset export is enabled. Pending work blocks collection funding release. The local adapter is forbidden in staging/production; production storage/moderation operations remain review gates.

## Backend package structure

The backend now separates concerns under `backend/app/`:

```text
app/
├── main.py                 # Application composition and lifespan
├── api/
│   ├── dependencies.py     # Shared HTTP authentication and transaction boundaries
│   └── routes/             # Auth, development email, projects, submissions, health
├── schemas/                # Pydantic request/response and criteria contracts
├── services/               # Authentication, eligibility, collections, image processing, submissions
├── db/
│   ├── models/             # Domain mappings, shared base and public exports
│   └── session.py          # Engine/session construction
├── core/                   # Environment configuration
├── integrations/           # SMTP delivery and private object-store adapter
├── cli/                    # Explicit development fixture command
└── jobs/                   # Abandoned-upload cleanup worker
```

Routes translate HTTP requests into service calls and own explicit transaction boundaries. Services enforce domain rules; schemas validate contracts; integrations handle external I/O. SQLAlchemy models remain together in `db/models.py` to preserve their existing relationship/metadata registration without introducing unnecessary repository abstractions. The fixture service remains development-gated; its CLI is `python -m app.cli.dev_seed`. The cleanup worker is `python -m app.jobs.upload_cleanup`. Neither runs on import.

This is a package reorganisation only: public API paths, operation IDs, generated frontend contracts, ledger rules and frozen migration revisions are unchanged. Alembic's environment imports models from their new package; it does not create tables at application startup. The Uvicorn entrypoint remains `app.main:app`.

## Phase 2D moderation and payouts (current behavior)

[Phase 2D](phase-2d.md) supersedes earlier moderation/payout deferrals. Revisions 0006–0007 add immutable moderation decisions, explicit moderator assignments and a durable notification outbox (18 model tables total). Rewards move QC from held collection escrow to contributor ledger balances atomically; remaining reserved QC is derived from original reservations minus rewards. Closing refunds only unspent escrow after pending work resolves. Removal revokes access and retains earned credits; no automatic clawback or public export exists. Revision 0007 adds foreign-key-compatible User locks for concurrent authentication/payouts without rewriting 0006. Existing images and earlier removal requests are grandfathered; see the retention policy and manual two-account checks in the Phase 2D document.

## Phase 2E datasets (current behavior)

[Phase 2E](phase-2e.md) supersedes the previous dataset-export deferral. Six new tables (24 total) separate owner policy, contributor consent, owner distribution review, immutable version/member snapshots, disposable private ZIP caches and public reporting. New revocation triggers stop stale distribution on removal/withdrawal. Private disk generation and chunk-authorised streaming are bounded, deterministic and rate limited. No dataset service posts to the ledger; all downloads are free. No existing image or collection is automatically made public.

### Frontend container packaging

Phase 2E uses Next.js `output: "standalone"`; the final Docker image copies only the traced runtime and `.next/static`, and starts `node server.js` as the existing non-root node user. It does not duplicate the full development dependency/build tree into the runtime layer. This follows [Next.js standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output). The project currently has no `public/` directory; if one is introduced, its assets must also be copied into the runtime.


## Final MVP functional enhancement (1 November 2026)

Collection mode and dataset visibility are independent. Revision 0009 defaults existing projects to Crowdsourced and adds an owner-inferred zero-reward submission workflow plus append-only annotation revisions. Personal projects retain private owner-only project access regardless of a separate public dataset permission. Crowdsourced escrow remains fully reserved until ordinary closure; owner images reduce target capacity without displacing community commitments or generating payouts. Public exports reuse the worker; bounded private snapshots reuse canonical image/ZIP processing with authenticated revocable streaming. See [the complete policies and file inventory](final-mvp-enhancement.md). No Phase 3 infrastructure or features are enabled.

## Model package organisation

SQLAlchemy mappings live in `backend/app/db/models/`: `accounts.py`, `organisations.py`, `projects.py`, `submissions.py`, `credits.py`, `moderation.py` and `datasets.py`. `base.py` owns the single declarative Base and common Record mixin. Package exports preserve existing `from app.db.models import ...` imports and register every table for Alembic. Domain modules use table-name foreign keys without circular imports or database connections at import time. This is a structural refactor only: class definitions, constraints, table/index DDL and migration history are unchanged.
