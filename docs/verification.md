# Custom linked-frame logo — 1 November 2026

Replaced the plain navbar wordmark with a reusable Brand component: original vector mark with two linked rounded Q/image frames, navy/blue fills and a small mint accent; paired with heavier QPQ and lighter Data lettering. Decorative SVG is hidden from assistive technology and the home link has an explicit accessible label. Sizes adapt for smaller screens; hover tilt is gated by hover capability and reduced-motion preference. No image service, remote asset or new dependency.

Executed **86 frontend tests**, ESLint, TypeScript, Prettier, whitespace checks and production Docker build successfully. Recreated frontend is healthy; Chrome desktop screenshot confirmed logo rendering in the existing navbar. Physical mobile and broader brand acceptance remain manual. No backend or stored-data changes.

---

# Contained navigation and drawn active accent — 1 November 2026

Kept the header background full-width while containing logo/navigation within a centred 1100px inner layout. Replaced the straight underline with an original embedded SVG double-curve accent, fixed at 30px and centred under each active label. Hover uses a smaller, softer version with restrained rotation/scale; existing reduced-motion overrides and aria-current remain. No external asset or dependency was added.

Verified: **86 frontend tests**, ESLint, TypeScript, Prettier, production Docker build and whitespace checks passed. Frontend recreated successfully and healthy. Chrome desktop screenshot confirmed the compact inner layout and short curved active mark. Physical mobile acceptance remains manual. No backend or stored-data changes.

---

# Full-width navbar and underline refinement — 1 November 2026

Removed the header max-width and centred-container constraint so the navbar spans the viewport. Replaced main-navigation pills with a short rounded blue underline; hover reveals a softer, shorter line. Removed active account-pill/outline decoration while retaining keyboard focus, aria-current, nested-route matching and reduced-motion handling.

Executed: **86 frontend tests passed**, ESLint, TypeScript, Prettier, whitespace checks and production Docker build passed. Recreated the frontend from the completed image; service healthy. Chrome desktop screenshot confirmed edge-to-edge header and underline without a pill. Physical mobile checks remain manual. No backend or data changes.

---

# Navbar interaction and active states — 1 November 2026

Added client-side SiteNav with pathname-aware Explore/Datasets selection, including nested detail/capture routes. Active links have a tinted pill, heavier text, border and blue inset underline, plus aria-current. Hover/press feedback, 44px minimum targets, existing keyboard focus outlines and reduced-motion overrides are retained. Account links and profile-menu destinations also show current-page state without changing session handling or guest/authenticated visibility.

Node 22 frontend suite: **86 passed**, including seven new navigation route cases for exact matches, nested pages, homepage, unrelated routes and prefix collisions. ESLint, TypeScript, Prettier and whitespace checks passed. Production Docker build passed; restarted frontend is healthy. Chrome desktop inspection verified the Datasets active pill and its switch to Explore after navigation. Physical mobile and authenticated profile-menu visual acceptance remain manual checks. No backend or database changes.

---

# Application hierarchy and balanced cards — 1 November 2026

Reworked collection and dataset discovery cards into a responsive content column and contrasting summary panel. Titles/descriptions/labels stay in the content column; requested/available image counts, QC rewards or licence, availability and actions occupy the summary. Full identifiers remain visible as secondary references. Below 720px the panel stacks; below 380px its metrics use one column. No information is truncated or made dependent on hover. Application headings, facts and card titles now have stronger weight and explicit size hierarchy; supporting text uses quieter, readable colours. Kept presentation rules in `styles/cards.css`.

Frontend suite: **79 passed**, plus ESLint, strict TypeScript, Prettier and whitespace checks passed. Initial suite had one failure because the ID assertion expected the old label; updated it to the clearer Project ID label and reran successfully. Production Docker build passed and the restarted frontend became healthy. Chrome desktop visual inspection confirmed the two-column collection and dataset cards and stronger hierarchy. Physical mobile layout and screen-reader acceptance remain manual checks. No API, credit, database or storage changes; backend tests were not repeated for this presentation-only work.

---

# Homepage content and typography review — 1 November 2026

Reviewed current homepage against the implemented personal collection, owner/community contribution and dataset policies. Updated the hero and three feature cards to describe private-by-default, zero-QC personal collections and private exports; approved community rewards versus zero-QC owner images; and explicitly published public datasets with free downloads subject to licence terms. Updated site description accordingly.

