# Phase 2C verification — 31 October 2026

## Implemented boundary

Development-only contributor capture/gallery selection, independent per-image labels, consent/review/progress, idempotent private upload, My Submissions/recovery, removal-request suppression and abandoned-upload cleanup are implemented. Phase 2A/B authentication, published definition history, reservations and append-only ledger safeguards remain. **No moderation decisions, contributor payouts or dataset ZIP downloads are implemented.** Complete architecture, assumptions, file map and manual acceptance are in [phase-2c.md](phase-2c.md).

## Executed checks

| Check | Actual result |
| --- | --- |
| Backend full locked suite | **96 passed, 0 skipped**, final run 4.92 seconds on host Python 3.12.13, with TEST_DATABASE_URL pointing to fresh PostgreSQL database `qpqdata_phase1_test_5d3e4acf1a`. |
| Existing regressions | Original auth/email/eligibility, profile/session/CSRF, welcome grant, ledger, collection versioning, ownership/discovery, reservation/release and concurrency scenarios remain in the full passed suite. |
| Migration and schema | Normal migration to 0004, insertion of synthetic legacy user/draft/submission rows, then normal upgrade to 0005 passed. All original legacy submission column values were preserved with null new workflow/version markers. PostgreSQL metadata comparison passed. Offline PostgreSQL migration rendering passed. |
| Local migration | Backed-up development database upgraded normally to **0005 (head)**. `alembic current` returned 0005 and `alembic check` reported **No new upgrade operations detected**. Previous migrations unchanged. |
| Backend lint/format | Ruff check passed; **39 Python files** passed formatting. |
| Frontend tests | **46 passed across 7 files**, final run 2.17 seconds. Includes 14 contributor UI cases and 3 raw-upload transport cases, plus previous regressions. |
| Frontend static checks | Strict TypeScript, ESLint and whole-frontend Prettier passed. `git diff --check` passed. |
| Production builds | Host Node 22 build passed. Final Docker production build and `compose up --build -d --wait` exited 0; db/backend/frontend/Mailpit/upload-cleaner are healthy and migrate/dev-seed exited 0. Images were built from lockfiles. Only new package is locked Pillow 12.3.0; existing locked package versions were retained. |
| Live running-stack smoke | Passed through real Next transport, FastAPI, PostgreSQL, Mailpit and private filesystem using new synthetic owner/contributor accounts and a generated image. Details below. |
| Live HTTP | Backend live/ready and frontend health returned 200/ok. Parsed homepage HTML contained the expected heading and typed API **API: ready**. All 9 referenced JavaScript/CSS resources returned 200; nosniff verified. |
| Cleanup execution | Normal `upload-cleaner --once` succeeded with **0 expired slots, 0 orphan objects** after the smoke; it preserved the referenced, suppressed synthetic image. Worker heartbeat health passed in Compose. Expiry/orphan deletion and retention of old referenced objects were additionally exercised with isolated test files/rows. The writer/cleanup lock ordering is implemented; a dedicated writer-versus-sweeper concurrency test was not executed. |
| Data preservation | All **42 original rows remain**. All 42 matched original values immediately after migration and again after the smoke. A later concurrent-use audit found **38 unchanged rows and four authentication-only changes**, detailed below. All 3 original projects, 7 ledger entries, 4 definition versions and 2 reservations remain exactly unchanged; no original row was deleted/reset. |
| Browser/device acceptance | A native Chrome attempt to open the contributor page encountered user focus changes and was stopped. **No new contributor browser screenshot, physical camera, phone-layout or full browser-console acceptance is marked passed.** Component tests, raw XHR transport tests and real HTTP smoke are separately executed evidence. |

Five non-failing warnings remain in the final backend suite: the upstream Starlette/httpx TestClient deprecation and Alembic legacy path-separator warnings from the staged migration/offline checks. No dependency update was introduced to silence them. The single PostgreSQL test item chains extensive helper scenarios; 96 is the Pytest item count, not a claim of 96 separate new submission integration cases.

## Scenarios executed

