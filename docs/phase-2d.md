# Phase 2D — Moderation and reserved-credit payouts

## Scope and policy

Build on the Phase 2C packages, immutable criteria snapshots, private storage, verified eligible cookie sessions and append-only ledger. No image-storage replacement, dataset exports, public image URLs, generic credit transfers or automatic clawbacks are introduced.

Owners and explicitly designated moderators can review workflow-1 submissions in their collections. Every request rechecks backend authentication, verification, eligibility, session/CSRF and current collection permission. Moderator assignment/revocation is owner-only; reviewers cannot decide their own submissions. Older submissions with no workflow version require separate review and are excluded. Reviewers see contributor display names (or “Contributor”), not email addresses or organisation proofs. Contributor metadata and consent stay private.

Reviews are allowed while **Published or Paused**, including after a closing date stops new contributions. Pausing holds the remaining funds. A collection may close only after all Pending submissions and unexpired active upload leases are resolved. Reject hidden Pending submissions with an explicit reason before closing. Approved records do not block closure. Closed collections never reopen; no new decision or reservation is created for them. Exact retries of an existing decision still return its original result after closure. Decisions are final in this phase: changing an approval to rejection or changing a rejection reason is a conflict. Appeals require a later reviewed workflow.

## Atomic accounting

A publication already debited the owner’s available wallet into a reservation. Paying an image appends **one positive `collection_reward` ledger entry** for the contributor and consumes the same amount of that held escrow. Debiting the owner’s available wallet again would charge twice. No new QC is minted: total available QC across wallets plus held escrow is conserved.

Approval locks the project and then the submission, rechecks current permission and Pending state, removal restrictions, object availability/size/decoded format/dimensions, recorded criteria answers, requested image count and remaining reservation. It inserts the reward, immutable decision, terminal submission status and notification-outbox record in one transaction. Failed validation, SQL constraints, commit or later service steps roll everything back. The response is returned after the transaction commits.

`moderation_decisions` records the exact submission, reviewer, time, outcome, rejection reason, reward and unique reward-ledger reference. The submission links the immutable project/version, label, answers, contributor and consent. The reward entry links its source project and recipient. Canonical `reward:v1:<submission UUID>` keys plus one decision per submission and a unique reward-entry reference make retries and simultaneous requests idempotent. A contradictory decision returns 409.

The reservation’s original amount/debit never changes. Remaining held QC is `reservation.amount - SUM(collection_reward.amount)` while published/paused. Closing appends a positive `collection_release` for **only the remaining amount**, linked to the original reservation debit; this reference records the partial release, not a full reversal of the original budget. If all QC was paid, closure adds no zero-value entry and leaves the release pointer null; closed state and exhausted escrow together prove no funds remain. No balance or spent counter is mutable.