Space Grotesk now applies to the logo and homepage headings, with a blue, lighter-weight hero emphasis. Application headings and wallet numbers use Manrope for a quieter reading experience; existing body/form typography remains Manrope.

Executed frontend regression suite: **79 passed**. ESLint, strict TypeScript, Prettier and whitespace checks passed. The homepage regression assertion now covers the implemented private/free options. Production Docker build passed and the deployed frontend became healthy. Chrome desktop inspection confirmed the refreshed homepage copy and two-tone headline. Physical mobile and authenticated-screen typography acceptance remain manual checks. No backend, data, schema or ledger changes.

---

# Frontend visual polish — 1 November 2026

Added a dedicated `frontend/src/app/styles/surfaces.css` layer for shared panel shadows, blue gradients, mint credit pills, lavender category chips, richer inset surfaces, pagination and hover/focus feedback. Updated homepage hierarchy and feature cards, collection reward badges, dataset cards and wallet summary/transaction badges. Preserved existing typography, forms, authentication and credit rules. Motion is restrained, hover lift is restricted to hover-capable devices with no reduced-motion preference, and keyboard focus indicators remain available.

- Node 22 container: **79 frontend tests passed**, ESLint, strict TypeScript and full Prettier check passed. Production Docker build passed; deployed frontend became healthy.
- Initial test run: 78 passed, one failed because the homepage test still asserted that downloads were unavailable. Corrected the stale homepage copy and test to reflect the implemented free dataset library; final suite passed. Initial CSS append used an incorrect relative path and made no CSS change; corrected before checks/build.
- Chrome desktop visual inspection confirmed the deployed homepage, dataset library, collection cards, category chips and QC badges render successfully. Authenticated wallet appearance, physical mobile layout and screen-reader acceptance remain manual checks; no claim of those checks passing is made.
- No backend, schema, stored balance, ledger or database-volume changes were made. Backend tests were not repeated for this presentation-only change.

---

# Model organisation refactor — 1 November 2026

Split `backend/app/db/models.py` into seven domain modules plus a shared base and explicit package exports. Largest mapping module: 114 lines. Existing `app.db.models` imports remain compatible.

- Exact before/after AST comparison passed for all 27 class definitions (25 mapped classes, Base and Record). PostgreSQL table and index DDL matched exactly for all 25 tables.
- Full backend suite against fresh disposable PostgreSQL database `qpqdata_phase1_test_5aad55585d`: **124 passed**, five existing deprecation warnings, no skips (9.19 seconds). Includes migrations, ledger constraints, authentication, submissions, exports and concurrency regressions.
- Ruff lint passed; all **85 Python files** under app/tests/migrations passed formatting. Diff whitespace check passed.
- Backend and worker images rebuilt successfully with frozen dependencies; Compose start/wait passed with all seven long-running services healthy and migration/fixture services exiting 0. Running backend reports **0009 (head)** and **No new upgrade operations detected**. Backend readiness and frontend health returned HTTP 200.
- No new migration, business-rule changes or volume reset. Existing database and image volumes retained. Frontend code was unchanged by this refactor, so frontend tests and its production build were not repeated for this change.

---

# Final MVP enhancement verification — 1 November 2026

Implemented Personal collections, zero-QC owner images and shared rapid capture/one-tap labelling; stopped for review before Phase 3. See [implementation, policy choices and complete manual steps](final-mvp-enhancement.md).