- All five question types, independent image answers, strict primitive types, required/optional fields, required false and zero, bounds, duplicate/unknown choices, unknown keys and explicit boolean consent.
- JPEG/PNG/WebP full decoding and fresh encoding; minimum dimensions, actual format allowlist, corrupt/truncated/unsupported/empty/oversized inputs, animation and pixel limits.
- Synthetic EXIF GPS/author/orientation stripping and PNG text removal. Rotated dimensions were checked after orientation. Private storage rejects traversal, absolute paths, symlinks and overwrite attempts.
- Guest/CSRF/Origin rejection, cross-user and collection-owner private access rejection, self-contribution prevention and eligibility revocation despite an existing cookie.
- Immutable published version/label/answer provenance, idempotent manifest/raw retries, conflicting retry key payloads, duplicate content, storage failure/rollback/recovery and expired uploads.
- Race for the last collection slot; five active leases per contributor/collection; 20 completed images per contributor/collection; cancellation frees capacity. Paused and closed collections reject new work.
- Pausing/resuming with pending work; both application and direct-database attempts to close/refund outstanding work fail. No contribution credit entries are posted.
- Database rejects direct Approved/Rejected transitions, changed completed metadata/hash and submission deletion. Removal requests hide images immediately and are idempotent without deciding moderation or physically erasing retained objects.
- Orphan sweep removes old unreferenced test objects and preserves live references; expired slots become abandoned with a controlled synthetic test clock, not edits to the development database.
- Frontend camera/gallery separation, multiple selection, preview removal/replacement/retake and picker cancellation; label independence, required answer failures, consent gates, review, progress/validating/confirmation, failed-image retry and personal removal/recovery states.
- Actual XHR wrapper sends raw bytes on the fixed private endpoint, reports byte progress, surfaces server/network errors and handles AbortSignal. Same-origin proxy size/Origin/cookie/no-store boundaries are tested.

## Live smoke, backups and retained state

Two new exact `university.test` accounts signed up using real Mailpit emails and browser-bound HTTP cookie jars; no token or cookie was printed. A synthetic owner published **Phase2C Synthetic Kitchen Study**, UUID `47b5d4b7-4276-4368-a173-fb80b3745e63`, requesting 3 images at 1 QC with all five field types. The contributor requirements HTML rendered, a slot was created, bad bytes rejected, a generated 640×480 PNG uploaded and decoded privately with its synthetic GPS-text metadata absent. Required false and zero values survived. Retry returned the same pending record. Guest, other-account and owner image reads failed; self-contribution failed. Pause/resume and duplicate-content rejection/cancellation passed. My Submissions rendered Pending Review. A privacy request hid the image. Closing was refused with pending work. The owner remained at **47 available + 3 reserved QC** and the contributor at **50 QC**, with no payout. Both synthetic sessions were logged out. Captured backend/frontend/Mailpit/worker logs contained no smoke token or secret-link fragment.

Retained new development state: two synthetic accounts and their normal auth/grant records, one published synthetic collection/version/reservation, one hidden pending sanitized image, one cancelled upload record and one removal request. The generated source fixture is outside Git at `/tmp/qpqdata-phase2c-fixtures/synthetic-scene.png`. It contains no real photograph or location. Disposable PostgreSQL databases and isolated temporary test artifacts are retained for inspection; none were dropped/reset by this task.

The last all-column hash audit failed its unchanged-record assertion for four existing auth records. A read-only `pg_restore --data-only --file=-` comparison against the retained archive (captured in memory, no database restore) identified only these changed columns: one User `email_verified_at`; one verification challenge `token_hash`, `requested_at`, `expires_at`, `consumed_at`, `browser_hash`; one session `revoked_at`; one throttle `window_start`. Identity, email, profile, project and ledger values remain unchanged, and every original row remains present. These are consistent with login/logout/reverification activity during concurrent application use; the actor was not inferred. No values, keys or token hashes were printed, and no changes were overwritten to force a green audit. The final result is **not** an unqualified claim that every auth value remained unchanged throughout concurrent use.

A separate custom-format pre-migration backup is at `/tmp/qpqdata-pre-phase2c.dump` and record-hash baseline at `/tmp/qpqdata-pre-phase2c-records.json`, both mode 0600 outside Git. Earlier backups and the existing PostgreSQL volume are retained. A new private `qpqdata_image_data` volume was added; neither volume was removed. Backup creation and record preservation passed; **a restore drill of this backup was not executed**.

## Failures encountered / resolutions

1. Initial contract regression checks detected stale generated OpenAPI while new routes were being added. Export and TypeScript regeneration resolved it; the final full suite verifies equality.
2. First-pass Ruff reported formatting/import/string-length issues in new scaffolding. They were corrected; all 39 files now pass. One new direct-refund test initially lacked the Project model import (NameError); after correction the full PostgreSQL suite passed, including the real database rejection.
3. TypeScript found two missing `description` fields in synthetic label fixtures; fixtures were corrected. A later test expectation accidentally included read-only display titles in an initiation payload; it was corrected to assert only client-supplied request fields. Final frontend tests/types/lint all pass.
4. Several helper commands initially used repository-prefixed paths while already inside frontend, and failed without writing the requested files. They were rerun with correct/absolute paths. No failed invocation is counted as a passed check.
5. The late all-row unchanged assertion detected the auth changes documented above. A read-only archive column comparison initially failed because pg_restore needed an explicit output target; rerunning with `--file=-` succeeded without restoring/writing a database. It exposed no row values and identified the exact auth-only columns rather than ignoring the failed assertion.
6. Native Chrome interaction reported that the user changed application focus. Further input was stopped; actual device camera/mobile visual acceptance remains pending instead of being inferred from tests.

## Remaining review

