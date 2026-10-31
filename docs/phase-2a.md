# Phase 2A — Authentication and User Accounts specification

Approved on 30 October 2026. The user selected **passwordless email-link authentication**; email-and-password login is not required for the MVP. Stop after Phase 2A for review.

## Requirements and implemented contract

| Requirement | Implementation |
| --- | --- |
| Preserve foundation | Add revision 0003; do not change 0001/0002 or reset storage. Preserve Mailpit, the approved development organisation, existing users and verification records. |
| Signup | `/signup` requests an email-proof challenge for an approved school/work domain. Verification creates or reuses only the matching email-issuer account; federated identities are never automatically linked. |
| Login | `/login` issues a separate login-purpose magic link with a fixed 600-second lifetime. Redemption requires an existing verified, enabled account and current backend eligibility. |
| Token security | 256-bit random values, SHA-256 hashes at rest, explicit purposes, expiry, one-minute resend cooldown, replacement and single-use row locks. Links carry fragments, require confirmation, and are bound to the initiating browser's HttpOnly nonce. |
| Sessions | Hashed opaque server-side records. Session and CSRF cookies are HttpOnly, SameSite=Lax, Path=/, with Secure and __Host- prefixes outside development. No tokens in localStorage or JSON responses. |
| Session lifetime | Default absolute lifetime 12 hours; idle timeout 30 minutes, both enforced by backend. Reauthentication rotates the session and revokes the preceding cookie's session. Logout revokes it in PostgreSQL and clears cookies. |
| Request integrity | Origin checks at both BFF and backend; protected mutations require the session-bound CSRF secret forwarded by the same-origin BFF. Foreign/missing origins fail closed. |
| Account enumeration/rate limits | Generic request responses for existing, absent, unverified and domain-ineligible accounts. Approved-domain login requests perform SMTP delivery regardless of account existence; redemption never creates a login-only account. Persistent limits: 5 email requests and 100 backend-peer requests per 15 minutes, plus one-minute mailbox cooldown. Redemption is limited to 100 attempts per backend peer per 15 minutes. |
| School/work eligibility | Exact reviewed organisation domain, accepted organisation kind (school/university/employer), verified mailbox, non-disabled user and current non-revoked membership evidence for real domains. No suffix guessing or postcode-like similarity matching. |
| Development exception | Only university.test with the explicit fixture marker, development environment and dev-email flag. Reserved .test/.invalid/.localhost/.example domains are denied elsewhere, even if copied into the database. |
| Profile | Backend-authorised `GET /api/v1/auth/me` and `PATCH /api/v1/auth/profile`; display-name edit only. Email changes require separate re-verification design and are not enabled. |
| Guest navigation | Exactly Log in and Sign up account actions. |
| Authenticated navigation | Profile avatar summary only; its menu contains My Profile, My Collections, My Submissions, QPQ Wallet and Sign Out. |
| Protected routes | Profile, wallet, collections and submissions pages require backend-authenticated eligibility. Collections/submissions remain placeholders, with no feature APIs. |
| Welcome QC | Exactly 50 QC once per eligible verified user. User activation, proof consumption, ledger insertion and session insertion commit atomically. Pending real membership review creates no session or welcome grant. |
| Credit integrity | Existing append-only triggers preserved. Unique welcome-per-user index, canonical idempotency key and welcome amount/key check added. Wallet computes SUM(amount); no mutable balance or transfers. |
| Regression tests | Preserve previous verification and ledger tests; add replay, purpose isolation, browser binding, sessions, CSRF, expiry, eligibility, concurrency, rollback, production cookie flags, navigation and rate-limit tests. |

## Existing implementation inventory before Phase 2A

Mailpit SMTP delivery and loopback inbox, dev-only idempotent test-university seed, hashed expiring verification tokens, an explicit confirmation UI and tests were already working. Users, memberships, reviewed domains and append-only credits were modelled. No login, logout, sessions, profile API, authenticated navigation or welcome grant existed.

## Architecture and migration choices

FastAPI remains authoritative. Next.js route handlers are transport only: fixed typed API operations, an Origin check, bounded JSON bodies, cookie forwarding and propagation of Set-Cookie after backend commit. Server-rendered protected pages call the same backend `me` contract and fail closed. Navigation state is refreshed after login/logout/profile edits.

The historical `dev_email_verifications` table name is retained to avoid moving existing records or duplicating the working token store. Revision 0003 adds intent, issuer, display name and browser-binding hash. Legacy rows default to verification purpose and keep their existing token hashes/expiry/consumption state. The legacy endpoint accepts only verification-purpose development tokens; authentication accepts only signup/login intents. Requests for a new purpose supersede old links for that mailbox. Both flows share the existing SMTP delivery implementation; the legacy verification UI and links remain operational.

No automatic production organisation approval or membership-review UI is provided. Real signup email verification can leave the account pending membership review. Once independently reviewed evidence is recorded through an authorised operational process, the first eligible authentication transaction issues the welcome grant and session. Existing verified development accounts receive their grant on first eligible login; no bulk backfill rewrites old records. When auth is enabled, the legacy development verification transaction also grants welcome QC once eligibility is established, without creating a login session.

## Production and operational gates

Auth is disabled by default (`QPQ_AUTH_ENABLED=false`). Local `.env` explicitly enables it. Production/staging enabling requires an HTTPS frontend origin, non-local SMTP with STARTTLS and a configured non-test sender. Real provider credentials and membership-approval operations are not invented. Test fixtures remain dev-only.

The backend peer limiter sees the Next.js container as the peer in this architecture; its 100-request limit is shared by that instance. Forwarded client IPs are not trusted; Compose runs Uvicorn with proxy-header interpretation disabled. Before public deployment, review proxy identity/rate-limit capacity, mail delivery/outbox reliability, session/throttle retention, runtime least privilege, backup retention, HTTPS/CSP and provider configuration. No unreviewed proxy trust or automatic cleanup job is added here.

Mailbox-local parts are normalised to lowercase by policy. The maintained email-validator parser handles syntax and IDNA; DNS deliverability checks do not replace reviewed organisation evidence. A small explicit denylist also rejects common shared personal-email providers, but acceptance is always based on the reviewed registry plus membership, never a completeness claim about that denylist.

## Manual acceptance

1. Start `docker compose up --build -d --wait --wait-timeout 120` with the existing development `.env` and `QPQ_AUTH_ENABLED=true`.
2. Visit `/signup`, enter a fresh university.test address and optional display name. Open Mailpit at http://localhost:8025 in the **same browser**, then follow its QPQData link and click Verify email.
3. Expect `/profile`, the avatar instead of Log in/Sign up, and all five profile-menu entries. Edit the display name and save.
4. Open QPQ Wallet: expect 50 QC. Collections/submissions links show protected unavailable-feature pages.
5. Sign Out. Protected pages redirect to `/login`, and `me` rejects the old session.
6. After the one-minute resend cooldown, log in using that existing verified address. Follow the new login-purpose email link within 10 minutes in the initiating browser. The same account and balance of 50 QC must remain.
7. Reopen a consumed link: expect rejection. A different browser without the initiating nonce must also be rejected. Request a fresh link instead of copying cookies or tokens.
8. Personal/unknown organisation addresses receive the generic response but cannot activate or sign in. Unverified/absent accounts cannot redeem login-only links. Real accounts lacking membership approval remain pending without credits.
9. Run the locked backend suite with TEST_DATABASE_URL pointing to a newly created empty disposable PostgreSQL database; it exercises expiry without changing application timestamps. Run frontend lint/typecheck/tests/build.

See `docs/verification.md` for actual executed results and remaining limits.