| Check | Actual executed result |
| --- | --- |
| Prerequisite Phase 2E | Before application changes: **124 backend/PostgreSQL** and **67 frontend tests** passed. Completed the previously missing running-stack two-account HTTP flow through Next.js: Mailpit authentication, image uploads/approval, separate publication/consent/authorisation, real worker ZIP, guest download, ZIP/manifest/image hashes, versions 1–3, unchanged earlier version, withdrawal revocation, private source retained and wallets unchanged by downloads. |
| Final backend suite | **124 passed**, no skipped tests; final disposable PostgreSQL target `qpqdata_phase1_test_1abd1062a0`. The existing aggregate PostgreSQL test now includes the owner/personal scenarios, so the top-level test count is unchanged despite added integration coverage. Five existing Starlette/httpx and Alembic configuration deprecation warnings remain. |
| PostgreSQL owner/personal scenarios | Zero-available-QC personal creation and 21 sequential owner captures (without the community 20-image limit); private defaults and cross-user/guest denial; public personal collections still reject community capture; no personal credit entries/reservations; owner status/reward provenance; duplicate/retried images and concurrent same-key initiation; immutable label history and stale edit rejection; publicly authorised label-edit restriction; private ZIP contents/resource bounds; public owner export; forbidden owner payout; storage failure rollback/recovery; owner/community final-slot race; concurrent paused owner completion/community approval; removed-owner slot reuse while protecting community commitments; closure versus completion; exact refund/reward accounting; raw removal restriction interrupts private streaming and subsequent access. |
| Existing regressions | Authentication/eligibility/welcome grant, append-only ledger, community reservations/approval concurrency, original image validation/metadata stripping, secure object access, publication consent, free download/immutable versions and removal cases remain passing. |
| Frontend | **79 passed across 10 files** (12 new rapid-capture/personal UI tests). ESLint, strict TypeScript and Prettier passed. Tests cover mode selection, private setup, independent one-tap values, collapsed optional fields, required labels/attestation, same-slot retry, community pending outcome, denied camera, camera cleanup, Save & Capture Next retaining the live stream without a second permission request, unsupported file rejection and optimistic personal label edits. |
| Lint/build | Ruff lint passed; **78 Python files** passed formatting; `git diff --check` passed. Frozen-dependency production images built successfully. Final Compose build/start/wait passed after the last removal-access and zero-QC display corrections. |
| Migration | Normal additive revision **0009** applied; running backend reports **0009 (head)** and **No new upgrade operations detected**. ORM comparison passed in PostgreSQL. Revisions 0001–0008 were not rewritten. No database reset, downgrade, volume deletion, balance override or user-data reset was performed; the existing organisation fixture remains idempotent. |
| Services/connectivity | All seven long-running services healthy; migrate and development-organisation fixture services exited 0. API readiness and frontend health returned HTTP 200. Authenticated personal gallery/capture and public dataset pages rendered through the running frontend. |
| Live enhancement HTTP flow | Two fresh synthetic accounts: personal capture saved two approved owner images, relabelled one, produced a valid private ZIP with private answers and denied guest/other-account access. Explicitly authorised public personal export included owner provenance, excluded private text and still denied community capture. Crowdsourced target 2 reserved 2 QC; one owner image earned/spent 0 QC, one community image paid 1 QC while paused, a third slot was denied, and closure refunded the unused 1 QC. Final available balances **owner 49 / contributor 51**, owner reserved **0**. Mixed public ZIP recorded both provenance types and changed neither wallet. |
| Final deployed-image recheck | Reauthenticated the **same** synthetic owner (no fresh welcome award), downloaded a valid two-image private ZIP, rendered the setup/gallery/capture pages, and confirmed the entire ledger was byte-for-byte unchanged by login/download checks. Guest private export was denied and the personal project stayed non-public. |
| Old export compatibility | Prepared the pre-enhancement Phase 2E version 3 after migration and downloaded it through the running frontend: regenerated archive SHA-256 exactly matches its recorded immutable checksum. |
| Preservation | Immediately after migration: **121 original ID-bearing rows** retained all captured original column fingerprints (session last-seen excluded); new columns were not substituted for old values. After live tests: original non-cache business fingerprints remain unchanged and original cache rows remain; mutable export-cache state/files intentionally changed during expiry/regeneration. Non-ID throttle buckets are operational, not part of that row count. All **4 original source image objects** retain identical SHA-256 hashes. Existing volumes and prior backups retained. |
| Backup | Git-ignored, mode-0600 `pre-0009-mvp.dump`; SHA-256 `d00860d53e8cebb860d144828a5105872bf8ce29b1caff6d4db332409dad0210`. PostgreSQL archive catalog readable. No restore drill was performed. |

## Resumption after interruption — 1 November 2026

The final audit was interrupted after implementation, tests and deployment had passed. On resumption Docker was stopped, so the first connectivity/preservation attempt failed with a missing Docker socket and refused PostgreSQL connection. Started Docker Desktop and the existing Compose services without rebuilding or changing volumes. The three background workers initially remained unhealthy; restarting those existing workers recovered their connections/heartbeats. Final check: all seven services healthy, API readiness and frontend health HTTP 200, revision 0009 with no schema drift, original row preservation passed and all four original source image SHA-256 hashes matched again. Ruff lint, formatting and diff checks also passed. No application or schema changes were needed during this resumption; the completed 124-backend/79-frontend regression results above remain the applicable full-suite runs.