No known functional startup, migration, schema, automated-test or live HTTP pipeline blocker remains. Before acceptance, execute the phone/browser manual steps in [phase-2c.md](phase-2c.md), especially real device capture, gallery permission behaviour, accessibility and network recovery. The native file input may use a picker fallback depending on device/browser. HEIC and images above configured limits require export/resizing before submission.

Production storage remains intentionally disabled until a reviewed private object adapter and deployment controls exist. The removal queue needs an assigned operator/support contact and approved physical/backup-erasure procedure before real public use. Suppression is not a completed erasure decision. Pending images retain owner funding until a later reviewed moderation/reconciliation phase. No next-phase implementation is authorised by these results.

---

Earlier phase/UI verification follows as historical evidence; its revision, feature-boundary and counts describe those earlier executions.

# UI consistency follow-up — 31 October 2026

User-requested visual refinements: shared blue/ink palette across home, logo, accounts and collections; locally hosted Space Grotesk headings/logo and Manrope body text; softer bordered form surfaces, consistent blue focus rings, larger rounded controls and inset select chevrons. SIL Open Font Licence notices are kept beside the font files. No runtime font-CDN requests or new package dependencies were introduced.

The native profile disclosure now dismisses on outside pointer interaction, Escape (returning focus to the avatar), focus leaving the disclosure, navigation link selection and route/user changes. Existing guest/authenticated actions and authentication endpoints are preserved.

Executed: **29 frontend tests passed** across five files, including three new dropdown interaction tests; ESLint, strict TypeScript, Prettier and host production build passed. The frontend-only Docker rebuild also passed and the container is healthy. HTTP checks passed for the homepage, frontend health, stylesheets and both CSS-referenced local font files. No backend schema, ledger or authentication-service changes were made; the prior backend suite was not rerun for this frontend-only follow-up.

Chrome desktop screenshots of the refreshed homepage and collection-creation form were inspected. The actual focused input showed the matching blue ring, the category chevron had an inset from the right edge, both pages used the new typography/palette, and all five profile actions appeared. Clicking outside removed the dropdown from the accessibility tree; Escape closed it and left the avatar focused. No form was saved and no credits were posted during these UI checks. Full mobile and cross-browser visual acceptance remains pending.

Initial frontend test execution failed because the navigation mock lacked the new `usePathname` dependency; the mock was updated and all tests rerun successfully. A jsdom navigation warning from the link-selection test was removed by preventing actual navigation in that test only; the dropdown close handler remains exercised. Early helper edits used an incorrect relative working directory and made no changes before being rerun with absolute paths. Two initial font-delivery probes incorrectly expected HTML preload elements; this build declares the font resources in CSS. The corrected stylesheet/font-face resource probe passed for both locally hosted fonts.

---

# Phase 2B verification — 31 October 2026

## Result and boundary

Collection creation/editing, versioned criteria, owner lifecycle, public discovery and ledger-backed reservation/release are implemented. Phase 2A and Mailpit are retained. No image capture, uploads, submission creation, contribution payouts or moderation were implemented. Services are left running for Phase 2B review.

## Executed results

| Check | Actual result |
| --- | --- |
| Compose validation | Passed: `docker compose config --quiet`, no secrets printed. |
| Docker builds/startup | Passed: full `docker compose up --build -d --wait --wait-timeout 120`, then final backend rebuilds for response-cache headers and authentication-disabled draft privacy. Both exited 0. Locked dependency installs reused; no dependency changes. |
| Services | PostgreSQL, backend, frontend and Mailpit healthy. Migration and development seed jobs exited 0. Existing named volume retained. |
| PostgreSQL | `pg_isready` reports accepting connections; host remains loopback port 55432. Existing PostgreSQL 17.11 instance retained. |
| Migration | Passed on fresh synthetic databases and existing backed-up local database. `alembic current` in running backend reports **0004 (head)**; independent SQL revision read confirms 0004. Readiness requires 0004. Prior migrations unchanged. |
| Backend full suite | **59 passed, 0 skipped**, final run 2.52 s, locked uv/Python 3.12.13 with TEST_DATABASE_URL set to new disposable PostgreSQL database `qpqdata_phase1_test_4b6b781f70`. The historical helper prefix is unchanged; this run includes Phase 2B. |
| Backend host-only suite | **58 passed, 1 intentionally skipped** without TEST_DATABASE_URL. This does not substitute for the separately successful full PostgreSQL run. |
| Schema | PostgreSQL integration applies normal migrations, compares ORM/schema through Alembic, and exercises original ledger integrity plus new collection guards. Offline PostgreSQL migration rendering passed in the suite. SQLite migration comparison was replaced because PostgreSQL-specific funding triggers/FKs are not portable; actual PostgreSQL comparison remains mandatory in integration. |
| Backend lint/format | Ruff check passed; all 30 Python files formatted. |
| Frontend tests | **26 passed across 5 files**, including 12 new collection component/transport tests, final run 2.04 s. |
| Frontend lint/types/format | ESLint, strict `tsc --noEmit`, and whole-frontend Prettier checks passed. |
| Frontend production builds | Host Node 22 `npm run build` and Docker Node 22 production build both passed. All new public/owner/API routes compiled. |
| API contract | OpenAPI exported from FastAPI and TypeScript declarations regenerated successfully. Frontend type checks cover the resulting contract. |
| HTTP health/render/assets | Backend live/ready and frontend health returned 200/ok. Homepage parsed visible HTML contains expected heading and actual typed API `API: ready`. All 9 referenced JavaScript/CSS assets returned 200; nosniff header verified. Repeated successfully after final backend rebuild. |
| Final cache headers | Public collection endpoint returned 200 with `Cache-Control: no-store`, `Vary: Cookie, Origin`. Correct token-list assertion passed. |
| Live end-to-end collection smoke | Passed through Next.js HTTP transport, real FastAPI/PostgreSQL and Mailpit. Details below. |
| Visual inspection | Desktop Chrome screenshot/accessibility tree of `/projects` inspected: Figma-style search/filter cards, empty state, pagination, public Explore and guest account actions render. Other screen/device visual acceptance is **not marked passed**. Native Chrome focus changed during the next inspection and remaining UI interactions were stopped to avoid interfering with the user. Component tests and HTTP rendering are independent passed checks, not a substitute for full mobile visual review. |
| Git whitespace | `git diff --check` passed. |

