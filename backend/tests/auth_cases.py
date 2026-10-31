from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auth
from app.config import Settings
from app.dev_email import DEV_ISSUER, VerificationError
from app.dev_email import verify as legacy_verify
from app.eligibility import eligible
from app.main import create_app
from app.models import (
    AuthSession,
    CreditLedgerEntry,
    DevEmailVerification,
    Organisation,
    OrganisationDomain,
    OrganisationMembership,
    User,
)


def exercise_authentication(engine, monkeypatch) -> None:
    settings = Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        environment="development",
        dev_email_enabled=True,
        auth_enabled=True,
    )
    sent = []
    monkeypatch.setattr(
        "app.auth.send_link", lambda config, email, token: sent.append((email, token))
    )

    def request(email, intent="signup", browser="b" * 43):
        with Session(engine) as session, session.begin():
            auth.request_link(session, settings, email, intent, "Synthetic Student", browser)
        return sent[-1][1]

    def redeem(token, browser="b" * 43, previous=None):
        with Session(engine) as session, session.begin():
            user, raw, csrf = auth.complete(session, settings, token, previous, browser)
            return user.id, raw, csrf

    def welcome_count(user_id):
        with Session(engine) as session:
            return session.scalar(
                select(func.count())
                .select_from(CreditLedgerEntry)
                .where(
                    CreditLedgerEntry.user_id == user_id,
                    CreditLedgerEntry.reason == "welcome_grant",
                )
            )

    def access(raw, csrf=None, mutation=False):
        with Session(engine) as session, session.begin():
            user = auth.authenticate(session, settings, raw, csrf, mutation)
            return user.id

    token = request("auth-student@university.test")
    with Session(engine) as session:
        row = session.scalar(
            select(DevEmailVerification).where(
                DevEmailVerification.email == "auth-student@university.test"
            )
        )
        assert row.intent == "signup" and row.token_hash != token
        assert (row.expires_at - row.requested_at).total_seconds() == 600
    with pytest.raises(auth.AuthError):
        redeem(token, "wrong-browser")
    with Session(engine) as session, session.begin(), pytest.raises(VerificationError):
        legacy_verify(session, settings, token)
    user_id, raw, csrf = redeem(token)
    assert access(raw) == user_id and welcome_count(user_id) == 1
    with pytest.raises(auth.AuthError):
        redeem(token)
    with pytest.raises(auth.AuthError):
        access(None)
    with pytest.raises(auth.AuthError):
        access(raw, "wrong-csrf", True)
    assert access(raw, csrf, True) == user_id
    with Session(engine) as session:
        stored = session.scalar(select(AuthSession).where(AuthSession.user_id == user_id))
        assert stored.token_hash != raw and stored.csrf_hash != csrf
        user = session.get(User, user_id)
        assert auth.balance(session, user) == 50
    # Login creates a fresh session, revokes the previous one and never repeats QC.
    with Session(engine) as session, session.begin():
        row = session.scalar(
            select(DevEmailVerification).where(
                DevEmailVerification.email == "auth-student@university.test"
            )
        )
        row.requested_at = datetime.now(UTC) - timedelta(minutes=2)
    token2 = request("auth-student@university.test", "login")
    _, raw2, csrf2 = redeem(token2, previous=raw)
    assert raw2 != raw and welcome_count(user_id) == 1
    with pytest.raises(auth.AuthError):
        access(raw)
    with Session(engine) as session, session.begin():
        auth.revoke(session, raw2)
    with pytest.raises(auth.AuthError):
        access(raw2)

    expired = request("auth-expired@university.test")
    with Session(engine) as session, session.begin():
        row = session.scalar(
            select(DevEmailVerification).where(
                DevEmailVerification.token_hash == auth.digest(expired)
            )
        )
        row.requested_at = datetime.now(UTC) - timedelta(minutes=11)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(auth.AuthError):
        redeem(expired)

    # Parallel redemption and independent parallel grant calls remain exactly once.
    concurrent = request("auth-concurrent@university.test")

    def race(_):
        try:
            return redeem(concurrent)[0]
        except auth.AuthError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(race, range(2)))
    winners = [r for r in results if r is not None]
    assert len(winners) == 1 and welcome_count(winners[0]) == 1

    def grant(_):
        with Session(engine) as session, session.begin():
            auth.grant_welcome(session, session.get(User, winners[0]), settings)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(grant, range(2)))
    assert welcome_count(winners[0]) == 1
    for values in [
        dict(amount=40, idempotency_key="bad-welcome"),
        dict(amount=50, idempotency_key=f"welcome:v1:{user_id}"),
    ]:
        with pytest.raises(IntegrityError), Session(engine) as session, session.begin():
            session.add(CreditLedgerEntry(user_id=user_id, reason="welcome_grant", **values))

    # Failure before activation commit rolls back proof, account, QC and session.
    failing = request("auth-rollback@university.test")
    original = auth.grant_welcome

    def fail(*args):
        raise auth.AuthError("Synthetic grant failure", 503)

    monkeypatch.setattr("app.auth.grant_welcome", fail)
    with pytest.raises(auth.AuthError):
        redeem(failing)
    with Session(engine) as session:
        assert (
            session.scalar(select(User).where(User.email == "auth-rollback@university.test"))
            is None
        )
        assert (
            session.scalar(
                select(DevEmailVerification).where(
                    DevEmailVerification.token_hash == auth.digest(failing)
                )
            ).consumed_at
            is None
        )
    monkeypatch.setattr("app.auth.grant_welcome", original)
    rollback_id, _, _ = redeem(failing)
    assert welcome_count(rollback_id) == 1

    before = len(sent)
    for email in ["personal@gmail.com", "someone@unknown.test", "user@sub.university.test"]:
        request(email)
    assert len(sent) == before
    unknown_login = request("unknown-login@university.test", "login")
    with pytest.raises(auth.AuthError):
        redeem(unknown_login)
    before = len(sent)
    with Session(engine) as session, session.begin():
        user = User(
            email="unverified@university.test",
            identity_issuer=DEV_ISSUER,
            identity_subject="unverified@university.test",
        )
        session.add(user)
    unverified_login = request("unverified@university.test", "login")
    with pytest.raises(auth.AuthError):
        redeem(unverified_login)
    assert len(sent) == before + 1

    # Real reviewed school/work domains require current membership evidence.
    with Session(engine) as session, session.begin():
        org = Organisation(name="Synthetic Employer", kind="employer")
        session.add(org)
        session.flush()
        session.add(
            OrganisationDomain(
                organisation_id=org.id,
                domain_ascii="research.example.org",
                reviewed_at=datetime.now(UTC),
                review_reference="synthetic-reviewed-evidence",
            )
        )
        org_id = org.id
    pending = request("employee@research.example.org")
    real_id, no_session, _ = redeem(pending)
    assert no_session is None and welcome_count(real_id) == 0
    with Session(engine) as session, session.begin():
        session.add(
            OrganisationMembership(
                user_id=real_id,
                organisation_id=org_id,
                evidence_reference="synthetic-current-employment-proof",
                verified_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
        )
        challenge = session.scalar(
            select(DevEmailVerification).where(
                DevEmailVerification.email == "employee@research.example.org"
            )
        )
        challenge.requested_at = datetime.now(UTC) - timedelta(minutes=2)
    login = request("employee@research.example.org", "login")
    _, real_raw, _ = redeem(login)
    assert access(real_raw) == real_id and welcome_count(real_id) == 1
    with Session(engine) as session, session.begin():
        membership = session.scalar(
            select(OrganisationMembership).where(OrganisationMembership.user_id == real_id)
        )
        membership.revoked_at = datetime.now(UTC)
    with pytest.raises(auth.AuthError):
        access(real_raw)
    # Reserved fixtures fail in production even when copied into its database.
    prod = Settings(database_url="postgresql+psycopg://unused")
    with Session(engine) as session:
        assert not eligible(session, prod, session.get(User, user_id))

    # HTTP API checks verify origin, CSRF, cookie flags, profiles and logout.
    client_token = request("auth-http@university.test", browser="c" * 43)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/auth/me").status_code == 401
        assert client.post("/api/v1/auth/verify", json={"token": client_token}).status_code == 403
        client.cookies.set("qpq_login_nonce", "c" * 43)
        response = client.post(
            "/api/v1/auth/verify",
            json={"token": client_token},
            headers={"Origin": settings.frontend_url},
        )
        assert response.status_code == 200 and response.json()["status"] == "authenticated"
        assert "token" not in response.text
        assert (
            "HttpOnly" in response.headers["set-cookie"]
            and "SameSite=lax" in response.headers["set-cookie"]
        )
        assert client.get("/api/v1/auth/me").json()["credit_balance"] == 50
        headers = {"Origin": settings.frontend_url, "X-CSRF-Token": client.cookies.get("qpq_csrf")}
        assert (
            client.patch(
                "/api/v1/auth/profile", json={"display_name": "Edited Student"}, headers=headers
            ).json()["display_name"]
            == "Edited Student"
        )
        assert (
            client.patch(
                "/api/v1/auth/profile", json={"display_name": " "}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/auth/logout", headers={"Origin": settings.frontend_url}
            ).status_code
            == 403
        )
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401

    # API enumeration and persistent throttling return no account-specific details.
    with TestClient(create_app(settings)) as client:
        responses = []
        for address in ["does-not-exist@university.test", "personal@gmail.com"]:
            response = client.post(
                "/api/v1/auth/request-link",
                json={"email": address, "intent": "login"},
                headers={"Origin": settings.frontend_url},
            )
            assert response.status_code == 200
            responses.append(response.json())
        assert responses[0] == responses[1]
        for _ in range(6):
            response = client.post(
                "/api/v1/auth/request-link",
                json={"email": "rate-limited@university.test", "intent": "login"},
                headers={"Origin": settings.frontend_url},
            )
        assert response.status_code == 429
        assert (
            client.post(
                "/api/v1/auth/verify",
                json={"token": {"secret": "sensitive-input"}},
                headers={"Origin": settings.frontend_url},
            ).text.find("sensitive-input")
            == -1
        )

    # A verification-purpose token cannot become a login-purpose token.
    with Session(engine) as session, session.begin():
        old = DevEmailVerification(
            email="old-purpose@university.test",
            token_hash=auth.digest("z" * 43),
            requested_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            intent="verify",
            identity_issuer=DEV_ISSUER,
        )
        session.add(old)
    with pytest.raises(auth.AuthError):
        redeem("z" * 43)

    # Fail after the ledger insert: the whole activation must still roll back.
    after_grant = request("auth-after-grant@university.test")
    original_session_class = auth.AuthSession

    def fail_session(**kwargs):
        raise auth.AuthError("Synthetic session failure", 503)

    monkeypatch.setattr("app.auth.AuthSession", fail_session)
    with pytest.raises(auth.AuthError):
        redeem(after_grant)
    monkeypatch.setattr("app.auth.AuthSession", original_session_class)
    with Session(engine) as session:
        assert (
            session.scalar(select(User).where(User.email == "auth-after-grant@university.test"))
            is None
        )
        assert (
            session.scalar(
                select(DevEmailVerification).where(
                    DevEmailVerification.token_hash == auth.digest(after_grant)
                )
            ).consumed_at
            is None
        )
    after_id, _, _ = redeem(after_grant)
    assert welcome_count(after_id) == 1

    # Check production cookie attributes with an eligible non-fixture account.
    with Session(engine) as session, session.begin():
        membership = session.scalar(
            select(OrganisationMembership).where(OrganisationMembership.user_id == real_id)
        )
        membership.revoked_at = None
        challenge = session.scalar(
            select(DevEmailVerification).where(
                DevEmailVerification.email == "employee@research.example.org"
            )
        )
        challenge.requested_at = datetime.now(UTC) - timedelta(minutes=2)
    secure_token = request("employee@research.example.org", "login", browser="p" * 43)
    secure_settings = Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        auth_enabled=True,
        frontend_url="https://qpq.example.org",
        smtp_host="smtp.example.org",
        smtp_starttls=True,
        email_sender="noreply@qpq.example.org",
    )
    with TestClient(create_app(secure_settings), base_url="https://qpq.example.org") as client:
        client.cookies.set("__Host-qpq_login_nonce", "p" * 43)
        response = client.post(
            "/api/v1/auth/verify",
            json={"token": secure_token},
            headers={"Origin": secure_settings.frontend_url},
        )
        assert response.status_code == 200
        cookies = response.headers.get_list("set-cookie")
        assert all(
            "Secure" in cookie
            and "HttpOnly" in cookie
            and "SameSite=lax" in cookie
            and "Path=/" in cookie
            for cookie in cookies
        )
        assert all("Domain=" not in cookie for cookie in cookies)
        assert "__Host-qpq_session=" in response.headers["set-cookie"]

    for kind in ["idle", "absolute", "disabled"]:
        t = request(f"auth-{kind}@university.test")
        ident, sess, _ = redeem(t)
        with Session(engine) as session, session.begin():
            row = session.scalar(
                select(AuthSession).where(AuthSession.token_hash == auth.digest(sess))
            )
            if kind == "idle":
                row.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
            if kind == "absolute":
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            if kind == "disabled":
                session.get(User, ident).disabled_at = datetime.now(UTC)
        with pytest.raises(auth.AuthError):
            access(sess)
    with Session(engine) as session, session.begin():
        assert all(auth.throttle(session, "synthetic-limiter", 2) for _ in range(2))
    with Session(engine) as session, session.begin():
        assert not auth.throttle(session, "synthetic-limiter", 2)