## Corrections and remaining acceptance

Initial integration checks correctly failed on the old self-contribution rejection expectation, old readiness revision and stale API contract; updated fixtures/contracts for the explicitly authorised owner workflow and revision 0009. Owner images remain excluded from moderation rather than weakening its self-payout guard. New test-fixture syntax/type omissions and an optional-field selector were corrected. The full advanced builder test now expects the intentional optional default for new questions. Ruff/TypeScript/format checks were rerun successfully; no integrity guard was disabled to pass a test.

Final review corrected project-before-image locking, owner-removal capacity accounting, raw removal restrictions in private access/streaming, and misleading community-reward text on personal surfaces. Those corrections were regression tested and deployed. The final production build includes them.

**Manual checks still required:** physical iOS/Android camera and picker behaviour, sustained Save & Capture Next, portrait/landscape layout, keyboard/focus and screen-reader acceptance against the Figma frames, mobile background interruptions and natural upload/cache expiry. No connected browser was available for visual inspection. Live HTTP smoke tests do not claim physical camera or rendered-browser visual acceptance. Resource-limit branches were exercised synthetically; no full 128-MiB private/512-MiB public export load benchmark or production deployment was performed.

Policy points for review: crowdsourced surplus remains held until closure; publication/consent withdrawals remain terminal; publicly authorised personal labels require withdrawal before editing. Default Compose networking remains loopback-only and local storage remains development-gated. No cohorts, expanded notifications, offline synchronisation, payments, credit purchases or Phase 3 work was added.

---

# Navigation and Explore UI follow-up — 31 October 2026

- Guest Log in/Sign up links now share centred alignment, spacing and 44px minimum touch targets with the header navigation.
- Explore filter labels no longer add a bottom margin that lifts their inputs above Search. Controls align at their bottom edges, with consistent button height and vertical spacing on narrow screens. Shared dataset filters receive the same correction.
- Account navigation rechecks the existing no-store session endpoint on navigation, tab focus/visibility and every 30 seconds while visible. Confirmed expiry/revocation replaces the avatar with guest links; transient network failures preserve the last known state. Successful logout clears the avatar immediately. Responses that began before logout cannot restore stale authenticated navigation. No tokens are stored in browser storage.
- Added four regression tests: expired session, tab return, temporary network failure and immediate logout. Final frontend suite: **67 passed across 9 files**. The initial focus test fired before its first request completed; it now waits for the returned account to render. ESLint also identified effect-based prop copying; session state now derives from the current server prop without that extra render. Final ESLint, strict TypeScript, Prettier and production Docker build passed. The frontend was rebuilt/restarted; Explore and frontend health returned HTTP 200. Backend/database code was unchanged, so backend tests were not repeated for this UI-only follow-up.

Manual checks: open `/projects` as a guest at desktop and phone widths; compare navigation alignment and the Search button against neighbouring inputs. Sign in, sign out and confirm guest links appear immediately. Sign out in another tab, return here and confirm the avatar disappears without a reload. For server-side revocation/expiry while remaining on the page, allow up to 30 seconds for the next visible-tab check. Temporary API unavailability should not falsely change the account state. Browser visual inspection was unavailable through the connected Chrome tool in this session.

---

# Phase 2E verification — 31 October 2026

Phase 2E implementation and automated verification are complete; browser acceptance remains for review. See [phase-2e.md](phase-2e.md) for architecture, API/file inventory, publication policy and the complete two-account manual test steps. Historical results below are retained.