The single PostgreSQL test item intentionally chains extensive synthetic Phase 1, email, authentication and collection scenarios through helper suites. “59 passed” is the Pytest item count, not a claim of 59 separate new collection integration cases. Upstream non-failing warnings remain: Starlette/httpx TestClient deprecation and Alembic legacy path-separator handling. No dependency upgrade was made to silence them.

## Collection and credit scenarios exercised

- Duplicate names with distinct UUIDs; private drafts and owner-only editing; optimistic draft versions and immutable snapshot history.
- Full schema bounds, five question types, options, duplicate keys/names, incompatible rules and invalid min/max combinations.
- Required publication fields, expired closing date, insufficient funds, permitted lifecycle transitions, terminal close and frozen published definitions.
- Authenticated Origin/CSRF, guest mutation rejection, hidden non-owner drafts refusal of an old session when email verification is removed, and hidden drafts while authentication is disabled.
- Search by keyword/name/UUID, literal wildcard escaping, category/status filtering, relevance, stable pagination across multiple pages and exclusion of private drafts.
- Exact reservation, repeat publication without double debit, pause/resume without extra debit, exact one-time release and repeat close without double refund.
- Concurrent competing 40-QC publications from a 50-QC wallet: one succeeds; concurrent close refunds only once.
- Direct concurrent ledger debit inserts cannot overdraw; overspend, orphan reservation debit, unfunded published state, immutable history changes, changed owner, reset release pointer, wrong-amount/wrong-owner refunds and failure-after-reserve all roll back.
- Original ledger immutability, welcome-grant idempotency, sessions, eligibility, Mailpit verification expiry/replay and all prior backend scenarios remain in the passing suite.
- Frontend tests cover editor payload/defaults, version conflict messages, labels/choices, all field types, stale-rule clearing, stable-key reorder, unsaved preview, confirmation/cancellation, funding errors, read-only requirements, cards/pagination and Origin/body-size/cookie/CSRF transport boundaries.

## Running-stack smoke and retained records

A new synthetic `university.test` account requested a signup link through the existing frontend authentication endpoint. Mailpit captured it, the same HTTP cookie jar verified it, and the account received 50 QC. No raw token, cookie or secret link was printed. The smoke rendered owner create/edit HTML, created and edited a complete Kitchen collection through the typed Next transport, published definition v2, verified 30 available/20 reserved, repeated publication, paused/resumed, read public search/details with label/question/image requirements, rejected published edits, closed twice and verified 50 available/0 reserved. A separate 51-image draft failed publication without changing its wallet. Logout and protected-route redirect passed. Captured backend/frontend/Mailpit logs contained neither the smoke token nor secret-link fragments.

Retained development smoke state: one synthetic account, one closed published collection (`dd5f964c-b3bc-444b-baf8-44531cdfa829`), one unfunded private draft and their authentic ledger/challenge/session/throttle records. No fake balance or direct ledger correction was used. Earlier disposable verification databases are retained; none were dropped/reset. No volume was removed.

Before deployment a custom-format backup was saved to `/tmp/qpqdata-pre-phase2b.dump` and a per-record hash baseline to `/tmp/qpqdata-pre-phase2b-records.json` (both mode 0600, outside Git; private values not printed). Immediately after migration **all 24 original rows** retained all original column values. After the normal signup/logout smoke, a final read-only audit confirmed all original rows still exist: **22 are byte-for-value unchanged**, including all 5 original users, 3 ledger entries, organisation/domain, 7 verification records and 3 sessions. Two original `auth_throttles` rows advanced their counters/window through normal authentication requests. This expected operational change is explicitly excluded from the claim of unchanged business/account history; no counter was reset to make the audit pass. Existing backup/recovery artifacts remain untouched. Backup creation was verified; a restore drill for this new backup was not executed.

