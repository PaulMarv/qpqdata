> Phase 2A update: the legacy verification steps below remain valid. When auth is enabled, eligible verification also posts the one-time 50 QC welcome grant, but still creates no login session. Use `/signup` and `/login` for the separate browser-bound magic-link flow; see [phase-2a.md](phase-2a.md). The later Phase 2A behavior supersedes the earlier no-credits statement below.

# Development email verification with Mailpit

This is a local mailbox-verification harness, not production authentication. A verified test mailbox creates or activates a user under the separate `urn:qpqdata:development-email` issuer. It creates no session, password, membership, production eligibility, credits or reviewer privileges.

## Start safely

From the project directory:

```sh
cd /Users/user/Desktop/qpqdata
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 120
docker compose ps -a
```

Keep the existing `.env` database credentials and `POSTGRES_HOST_PORT=55432`. Do not reset the database or remove the volume. These nonsecret settings explicitly enable the local harness:

```dotenv
QPQ_ENVIRONMENT=development
QPQ_DEV_EMAIL_ENABLED=true
QPQ_FRONTEND_URL=http://localhost:3000
QPQ_VERIFICATION_TTL_SECONDS=900
```

Compose defaults to production/disabled when the two development settings are absent. Application defaults are also production/disabled. The `dev-seed` job refuses to run unless both development conditions hold, so missing settings fail startup rather than silently seed data. This Compose file is for local development only, not staging/production deployment.

Migration `0002` only adds `dev_email_verifications`; migration `0001`, existing records and ledger triggers are preserved. The explicit idempotent seed creates **QPQData Test University** and the reviewed fixture domain **university.test**. It seeds no accounts. It refuses conflicting or revoked fixture records rather than silently overwriting them.

## Complete manual test: successful verification

1. Confirm `db`, `mailpit`, `backend` and `frontend` are healthy. `migrate` and `dev-seed` should show `Exited (0)`.
2. Open http://localhost:3000/dev-email using the exact frontend origin configured above.
3. Leave the example address **student@university.test**, then click **Register test account**.
4. Confirm the page says **Check Mailpit for your verification email.**
5. Open http://localhost:8025. This inbox captures local SMTP messages; no real mailbox or external email credentials are required.
6. Select the message addressed to **student@university.test**, titled **Verify your QPQData development email**.
7. Click **Verify development email** in its HTML body. If using the text view, open the provided URL including its fragment. Do not paste the link into shared logs, issue reports or chat.
8. The frontend opens `/dev-email/verify`. It reads the fragment into memory and removes it from the address bar. Merely opening the page does not consume the token.
9. Click **Verify email** once.
10. Confirm **Development account activated. Email verified; no login session created.** The button becomes disabled. This message confirms mailbox verification only; there is no login or production eligibility flow.
11. Optionally confirm the stored account through a read-only query:

```sh
docker compose exec -T db psql -U qpqdata -d qpqdata -c "SELECT email, email_verified_at IS NOT NULL AS email_verified FROM users WHERE identity_issuer = 'urn:qpqdata:development-email' AND email = 'student@university.test';"
```

Expected: one row with `email_verified = t`. No token hashes or secret links are printed by this query.

## Repeatable and negative tests

- **Other addresses:** repeat with `student+second@university.test`, `researcher@university.test` or another new local part. All exact-domain fixture addresses are supported without individual preapproval. Nothing is delivered externally.
- **Reused link:** reopen the original email link, click **Verify email** again, and expect **Link invalid or expired. Request a new verification email.** Reloading the cleaned URL cannot restore the token; reopen it from Mailpit to test reuse.
- **Unknown organisation:** register `student@unknown.test`; expect **Use an approved development organisation address.** No message should arrive.
- **Personal email:** register `student@gmail.com`; expect the same rejection and no message. The backend sends no mail to personal addresses.
- **Subdomain/suffix confusion:** `student@sub.university.test` and `student@university.test.attacker.example` must also be rejected. Eligibility never uses a domain-suffix shortcut.
- **Resend:** wait at least one minute before registering the same address again. A new challenge invalidates the older link. Open the newest email to verify. Requests within the minute return a cooldown message; use a new fixture address for immediate repeated tests.

## Manual expired-link test without editing database data

Temporarily start only the backend with a 30-second token lifetime:

```sh
QPQ_VERIFICATION_TTL_SECONDS=30 docker compose up -d --no-deps --wait backend
```

1. Register a fresh address such as `expired+manual1@university.test` at http://localhost:3000/dev-email.
2. Open its message in Mailpit. Confirm the text body states the link expires in 30 seconds.
3. Wait at least 32 seconds after receipt.
4. Open the link and click **Verify email**.
5. Expect **Link invalid or expired. Request a new verification email.** The unverified account must not be activated.
6. Restore the `.env` default (900 seconds) with:

```sh
docker compose up -d --no-deps --wait backend
```

Do not shorten expiry by updating existing application records. The automated PostgreSQL suite also tests exact expiry, reuse, replacement, simultaneous redemption and domain revocation against a separate disposable database.

## Security boundaries

- Both seed and every backend registration/redemption require the explicit development environment and feature flag. Enabling the flag with staging, production or test settings is rejected during settings validation. With it disabled the endpoints return 404, even if a copied database contains the fixture.
- Only exact `university.test` and the explicit fixture review marker are accepted here; no general production-domain approval service is implemented. Reserved `.test` domains must be rejected by future production eligibility code, independent of any copied fixture data.
- This harness accepts a deliberately restricted ASCII fixture-address syntax. Production email parsing, IDNA handling, federation, current institutional affiliation, reviewer identity and membership evidence remain separate work; this code is not that service.
- Mailpit SMTP is reachable internally at `mailpit:1025`; SMTP is not published on the host. Its inbox UI/API binds only to `127.0.0.1:8025`. No relay is configured. Insecure local SMTP is restricted to known local Mailpit hostnames and port 1025 by settings validation.
- Verification links use `QPQ_FRONTEND_URL`, which must be a loopback HTTP origin when enabled. Raw 256-bit random bearer tokens appear only in the email and client memory; the database stores SHA-256 hashes. Default expiry is 15 minutes. Database row locks make consumption single-use across concurrent requests.
- Links carry a fragment, not a query parameter. The frontend removes it from history after reading and requires an explicit POST confirmation. Token values are never saved to browser storage. Referrer policy is `no-referrer`.
- The same-origin Next.js transport checks Origin and JSON content type, limits request bodies, and forwards to fixed typed backend paths. No frontend business or eligibility rules are authoritative.
- Validation and database/SMTP errors are sanitised. Do not enable SMTP debugging, body logging, URL/fragment analytics or reverse-proxy query/body logging. The Compose backend continues to disable access logs. The captured email necessarily contains its secret link in Mailpit; the local inbox must not be exposed or shared.
- Mailpit mail is ephemeral and may disappear when its container is recreated. The PostgreSQL volume and token state persist. Request a fresh email if an inbox message is lost; no database reset is needed.
- SMTP runs within the challenge transaction. Delivery failure rolls it back; a rare commit failure after SMTP can leave an unusable email. Request a replacement after cooldown. No durable production mail outbox is claimed.

Mailpit configuration follows the [official Docker documentation](https://mailpit.axllent.org/docs/install/docker/). The pinned v1.32.0 image was selected from the [official release](https://github.com/axllent/mailpit/releases/tag/v1.32.0).