| Check | Actual executed result |
| --- | --- |
| Backend/PostgreSQL | **124 passed**, no skipped tests, five existing Starlette/httpx and Alembic deprecation warnings. Fresh disposable PostgreSQL 17 database; application database was not used for test fixtures. |
| Dataset integration | PostgreSQL tests cover explicit publication/consent/owner gates, excluded pending/rejected/restricted images, licensing, private access, ZIP integrity, manifest/CSV privacy, immutable versions, deterministic regeneration, missing-cache recovery, concurrent snapshots/workers, removal during generation/streaming, limits, retries, reports, expiry and unchanged ledger rows during downloads. Limit branches use bounded synthetic fixtures, not a full 512-MiB load benchmark. |
| Backend quality | Ruff lint passed; **75 Python files** passed formatting. OpenAPI contract and schema/migration tests passed within the suite. |
| Frontend | **63 tests passed across 9 files**. ESLint, strict TypeScript and Prettier passed using the Node 22 Docker build environment. Production Next.js standalone build and runtime-image packaging passed. |
| Compose | Configuration validation and build/start/wait passed after recovery. Database, backend, frontend, Mailpit, upload-cleaner, notifications and datasets worker are healthy. Migration and development-organisation fixture services exited 0. |
| Database | Running application reports **0008 (head)**; `alembic check`: **No new upgrade operations detected**. Migration creates publication/export records only when explicitly requested; existing approvals remain private. |
| HTTP/rendering | Backend readiness and frontend health HTTP 200; homepage and dataset library SSR HTTP 200. Public dataset API HTTP 200 with an empty library. This is a successful connectivity/empty-state check, not a live two-account export acceptance test. |
| Record preservation | A fresh pre-migration custom-format backup was created after PostgreSQL recovery. Read-only COPY-data comparison confirms all **103 original business/operational rows** remain byte-identical. The Alembic row changed from 0007 to 0008; public HTTP checks added two rate-limit rows. No original business/ledger row was changed or removed. Existing PostgreSQL/image volumes were retained. |
| Backup | Private, Git-ignored `pre-phase2e-resumed.dump` in the repository root, mode 0600; SHA-256 `bfbe5993b4cbd547061f8ede1d400bb5c193d747896effe9ec83b2440cfca4d0`. PostgreSQL archive catalog and data extraction succeeded. No restore drill was performed. |

## Failures, recovery and limits

- The earlier Docker build failed with **no space left on device** and Docker stopped responding. Frontend runtime packaging now copies Next.js standalone output rather than the entire build/dependency tree; its rebuilt image succeeds after Docker restart. No Docker prune, database reset or volume deletion was used.
- After restart, PostgreSQL refused a zero-filled 94-byte `postmaster.pid`, then a corrupted ephemeral socket lock. Confirmed no running container mounted the database volume; preserved the former as `postmaster.pid.pre-recovery-20261031`, and recreated only the database container to clear its writable-layer socket lock. PostgreSQL completed normal WAL crash recovery and accepted connections. No database files, WAL or credit records were repaired manually.
- Previous `/tmp` verification helpers and pre-crash backup/hash baselines were no longer present after restart. A new backup was taken before migration. Consequently, the post-recovery-to-post-migration row comparison is verified, but the earlier pre-crash row/image hash comparison cannot be repeated. Do not interpret retained volumes as proof that every original image byte survived the Docker failure.
- The first resumed test invocation failed because its temporary helper was missing; recreated the helper and ran the complete suite successfully. The first preservation comparison correctly reported the Alembic revision change and two added rate-limit records; checking all original rows separately passed. No integrity checks were weakened.
- Actual browser two-account publication/opt-in/download acceptance, mobile appearance, natural 15-minute expiry and a live multi-process HTTP export/removal exercise have **not** been executed on this resumed stack. Automated PostgreSQL/API/UI tests cover those branches; they are not claimed as manual browser results. Follow the manual instructions before acceptance.
- Production storage/deployment is not configured. Local adapters remain development-gated. Previously downloaded copies cannot be remotely revoked. Downloads cost **0 QC**, and no download feature posts ledger entries.

Stop after Phase 2E for review. No payments, credit purchases or marketplace features were added.

---

# Phase 2D verification — 31 October 2026

Phase 2D is implemented and stopped for review. The [implementation specification and complete two-account manual instructions](phase-2d.md) document policies, APIs and files. Earlier phase results below remain historical evidence.