## Failures encountered and causes

1. Initial integration helper invocation used system Python without dotenv; it failed before tests. Rerun with `backend/.venv/bin/python` successfully launched locked tests. An initial direct OpenAPI export lacked the backend module path; rerunning from backend with `PYTHONPATH=.` succeeded.
2. First frontend type check found an undefined numeric editor value and missing generated `integer_only` fields on new questions. Corrected the editor to use numeric values and explicit field defaults. All subsequent type checks/builds passed.
3. `docker compose exec migrate ...` failed because that one-shot job had already exited successfully. The revision command was rerun in the running backend and returned 0004. No migration reset/retry workaround was used.
4. The final all-row unchanged assertion failed for `auth_throttles` after normal login testing. The follow-up audit checks every original row, rejects missing rows or any business/account history changes, and separately reports expected mutable throttle counters. Original users/credits were not changed by the migration.
5. An exact `Vary == Cookie` assertion failed because CORS correctly appends `Origin`. A token-list check confirmed both the required Cookie variation and no-store header; implementation was unchanged.
6. Browser-provider Chrome automation was unavailable; native Chrome succeeded for the directory screenshot. The next native inspection encountered user focus changes. No editor/detail/mobile screenshot, full browser hydration flow, browser-console audit or human manual acceptance is claimed.

No known functional startup, database, funding-test or HTTP connectivity blocker remains. Remaining review: complete the manual phone/browser acceptance steps in [phase-2b.md](phase-2b.md), review the conservative published-definition freeze and reservation semantics, and review before further development. Existing production transport, approved institutional membership and restricted runtime-role provisioning limits remain; this local stack is not production deployment approval.

---

The following historical Phase 1 results are retained; their phase/revision and empty-database statements describe that earlier point in time, not the current Phase 2B state.

# Phase 2A verification — 30 October 2026

The passwordless decision, approved requirements, implementation inventory and manual acceptance steps are recorded in [phase-2a.md](phase-2a.md) and [authentication.md](authentication.md). This Phase 2A record supersedes older statements below that authentication is unimplemented or the current migration is 0001/0002.

## Executed results

| Check | Actual result |
| --- | --- |
| Existing implementation inspected | Mailpit, development university/domain, hashed verification store/UI and append-only ledger were present; login, sessions, profiles, account navigation and welcome credits were absent. They were extended without duplicating the token store or SMTP transport. |
| Backup and preservation | Local pre-migration custom-format pg_dump created at `/tmp/qpqdata-pre-phase2a.dump`, mode 0600. This backup was not restored as part of this task. Per-record hashes captured for all 10 existing model tables; all 10 preexisting records retained every original column value after migration and live authentication tests. |
| Migration | Additive revision **0003 (head)** applied to the existing local database. `alembic check` reported no new upgrade operations. Applied revisions 0001/0002 were not edited; original append-only triggers remain intact. |
| Locked backend tests | **39 passed, 0 skipped** in the final 3.29-second run, with PostgreSQL enabled on a new empty disposable database (`qpqdata_phase1_test_4e6e021dca`). Includes prior foundation, verification, permissions-by-eligibility and ledger checks plus Phase 2A scenarios described below. |
| Backend lint/format | Ruff checks passed after formatting/import-order corrections. |
| Frontend tests | **14 passed** across four files, covering previous UI/API tests plus guest/avatar navigation, all five profile actions, passwordless requests, separate authentication confirmation and cross-origin rejection. |
| Frontend checks | ESLint, strict TypeScript and Prettier passed. Next.js production webpack build passed in the Docker image. |
| Compose | Images built and `up --wait` completed. PostgreSQL, Mailpit, FastAPI and Next.js healthy; migration/dev-seed jobs exited 0. Existing volume retained throughout. |
| Live signup | Fresh synthetic university.test mailbox requested signup through Next.js. Actual SMTP message captured by Mailpit, containing the configured local frontend fragment URL and 600-second expiry. Confirmation set HttpOnly/SameSite cookies and returned an authenticated profile. |
| Live protected pages | All four account routes redirected guests to login. Authenticated profile and wallet rendered successfully. Authenticated page contained the avatar/menu and no Log in/Sign up actions. |
| Live profile/wallet | Display-name PATCH succeeded through the BFF. Wallet displayed 50 QC from the backend ledger. |
| Live replay/logout | Consumed link rejected; logout succeeded; authenticated `me` then returned 401. Reusing a copied pre-logout session cookie also returned 401. |
| Live repeat login | After waiting out the real one-minute resend cooldown without editing application timestamps, a new login-purpose link authenticated the same account. Balance remained 50 QC. A read-only database query confirmed exactly one 50 QC welcome entry. Final logout succeeded. |
| Legacy verification | Fresh registration, original `/dev-email/verify` Mailpit URL and original confirmation API passed after authentication was enabled. The legacy flow still creates no session; eligible verification now grants welcome QC once. |
| Health/rendering | Backend live/ready and frontend health returned HTTP 200; homepage rendered API: ready and all nine referenced JS/CSS assets returned HTTP 200. |
| Secret handling | Live smoke test checked backend/frontend/Mailpit logs for both magic links, the copied session token and secret fragment prefixes; none were found. Tokens/cookies were never printed by test commands. |

