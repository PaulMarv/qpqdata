# Phase 2B — Collection creation and criteria

## Scope and existing foundation

Phase 2A authentication, exact organisation-domain eligibility, Mailpit delivery, the development-only `university.test` organisation, sessions and the one-time welcome grant are retained. FastAPI owns collection validation, ownership, lifecycle and credits. No capture, uploads, submission creation, payouts, moderation, dataset publication/downloads or credit transfers are enabled.

Before implementation, the ORM, migrations 0001–0003, auth/session/CSRF dependencies, wallet calculation, PostgreSQL tests, frontend API transport and documentation were inspected. The Phase 1 project, criterion and label tables were only structural scaffolds. The wallet summed an immutable signed ledger; it had no reservation mechanism. No dependencies or credentials were added.

## UI reference

The [QPQData Figma file](https://www.figma.com/design/7M3EU9aXLzyJnpGjxtPdfI) supplied high-fidelity collection creation (`5:58`), search/pagination (`8:58`), detail (`8:97`), owner criteria (`12:2`), field configuration (`12:44`) and mobile criteria (`12:122`) frames. Collection surfaces use their pale blue background, white rounded cards, blue controls, inset requirement rows and mobile stacking. Existing authentication navigation is preserved. The initial implementation used Arial/system fallback. Following UI review, typography now uses locally hosted Manrope for body text and Space Grotesk for headings/logo, with SIL Open Font Licence notices retained in `frontend/src/app/fonts/`. The shared blue/ink theme also covers home and account screens; inputs, focus rings and inset select chevrons use the same palette. No external font requests occur at runtime. No static image assets were supplied for these frames. Out-of-scope camera/submission controls and illustrative fake metrics are omitted.

## Definition and validation

Each collection has an automatic UUID independent of its name. Similar and identical names are allowed. `ProjectDefinition` schema version 1 includes name, description, research purpose, category, target image count, integer QC reward (default 1), instructions, accepted/prohibited content, dimensions, JPEG/PNG/WEBP formats, optional closing date, dataset licence, reuse terms, keywords, label definitions and per-image questions.

The five question types are single choice, multiple choice, short text, number and yes/no. Each has a stable key, title, description and required flag. Choice options must be distinct (case-insensitive), with at least two and at most 30 options. Short text supports minimum/maximum length; number supports minimum/maximum and whole-number-only; multiple choice supports selection bounds. Inapplicable rules, inverted bounds, duplicate keys/options/labels, excessive lengths/counts, non-finite numbers and unknown fields are rejected by Pydantic on every create/edit. Up to 30 labels/questions and 20 keywords are supported. The editor clears incompatible rules when field type changes. The API validates definitions; answer validation belongs to the future, separately reviewed submission phase.

Draft saving requires a nonblank name and structurally valid fields/questions. Publication additionally requires description, purpose, instructions, accepted/prohibited content rules, at least one label, licence and reuse terms. The closing date cannot be in the past. Dates use UTC calendar days, inclusive through the selected day. There is no automatic close job; a passed closing date is displayed and the owner must close to release credits. No rewarded contributions can start in this phase.

Category choices: science, education, environment, health, technology, society, other. Licence choices: CC0-1.0, CC-BY-4.0, CC-BY-SA-4.0 or custom terms. These are explicit initial product assumptions; there is no legal eligibility certification implied by selecting one.

## Versioning and lifecycle

- Creation appends definition v1. Each successful draft edit appends a complete immutable snapshot and increments `current_version`.
- Edit/status requests include `expected_version`; a stale draft returns 409. Owners should reload after conflicts. Draft preview shows unsaved data and never saves answers.
- Draft → Published or Closed; Published → Paused or Closed; Paused → Published or Closed. Closed is terminal. Repeating the current status is idempotent when the expected version matches.
- First publication sets `published_version` and freezes the **entire definition**, including criteria, labels and reward. Pausing does not permit editing. Changed requirements require a new project with a new UUID. There is no silent criteria replacement or existing-submission migration.
- Backend ownership checks hide other owners' private drafts (404). Verified, currently eligible accounts are required for mutations and private owner pages. Guest browsing is public.
- Never-published drafts, including drafts closed without publication, stay private. Published, paused and closed previously published projects remain browsable archives; filters can select status.

The conservative whole-definition freeze prevents later submissions from referring to ambiguous criteria. Future submission models must explicitly reference a published definition version; implementing that association and answer validation is deferred. Existing Phase 1 `project_criteria`, `label_definitions` and submission records are retained unchanged. New collection labels/questions live in immutable definition JSON, not duplicated into legacy scaffolding. Existing version-0 drafts render their original name/description and must be saved through the editor before publication. Publication/closing of projects with existing submissions is refused pending a separately reviewed workflow.

## Credit reservation and invariants

There is no balance column and no ledger UPDATE/DELETE. Available QC remains the sum of ledger entries. Publishing 20 images × 1 QC appends a −20 `collection_reservation` entry and creates a reservation tied to that exact debit, owner, project and definition budget, in the same transaction as publication. The wallet then shows 30 available + 20 reserved = 50 total. Drafts reserve nothing. Pause holds the reservation; resume reuses it. Close appends exactly +20 `collection_release`, reverses the original debit and permanently attaches that release to the reservation. No payout exists.

User-row locks serialize funding for a wallet; project locks serialize its transitions. Authentication and grant paths use the same user-before-eligibility lock order. Unique canonical idempotency keys, one reservation per project, unique debit/release links, exact-amount/owner/reversal checks and deferred PostgreSQL constraint triggers prevent partial publication, orphan project debits, mismatched release or unfunded published/paused projects. A database ledger-insert lock and deferred nonnegative-balance guard also protect concurrent direct debit inserts. Failed transactions roll back status, snapshots, reservation and ledger entries together.

The original welcome grant constraint/index and ledger UPDATE/DELETE/TRUNCATE guards remain intact. Definition history cannot be updated/deleted/truncated. Reservation identity/amount/debit cannot change or be deleted/truncated; its release link is write-once. Published identity and definition are frozen; lifecycle checks also run in PostgreSQL. As before, a database owner can disable guards: development Compose's bootstrap role is not production role provisioning. Runtime-role hardening remains a deployment requirement.

## API and routes

| Method | Backend endpoint | Access / purpose |
| --- | --- | --- |
| GET | `/api/v1/projects` | Public directory: q, category, status, sort, page, page_size |
| POST | `/api/v1/projects` | Eligible account; create draft |
| GET | `/api/v1/projects/mine` | Eligible account; own projects including drafts |
| GET | `/api/v1/projects/{uuid}` | Public published history or authenticated owner draft |
| PUT | `/api/v1/projects/{uuid}` | Owner; append draft version |
| POST | `/api/v1/projects/{uuid}/status` | Owner; transactional lifecycle transition |

Search matches lowercased name, UUID, description, research purpose, keywords and label names. Up to ten whitespace terms are ANDed. Literal `%` and `_` are escaped. Relevance ranks exact ID, exact name, name prefix, then other matches; ties use newest creation and UUID. This deterministic initial ranking is not a full-text search engine. Queries use SQLAlchemy parameters, with server pagination (default 10, maximum 50; page 1–100000). Count is the filtered total. This simple substring approach is appropriate to the foundation and can be profiled before larger-scale indexing is needed.

Next.js `/projects` and `/projects/{uuid}` are public; `/collections`, `/collections/new` and `/collections/{uuid}/edit` require authentication. Server reads use the generated OpenAPI client. Same-origin `/api/projects/*` mutation transport checks Origin, forwards only session/CSRF cookies, supplies the CSRF header and bounds request size to 512 KiB. Business rules remain in FastAPI. Private and collection API responses are no-store. No tokens are stored in browser storage. Account navigation remains guest Log in/Sign up or authenticated avatar with the five required menu actions; Explore is a separate public navigation link.

## Schema and file map

Migration `0004` adds project version/discovery columns, nullable ledger `project_id`, `project_versions` and `project_reservations` (14 model tables total). Its companion frozen SQL installs funding/history/nonnegative guards. Migrations 0001–0003 are unchanged. No user records are seeded by this phase. No volumes are removed. Destructive downgrade remains disabled.

- `backend/app/schemas/projects.py`: versioned API/criteria validation contracts.
- `backend/app/services/projects.py`: definition, ownership, discovery, lifecycle, reservations.
- `backend/app/api/routes/projects.py`: authenticated/public HTTP boundaries.
- `backend/app/db/models.py`, `migrations/versions/0004*`: additive models/schema/integrity guards.
- `backend/app/services/auth.py`, `api/routes/auth.py`: lock-order alignment and derived reserved-wallet total.
- `frontend/src/app/components/project-*`: editor, dynamic builder, preview, cards and lifecycle actions.
- `frontend/src/app/projects/`, `(account)/collections/`, `api/projects/`: public/owner pages and typed transport.
- `frontend/src/lib/projects.ts`, `project-server.ts`, generated API contract: shared view types/client integration.
- Backend `tests/project_cases.py`, `test_project_validation.py`, schema/health integration updates; frontend `tests/projects.test.tsx`: validation, permissions, concurrency, funding, rendering, editing and transport tests.

See [verification.md](verification.md) for executed results and limits.

## Complete manual testing steps

Use only local development at http://localhost:3000. Do not reset volumes or run integration tests against this development database.

1. Keep the existing `.env` and database credentials. Check `QPQ_ENVIRONMENT=development`, `QPQ_DEV_EMAIL_ENABLED=true`, `QPQ_AUTH_ENABLED=true` and `QPQ_FRONTEND_URL=http://localhost:3000`. Run `docker compose config --quiet`, then `docker compose up --build -d --wait --wait-timeout 120`. Check `docker compose ps -a`: db/backend/frontend/Mailpit healthy, migrate/dev-seed exited 0. Readiness http://localhost:8000/api/v1/health/ready and frontend http://localhost:3000/api/health should return ok. Alembic head is 0004.
2. As a guest, visit `/projects`: search and filters are available, private drafts absent. Click **Create collection**: login is required. Account actions show only **Log in** and **Sign up**.
3. Sign up with `student@university.test` (or a fresh address such as `collections-demo@university.test`). For an existing account use **Log in**. Open http://localhost:8025, find that address's message, open its link in the same browser, then click **Verify email**. Do not copy links into logs/screenshots. Check the avatar menu and `/wallet`. A fresh verified eligible account has 50 QC exactly once; an existing account retains its actual ledger-derived balance.
4. Avatar → **My Collections** → **Create collection**. Enter **Clean & Messy Kitchens**. The ID field says it will be generated. Set description “Original photographs of household kitchens”, purpose “Study kitchen scene classification”, category Science, 20 images, reward 1 QC. Enter instructions, accepted content and prohibited content (for example no people or private documents), minimum 640×640, JPEG and PNG. Leave closing date blank or choose a future UTC date. Choose CC BY 4.0 and explain attribution/research reuse. Add keywords `kitchen,household`.
5. Add labels **Clean / organised** and **Messy / dirty**, with descriptions. Add a required **Single choice** question “How would you classify this kitchen?” with those two options. Add an optional **Single choice** question “What lighting was used?” with Daylight, Indoor lighting, Dim lighting. Add trial multiple-choice, short-text, number and yes/no questions; inspect their appropriate validation controls. Move questions up/down and remove trial questions. Duplicate options, inverted ranges and mismatched rules should fail backend validation on save; invalid HTML numeric bounds also block submission.
6. Click **Preview draft**. Inspect full requirements, labels, licence and questions. Try selecting preview answers: nothing is saved. **Back to editor** retains edits. **Save draft** navigates to its details and displays its automatic UUID and v1. The wallet remains unchanged. Note: leaving the editor without saving loses unsaved changes.
7. Open a second draft with the same name: it must have a different UUID. In an incognito guest window neither draft URL should be accessible. In another eligible user's browser, drafts cannot be read or modified. Existing users with revoked/unverified eligibility cannot create or modify projects even with an old session cookie.
8. Edit the original draft, change a question, save: version increments. Open the same draft in two tabs, save one, then save the older tab: expect a conflict asking you to reload, with no silent overwrite. Save a named but incomplete draft and try publishing: expect a completion error. A past closing date must also prevent publication.
9. On the complete draft detail click **Publish · reserve 20 QC**, confirm. For a fresh 50-QC account, wallet becomes 30 available, 20 reserved, 50 total. Reload/repeat the same publication request: no second debit. Edit is no longer offered; direct draft edit API calls fail. Inspect the public URL as a guest: labels, questions and image requirements are visible. Contributions remain unavailable.
10. Search `/projects` by full UUID, project name, keyword and label text. Try category/status filters and Newest/Relevance sorting. Create/publish enough small-budget synthetic projects to exceed ten public results if testing pagination manually; otherwise the automated PostgreSQL suite covers multiple result pages. Check Next/Previous preserve query/filter/sort and do not repeat results. Test narrow phone viewport, keyboard focus, input labels, preview controls and text wrapping.
11. Pause the published project: 20 QC stays reserved and the status filter finds it. Resume: no new debit. Close and confirm: available returns to the prior amount, reserved becomes zero. Closing is permanent. Repeating close must not add another release. It remains a public closed archive.
12. With a fresh 50-QC account create a complete draft for 51 images × 1 QC. Publishing must fail with **Insufficient QC**, remain draft and leave wallet unchanged. With two browser tabs, attempt to publish two 40-QC drafts from that wallet: only one may succeed; the other must fail. Close the successful one to release its reservation. Do not manually edit the ledger.
13. Log out. The avatar disappears; guest actions return. `/collections` redirects to login while published project browsing remains available. Mailpit development verification and Phase 2A login/replay/expiry behavior remain unchanged; see [phase-2a.md](phase-2a.md) for their acceptance steps.

Stop after Phase 2B for review. Manual scenarios above are instructions, not claims that a human has executed every scenario.