| Check | Executed result |
| --- | --- |
| Backend suite with real PostgreSQL | **103 passed**, including the opt-in PostgreSQL migration/ledger test and its authentication, collection, submission and new moderation integration scenarios. Final disposable target: `qpqdata_phase1_test_40211203f6`. Five existing Starlette/httpx and Alembic configuration deprecation warnings remain. |
| Migrations and integrity | Normal staged migration from 0004 legacy fixtures through 0005, 0006 and **0007** passed; original legacy column values were preserved. ORM/schema comparison and offline PostgreSQL migration rendering passed. Applied 0006 was not rewritten for the later lock correction; a separate 0007 revision carries it. Revisions 0001–0005 have no diff. |
| Authentication/payout concurrency | A synchronised PostgreSQL test forces a recipient authentication transaction to hold its User lock and wait for the reviewer's eligibility lock. Payout and authentication both finish under a five-second lock timeout using FK-compatible `FOR NO KEY UPDATE` User locks. Existing welcome-grant, session, eligibility, nonnegative-wallet and concurrent debit tests also pass. |
| Moderation/credits | Owner/designated permission, cross-user and self-review denial, CSRF, approval, required rejection reason, final decision conflicts, duplicate/repeated approvals, synchronised same-image and distinct-image approvals, approval versus close, post-posting rollback, missing/corrupt images, criteria revalidation, forged reward amounts/recipients, orphan rewards, append-only history, insufficient-reservation service branch, residual refunds and exhausted escrow all pass. QC conservation across wallets plus held reservations is asserted. |
| Removal/notifications | Contributor and reviewer suppression, immediate access revocation, retained approved QC, actual object purge for new suppression, preservation of rejection bytes before 30 days, durable outbox, SMTP failure/backoff and successful retry without duplicate payouts pass. Natural elapsed 30-day retention acceptance was not manually observed; no immutable audit timestamps were altered to manufacture it. |
| Backend lint/format | Ruff lint passed; **65 Python files** passed formatting. `git diff --check` passed. |
| Frontend tests | **53 passed across 8 files**, including review reason validation, approval/error/retry UI, hidden images, contributor reasons/QC and same-origin proxy permissions/cookie filtering. Existing auth, collection and upload tests remain passing. |
| Frontend checks/build | ESLint, strict TypeScript and Prettier passed. Next.js production build passed on host and in Docker; the final Docker build includes `/reviews`, private review transport and updated wallet/submission UI. Frontend contracts were regenerated and match FastAPI's OpenAPI in the backend contract test. |
| Local services | Docker Compose validation/build/start/wait passed. **Database, backend, frontend, Mailpit, upload-cleaner and notifications are healthy**. Migrate and development fixture commands exited **0**. Existing database/image volumes remain in place. |
| Running schema | Application database reports **0007 (head)**. Running-container `alembic check` reports **No new upgrade operations detected**. |
| Connectivity/rendering | Backend live/ready and frontend health returned HTTP 200 after the final deployment. Homepage returned HTTP 200 with server-rendered API readiness; all nine referenced JS/CSS assets returned HTTP 200. Authenticated review, wallet and submission pages also rendered through the actual frontend transport in the smoke. |
| Live two-account workflow | Two fresh synthetic `.test` accounts used the working Mailpit/browser-bound link flow. Published 3 images × 2 QC: owner 44 available + 6 reserved. Two private uploads were reviewed while paused: approval paid 2 QC once despite retry; rejection paid zero and exposed its reason only after authentication. Closure returned only 4 unspent QC, leaving owner 48 and contributor 52. Removal revoked both image routes and retained QC. A follow-up on running 0007 reused those same accounts for a one-image collection: one 2-QC reward, duplicate retry unchanged, exhausted closure with no zero/refund entry and authorised reviewer removal. Across the two smoke collections: **2 reward entries totalling 4 QC**, 1 rejected submission and **3 SMTP outcome notices successfully delivered to Mailpit**. Both newly suppressed smoke images were purged with their audit rows retained. |
| Preservation | Private pg_dump and column/image hash baselines were created before migration. Immediately after 0006 and again after 0007 plus live tests: **all 63 preexisting rows retain every original column value, including auth fields and all ledger/project records; the one preexisting image retains identical bytes**. No original row/volume/image was removed or reset. Newly created smoke rows remain for review. The pre-2D suppressed image is grandfathered, not retroactively purged. |

## Failures encountered and corrections