## Automated authentication and credit scenarios

The real-PostgreSQL integration test exercises signup, verified-account-only login, separate token purposes, exact 600-second lifetime, expiry, replay, browser binding, rotation/revocation, idle and absolute session expiry, disabled users, Origin/CSRF rejection, production Secure/HttpOnly/SameSite/__Host- cookie attributes, generic responses and persistent rate limits. Schema/model agreement is checked on PostgreSQL.

Eligibility cases cover exact approved development domain, unknown and personal domains, subdomain confusion, copied reserved-domain fixtures in production, a reviewed synthetic real employer domain, membership-pending state without session/credits, subsequent independently approved membership, and revocation invalidating sessions. No real institution or user data was used in fixtures.

Welcome tests cover concurrent token redemption (one winner), simultaneous repeated grant calls, database rejection of malformed/duplicate welcome entries, failure before grant, failure after ledger insertion but before session creation, rollback of user/proof/credits/session together, safe retry, and unchanged balance after subsequent login. The original ledger UPDATE/DELETE/TRUNCATE guards and source constraints were rerun successfully. The legacy activation error path is also tested for sanitisation.

## Changes and assumptions

- Backend: auth/eligibility services and HTTP routes; shared existing SMTP delivery; additive profile/challenge/session/throttle fields and tables; welcome uniqueness/check constraint; privacy headers and typed OpenAPI regeneration.
- Frontend: signup/login and confirmation pages, same-origin typed BFF with cookie propagation, server-authorised account routes, avatar menu, display-name editing and read-only wallet. Collection/submission pages are protected unavailable-feature placeholders only.
- Real email syntax/IDNA uses newly locked `email-validator` 2.3.0 and transitive `dnspython`; DNS deliverability lookup is disabled. No other package upgrades were requested. Backend auth remains disabled by default and explicitly enabled only in local `.env`.
- Real organisation-domain approval and current membership evidence are required; no automatic domain-suffix approval or production acceptance of university.test exists. Real email-only accounts remain pending without session/credit until membership approval. No reviewer workflow or production credentials were invented.

## Failures, corrections and limits

The first container build failed on a syntax error in the new navigation component (a stray semicolon before else). It was corrected; subsequent lint, type checks, tests and production builds passed. Earlier lint/import-order findings were corrected without disabling rules or weakening tests. Existing Starlette/httpx and Alembic path_separator deprecation warnings remain non-failing.

Live browser visual/hydration inspection was not executed: the earlier Computer Use permissions blocker was not reopened. Component tests and live HTTP/SMTP/cookie flows are recorded separately and do not claim a visual browser pass. Production SMTP delivery, TLS termination and a public deployment were not exercised. HTTPS/STARTTLS settings and cookie security were tested using synthetic production configuration, not invented live credentials. Review the production gates and shared backend-peer limiter capacity in phase-2a.md before deployment.

The synthetic Phase 2A smoke account, legacy smoke account, disposable test databases, database backup and existing volume are retained. Sessions created by the end-to-end signup/login smoke were explicitly signed out. No database, volume, old user, verification record or ledger history was deleted or reset. Stop at Phase 2A for review; no image-collection, upload, contribution, approval or transfer features were implemented.

---

# Earlier verification history

# Development email verification — 30 October 2026

This authorised local-email follow-up supersedes the earlier migration/table-count and authentication-scope statements in the historical Phase 1 record below. Production authentication remains disabled. See [complete manual steps](development-email.md).

## Executed verification