New deferred PostgreSQL funding guards require each reward to match its exact approved decision, contributor, collection and configured reward; every terminal workflow-1 submission must match its decision. They prohibit orphan rewards, overspending, excess approvals, mismatched residual refunds, partial commits and releasing pending funding. Existing ledger UPDATE/DELETE/TRUNCATE, nonnegative-wallet and reservation immutability guards remain. Positive rewards lock the escrow project rather than the recipient’s User row; they cannot overdraw a wallet and this avoids reversing the existing authenticated User→eligibility lock order. Other wallet postings and authentication retain mutually exclusive User-row locks using `FOR NO KEY UPDATE`. These still serialise wallet/account writers while permitting foreign-key KEY SHARE checks against an unchanged user ID. Revision 0007 makes this follow-up without rewriting applied revision 0006. Services use PostgreSQL’s default READ COMMITTED isolation. See PostgreSQL’s [row-locking documentation](https://www.postgresql.org/docs/17/explicit-locking.html) and [deferred constraint triggers](https://www.postgresql.org/docs/17/sql-createtrigger.html).

## Capacity and discovery

The dashboard distinguishes requested target, active uploads, pending, approved and rejected images. Remaining funded approvals is the smaller of unspent QC / configured reward and requested count minus approved count. This number includes slots already occupied by pending images; it does not promise additional submission capacity. Existing admission guards count unexpired uploads + pending + approved against requested capacity, so pending work cannot overbook. Rejection frees admission capacity without consuming QC. Hidden approved images still count as approved and paid; hiding cannot generate a replacement payout beyond the original target.

`/reviews` is protected, paginated and filterable by collection/status, with secure image access and per-image decisions. Access it through **My Collections → Review submissions**. My Submissions displays decisions, rejection reasons and earned QC. Wallet shows available/remaining reserved QC and paginated immutable ledger history, including reward submission references.

## Removal, retention and notifications

Contributors retain the Phase 2C removal endpoint. Owners/designated reviewers can also hide an image through the review interface. Suppression is permanent in this phase and immediately blocks every contributor and moderation image endpoint. A Pending suppressed image cannot be approved. Removal requests and decision/consent/version/ledger records are preserved.

**Earned QC is retained after removal.** No automatic clawback, reversal or silent ledger edit exists. A future fraud/reversal policy requires explicit review; it must use compensating entries rather than changing history.

New removal requests opt into byte deletion (`purge_after`); the cleanup worker deletes their referenced objects on its next successful scan, normally within 60 seconds. Existing pre-2D removal records receive a null purge date and their images remain hidden and preserved until separately reviewed. This intentionally preserves all existing images rather than retroactively applying a deletion policy. Newly rejected image bytes are retained privately for 30 days after the decision and then purged by cleanup. Pending and approved unsuppressed bytes are retained for the collection; no dataset distribution is enabled. `image_deleted_at` records completed deletion; audit metadata stays. Deletion is idempotent; a storage/DB failure is retried. This covers the live object volume, not old backups: backup erasure and a full lawful-retention/review process remain deployment prerequisites. Operational escalations from non-contributors require a trusted operator to assess the report and use an authorised owner/moderator removal action; there is no public reporting or automated adjudication endpoint.

Outcome notices use the existing SMTP adapter through a durable outbox. The `notifications` Compose worker sends bounded batches, locks jobs with SKIP LOCKED and retries SMTP failures with backoff. Emails contain only the outcome/earned QC and the configured frontend `/submissions` URL, with no image, answers, rejection reason, credentials or tokens. Contributors read the full reason after authentication. UI says notification **queued**, not delivered. SMTP is at-least-once: a crash between send and marking delivery can duplicate an email; it cannot duplicate a payout. Stable Message-ID aids correlation but does not guarantee provider deduplication. No credential or message payload is logged.

## API and implementation map

- `GET /api/v1/moderation`: current reviewer’s dashboard; `project_id`, `status`, `page`, `page_size`.
- `GET /api/v1/moderation/{ident}/image`: no-store authorised private image.
- `POST /api/v1/moderation/{ident}/decision`: `{ "outcome": "approved" }` or `{ "outcome": "rejected", "reason": "…" }`.
- `POST /api/v1/moderation/{ident}/removal-request`: same reason/details contract as contributor removal.
- `POST /api/v1/projects/{project_id}/moderators`: owner-only `{ "user_id": "<verified account UUID>", "active": true/false }`. Revocation serialises with decisions on the project row. Eligible sessions are still required; designation never overrides eligibility.
- `GET /api/v1/wallet`: authenticated, paginated wallet and transaction history.
- Same-origin Next.js `/api/moderation` transport allowlists routes and forwards only session/CSRF cookies; origin, bounded JSON, timeouts and no-store headers apply. Frontend contracts are regenerated from FastAPI.
- Backend: `api/routes/moderation.py`, `schemas/moderation.py`, `services/moderation.py`, `services/wallet.py`, `services/notifications.py`, `jobs/notifications.py`, updated cleanup and submission/project services.
- New migration `0006_moderation.py` + frozen `0006_guards.sql`: three tables (18 model tables total), nullable image-deletion/purge scheduling fields, and additive/replaced guards. Revision `0007_reward_locking.py` adds the User-lock compatibility correction after 0006 was deployed. Revisions 0001–0006 remain frozen once applied. No preexisting rows are seeded, reclassified, paid or reset.

Development remains local-only; the existing storage/auth environment gates remain. Compose’s administrator/bootstrap identity is not production role provisioning. Owners of a PostgreSQL database can bypass triggers; restricted runtime roles, real organisational membership operations, production private storage and production moderation/reporting policies remain deployment gates.

## Manual two-account end-to-end test

Use localhost and synthetic pictures, never personal documents, faces, addresses or third-party copyrighted images. These steps create new development records; do not reset a volume or alter existing accounts.

1. Start Docker and run `docker compose up --build -d --wait --wait-timeout 180` from the repository. Check `docker compose ps -a`: database, API, frontend, Mailpit, cleanup and notification workers should be healthy; migrate/dev-seed should exit 0. `docker compose exec -T backend .venv/bin/alembic current` must show `0007 (head)`.
2. Open a normal browser window at `http://localhost:3000/signup`. Use a fresh `owner-2d-<unique>@university.test` address. Open `http://localhost:8025`, find its email and open the link **in the browser profile that requested it**. Confirm activation and a 50 QC wallet. If using an existing account, record its current balances instead of expecting another welcome grant.
3. Use a separate browser profile/incognito window for `contributor-2d-<unique>@university.test`. Request its signup there and open its Mailpit link in that same profile. Confirm 50 QC. Keep the two authenticated cookie jars separate.
4. As owner, create a complete collection with target **3 images**, reward **2 QC**, licence/reuse terms and at least one label. Add required criteria questions, preview, then publish. Wallet should show **44 available + 6 reserved** for a fresh account.
5. As contributor, browse that collection, read requirements, select two different original/synthetic images, answer every required question independently, confirm permission/reuse/privacy and upload. Both appear Pending Review in My Submissions with **0 QC earned**. Contributor wallet remains 50.
6. As owner, go to My Collections → Review submissions. Filter by the collection and Pending. Confirm counts: **3 requested, 2 pending, 0 approved**, six QC held and three funded approvals (two already occupied by pending images). Check private previews, labels and definition version. Open the same review in a second owner tab for the retry check.
7. Pause the collection from its owner controls. New contributions must fail, but existing Pending reviews remain actionable. Approve the first image; it becomes Approved with 2 QC paid. In the stale second tab approve that same image again: no second reward appears. The contributor sees **52 available**, and the owner has **44 available + 4 reserved**. Reload Wallet history to inspect the reward’s collection/submission and ledger IDs.
8. Try rejecting the second image with an empty/whitespace reason: the UI/API must refuse. Enter a clear reason and reject it. Contributor My Submissions shows Rejected, the exact reason and 0 QC earned; the image stays private. The reviewer cannot change this final decision.
9. Wait up to 15 seconds and open Mailpit. Both outcome emails should point to the configured `/submissions` page. Reading full details requires login. SMTP outage must not undo a decision or create an extra reward; queued notices retry when delivery recovers.
10. With all Pending work resolved and no active uploads, close the collection. Only **4 unspent QC** returns: owner **48 available, 0 reserved**; contributor **52 available**. Closing/reloading/retrying cannot refund again or reopen the collection. As a separate check, try closing another collection while it has Pending work; closure must fail.
11. As contributor, request removal of the approved image, or as owner use **Hide image & request removal** in its review. Refresh both profiles: both image endpoints must deny access immediately. Status/consent/decision history and the **2 QC earned remain**. New requests’ bytes are purged by the next successful cleanup scan. Rejected images expire after 30 days; do not change database timestamps or disable guards to force this test.
12. In the contributor profile, attempt to open the owner’s review image endpoint using a submission ID from the owner page. It must fail; the contributor’s own `/api/submissions/<id>/image` route remains the separate authorised route unless suppressed/deleted. Guests visiting `/reviews` are directed to login. No public object URL exists.
13. Optional designated reviewer check: obtain a third verified account’s UUID from its own `/api/auth/me` response (this endpoint does not disclose tokens). In the owner browser, call the same-origin endpoint below from developer tools, substituting IDs. The reviewer can then visit `/reviews`. Repeat with `active:false` to revoke. A moderator cannot approve their own image, and cannot designate another moderator.

```js
await fetch('/api/moderation/<collection UUID>/moderators', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({user_id: '<reviewer account UUID>', active: true})
});
```

Review [verification.md](verification.md) for executed checks and limitations. Browser/device acceptance is separate from API/component tests.