- The first PostgreSQL run reached a new dependent-table foreign-key restriction before the legacy ledger TRUNCATE trigger assertion. The test now includes the new audit/outbox tables in the TRUNCATE statement and still requires the exact append-only trigger SQLSTATE; no guard was disabled.
- The old cleanup test assumed suppressed bytes were retained indefinitely. Its timestamp-touch assertion failed after the new policy had already purged the synthetic image. The assertions now check deletion plus preserved audit records. Existing removal requests are explicitly grandfathered with null purge schedules, preserving preexisting files.
- Synthetic fixtures initially used an unsupported licence literal, the failure-injection stub did not accept a keyword argument, and one permission test retained the contributor cookie before an owner-only call. Those fixtures/stubs/session switches were corrected; the complete PostgreSQL suite was rerun successfully.
- TypeScript initially found a missing newly required response field in an old fixture; a later invocation preceded regenerated types. Both were corrected by updating fixtures and regenerating the contract. Running standalone TypeScript concurrently with `next build` also raced with `.next/types` regeneration; rerunning after the build passed. Final production builds passed.
- The first live smoke stopped at a raw HTML substring assertion because React placed comment separators between the QC number and its label. A proper visible-text parser passed. The same two accounts and same collection were reauthenticated and the smoke resumed through closure/removal; no test account or credit balance was reset.
- Final lock analysis identified an implicit reward FK/User-lock deadlock risk. Added revision 0007 and the synchronised authentication/payout regression rather than changing applied 0006. Full backend tests, local migration, metadata check, services and a new payout on the running final revision passed afterward.

## Recovery baseline and limits

The pre-change custom-format database archive is `/tmp/qpqdata-pre-phase2d.dump`, mode 0600, SHA-256 `53ddd4ba7152c5c77813369919024173ae15d0fe53cf89c85c74d331ad84ecf5`. Column/image hash baselines are private files alongside it; no secret, token, email payload or image was printed or committed. Archive creation/checksum were verified; **a restore drill was not run**. Earlier recovery artifacts remain untouched.

The earlier documented concurrent authentication changes were inspected before implementation and were never reverted. The new baseline measures the current records rather than asserting that old authentication timestamps must revert to a prior phase. No original baseline column changed in this run; legitimate future login/last-seen activity may change auth operational fields and must be reported separately from ledger/project integrity.

No local functional blocker remains. **Native-browser visual/hydration, real phone layout and manual human originality/suitability review were not executed**; component and HTTP checks do not substitute for those acceptance checks. Production private storage, restricted runtime database roles, real organisational review and full lawful retention/backup erasure remain deployment gates. No public downloads, dataset ZIPs, general transfers or automatic clawbacks are implemented.

---

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

## Backend package separation — 31 October 2026

Reorganised the existing implementation into API routes/dependencies, schemas, services, database, core configuration, integrations, CLI and job packages. See [architecture](architecture.md#backend-package-structure). Updated imports, monkeypatch targets, Alembic environment imports and Compose entrypoints. No frozen migration revision/SQL resource or frontend API contract changed; no volumes were removed or reset.

Executed verification:

- First local and PostgreSQL-enabled runs failed during collection because the extracted SMTP `DeliveryError` was still imported from its former service module. Corrected callers to import it from `app.integrations.email`; reran the full suite successfully.
- Locked backend suite against a fresh disposable PostgreSQL database: **96 passed**, including migration, authentication, ledger/reservation and submission integration scenarios and the unchanged OpenAPI contract check. Five existing dependency/configuration deprecation warnings remain (Starlette/httpx and Alembic path separator).
- Ruff lint: passed. Ruff formatting: all **55 Python files** already formatted. `git diff --check`: passed.
- Frontend Vitest: **46 passed across 7 files**. Frontend source/dependencies/contracts were unchanged; frontend lint, typecheck and production build were not rerun for this Python package-only change.
- `docker compose config --quiet`: passed. Backend, migration, development-seed and cleanup images rebuilt successfully. Compose startup/wait succeeded: backend, cleanup worker, PostgreSQL and Mailpit healthy; migration and development-seed commands exited successfully. Existing frontend remained running.
- Running backend reports `0005 (head)`. Alembic metadata comparison reports no new upgrade operations. Frozen migration versions and SQL resources have no diff.
- Backend liveness/readiness and frontend health returned HTTP 200. Homepage rendered HTTP 200 with server-rendered API readiness; all nine referenced JavaScript/CSS assets returned HTTP 200.

No new features or schema changes were introduced. Browser camera/manual contribution acceptance was not repeated for this package-only change.