- Added loopback-only Mailpit UI/API on port 8025 with internal-only SMTP on 1025; final image pin is `axllent/mailpit:v1.32.0` from the official release. No relay or external email credentials are configured.
- Existing Compose images built successfully and services started healthy. Existing PostgreSQL volume was retained; no volume or database was deleted or reset.
- Additive migration `0002` creates only the challenge table. The original `0001` and ledger guards were not changed. There are now ten ORM tables.
- The explicit idempotent development seed created QPQData Test University and exact domain university.test, with its development-fixture review marker. No example account was seeded; accounts activate only after verification.
- Full locked backend suite with PostgreSQL enabled: **31 passed, 0 skipped** (final run 1.30 seconds), including the preserved ledger guard/constraint tests, schema agreement and the development-email integration scenarios.
- Email tests cover successful activation, expiry, reuse, SHA-256 token persistence, multiple fixture addresses, persistent cooldown, replacement invalidating old links, two simultaneous redeemers (only one succeeds), revoked-domain denial and SMTP-failure rollback. Unknown, personal, subdomain and suffix-confusion addresses are rejected. Settings and endpoint tests reject staging/production activation and sanitise invalid token input.
- Frontend tests: **9 passed** across three files. They cover the example registration form, explicit confirmation, token-fragment removal, missing links, production-disable and same-origin transport boundaries, alongside the original foundation checks. Lint, strict TypeScript and formatting passed.
- Live local smoke test passed through the Next.js transport, FastAPI, PostgreSQL and actual SMTP to Mailpit: registration, captured message retrieval, configured `http://localhost:3000/dev-email/verify#token=...` link, activation, reused-token rejection and no email sent for unknown/personal/subdomain addresses. Tokens and complete secret links were kept out of command output.
- Real expiry was tested using a temporary 30-second backend lifetime: after waiting 32 seconds, the captured token was rejected through the live frontend transport. This test did not alter application database timestamps.
- Captured backend, frontend and Mailpit logs were checked for both smoke-test bearer tokens and secret-link fragments; none were found.

SMTP smoke accounts used fresh synthetic aliases under university.test; the manual example student@university.test remains available. Synthetic test databases are retained separately from the application database, including qpqdata_phase1_test_0bdd385e89 for the final backend suite. The application database now intentionally contains the organisation/domain fixture and local SMTP-smoke verification state; the earlier empty-table result is historical.

## Final running state

`docker compose up --build -d --wait --wait-timeout 120` completed successfully with the final code. PostgreSQL, Mailpit v1.32.0, backend and frontend are healthy; migration and dev-seed jobs exited 0. `alembic current` reports **0002 (head)** and `alembic check` reports no new upgrade operations. A read-only settings check confirmed the normal **900-second** lifetime was restored after the expiry test.

Read-only application checks confirmed exactly one test-university/domain fixture, one activated SMTP-smoke account, no activated expired-smoke account, and no organisation memberships or credit ledger entries. These are development records only; student@university.test was not pre-created.

## Boundaries and issues encountered

The initial frontend lint run rejected setting token state synchronously in an effect. The verification component now reads the external URL fragment into a ref, clears history while preserving router state, and sends the token only after an explicit confirmation click. Subsequent frontend checks passed. No lint rule was disabled.

The first Mailpit image was selected from an older documentation example, then replaced with the current official v1.32.0 release before the live smoke verification after checking release/security information. No dependency lockfiles were changed. Existing non-failing Starlette/httpx and Alembic path_separator deprecation warnings remain.

Verification is mailbox control in the explicitly labelled development environment, not institutional affiliation or production account authentication. No login session, organisation membership, credits or reviewer access is granted. Reserved .test fixture acceptance requires both development settings and the exact fixture marker; staging/production cannot enable this feature. Future production eligibility must independently reject reserved test domains.

Browser visual inspection was not performed in this follow-up. The earlier OS permission blocker remains; HTTP/SMTP/PostgreSQL smoke tests and component tests do not imply a browser visual inspection passed.

---

# Historical Phase 1 verification record

# Phase 1 verification — 30 October 2026

## Follow-up outcome

The existing Compose stack was built and started successfully. PostgreSQL, FastAPI and Next.js are running and healthy. The migration service completed with exit code 0. Phase 1 remains the implementation boundary; no Phase 2 features were added.

## Executed checks

| Check | Actual result |
| --- | --- |
| Docker daemon | Passed: Docker Engine 29.8.2 responded to `docker info`. |
| Compose configuration | Passed: `docker compose config --quiet`, using local configuration without printing secrets. |
| Docker builds | Passed: backend, migration and frontend images built from the existing Dockerfiles and locked dependencies. Frontend production build completed inside the Node 22 image. |
| Service startup | Passed: `docker compose up -d --wait --wait-timeout 120` exited 0 after the host-port correction. Final `docker compose ps -a` shows db, backend and frontend healthy; migrate exited 0 as expected. |
| PostgreSQL readiness | Passed: `pg_isready -U qpqdata -d qpqdata` reported accepting connections. |
| PostgreSQL query | Passed: `psql` connected to database `qpqdata` as `qpqdata` and queried database identity and version. Server is PostgreSQL 17.11. |
| Application migrations | Passed: Compose ran the existing `alembic upgrade head`; `alembic current` reports `0001 (head)`. No migration files were changed. |
| Schema agreement | Passed: `alembic check` against the running application database reported “No new upgrade operations detected.” |
| Backend tests | Passed: locked Pytest suite against a newly created disposable PostgreSQL database: **11 passed, 0 skipped**, in 4.13 seconds. Includes all unit, schema, contract and PostgreSQL integration tests. |
| Backend lint/format | Passed: locked Ruff lint and formatting checks; all 11 Python files formatted. |
| Frontend checks | Passed again: ESLint, strict TypeScript, Prettier and Vitest (**4 passed** across 2 test files), using Node 22. |
| FastAPI liveness | Passed: `GET http://localhost:8000/api/v1/health/live` returned HTTP 200 with `status: ok`. |
| FastAPI readiness | Passed: `GET http://localhost:8000/api/v1/health/ready` returned HTTP 200 with `status: ok`, checking the live database and migration revision. |
| Frontend liveness | Passed: `GET http://localhost:3000/api/health` returned HTTP 200 with `status: ok`. |
| Container-to-container API | Passed: a Node fetch inside the frontend container reached `http://backend:8000/api/v1/health/ready` and received HTTP 200 with `status: ok`. |
| Next.js page rendering | Passed at HTTP/server-rendering level: `GET /` returned HTTP 200; parsed visible HTML contained the expected main heading and **API: ready**, exercising the page’s actual typed API client. |
| Frontend assets | Passed: all six JavaScript/CSS assets referenced by the rendered page returned HTTP 200. `X-Content-Type-Options: nosniff` was also verified. |
| Data isolation | Passed: a read-only count against the application database confirmed all nine domain tables remain empty. Synthetic integration data exists only in the disposable test database. |
| Dependency audit | The container’s `npm ci` completed and reported zero vulnerabilities. This is a point-in-time registry result, not a security certification. |

Runtime versions checked in the running containers: Python 3.12.16 and Node v22.23.4; Next.js startup/build logs report 16.4.3. Host backend tests used Python 3.12.13 and the existing uv.lock.

## PostgreSQL ledger verification

The integration test now checks actual PostgreSQL SQLSTATE values rather than accepting any database error as proof of a guard. Successfully exercised:

- Migration from an empty test database to `0001`, presence of all model tables, and no ORM/schema drift.
- Ledger UPDATE, DELETE and TRUNCATE rejection by the append-only trigger (`P0001`).
- Zero-value and self-referencing reversal rejection (`23514`).
- Duplicate idempotency-key and duplicate reversal-reference rejection (`23505`).
- Missing user and missing reversal-target rejection (`23503`).
- Successful append of a synthetic compensating entry, unchanged original amount, exactly two surviving entries and a derived sum of zero after rejected writes.

The test database is `qpqdata_phase1_test_9e76bc2fd4` on the same local PostgreSQL server. It is retained for inspection and contains only synthetic fixtures. The test refuses nonempty databases, so use a newly named empty disposable database for another run. No existing database or volume was deleted or reset.

## Failures encountered and resolutions

1. The initial Docker probe inside the filesystem sandbox could not access the Docker socket. The permitted elevated probe succeeded; the daemon was already running. Docker did not need to be restarted.
2. The initial Compose build succeeded, but startup failed with `bind: address already in use` for host `127.0.0.1:5432`. A separate database-start attempt failed for the same reason. The initial listener inspection had not exposed the reservation; the underlying port occupant was not conclusively identified and was left alone.
3. A connection probe and the first test-database creation attempt failed because the PostgreSQL container had not started. No integration assertions ran in that failed attempt. These checks were rerun successfully after fixing the port.
4. The host database mapping is now configurable as `POSTGRES_HOST_PORT`, defaulting to 5432. Local `.env` selects **55432**; the internal Compose URL remains `db:5432`. README and `.env.example` document the setting. This was the only tracked operational configuration change.
5. Browser visual inspection through Computer Use could not execute because macOS Accessibility/Screen Recording permissions were not granted. Two attempts were made. **No browser visual, hydration, device-layout or browser-console check is marked passed.** HTTP rendering, asset delivery and component tests passed as recorded above.

Non-failing test warnings remain: upstream Starlette/httpx test-client deprecation and Alembic’s missing explicit `path_separator` setting. They did not prevent any test or migration. No dependency or migration changes were made to suppress them.

## Current local access and retained state

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Backend liveness/readiness: http://localhost:8000/api/v1/health/live and http://localhost:8000/api/v1/health/ready
- PostgreSQL host connection: `127.0.0.1:55432`, database/user `qpqdata`.
- A new private `.env` with a generated local-only password was required because none existed. Its permissions are 0600, and `.gitignore` excludes it. No password is recorded here or printed in verification output.
- The named `qpqdata_postgres_data` volume, application database and synthetic test database are retained. Services are left running. Normal `docker compose down` preserves the volume.

No functional startup, migration, database-test or API-connectivity blocker remains. Browser visual inspection remains unverified pending OS permissions. Production security, real identity-provider integration, object storage, uploads, transfers and approval workflows remain outside Phase 1.

## Original verification history

Before this follow-up, the host-only suite passed 10 backend tests with the PostgreSQL test skipped, and four frontend tests; lint, type checks, formatting, production build and offline migration rendering passed. Docker execution and PostgreSQL triggers had not been verified then. The executed results above replace those earlier outstanding infrastructure checks without claiming any unexecuted browser checks.
