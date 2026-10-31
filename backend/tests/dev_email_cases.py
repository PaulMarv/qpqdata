import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dev_email import DEV_ISSUER, DeliveryError, VerificationError, register, verify
from app.dev_seed import TEST_DOMAIN, seed
from app.models import DevEmailVerification, OrganisationDomain, User


def exercise_verification(engine, monkeypatch) -> None:
    settings = Settings(
        database_url="postgresql+psycopg://unused",
        environment="development",
        dev_email_enabled=True,
    )
    sent = []
    monkeypatch.setattr(
        "app.dev_email.send_verification", lambda config, email, token: sent.append((email, token))
    )

    def request(email):
        with Session(engine) as session, session.begin():
            register(session, settings, email)
        return sent[-1][1]

    def redeem(token):
        with Session(engine) as session, session.begin():
            verify(session, settings, token)

    with Session(engine) as session, session.begin():
        seed(session, settings)
        seed(session, settings)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(OrganisationDomain)) == 1
    token = request("student@university.test")
    with Session(engine) as session:
        stored = session.scalar(
            select(DevEmailVerification).where(
                DevEmailVerification.email == "student@university.test"
            )
        )
        assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert stored.token_hash != token
    redeem(token)
    with Session(engine) as session:
        user = session.scalar(
            select(User).where(
                User.identity_issuer == DEV_ISSUER, User.email == "student@university.test"
            )
        )
        assert user is not None and user.email_verified_at is not None
    with pytest.raises(VerificationError):
        redeem(token)
    with pytest.raises(VerificationError):
        request("student@university.test")  # persistent one-minute cooldown

    expired = request("expired@university.test")
    with Session(engine) as session, session.begin():
        challenge = session.scalar(
            select(DevEmailVerification).where(
                DevEmailVerification.email == "expired@university.test"
            )
        )
        challenge.requested_at = datetime.now(UTC) - timedelta(minutes=30)
        challenge.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    with pytest.raises(VerificationError):
        redeem(expired)
    replacement = request("expired@university.test")
    with pytest.raises(VerificationError):
        redeem(expired)
    redeem(replacement)

    before = len(sent)
    for address in ["student@unknown.test", "student@gmail.com", "student@sub.university.test"]:
        with pytest.raises(VerificationError):
            request(address)
    assert len(sent) == before

    race_token = request("concurrent@university.test")

    def race():
        try:
            redeem(race_token)
            return "verified"
        except VerificationError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: race(), range(2))) == ["rejected", "verified"]

    revoked_token = request("revoked@university.test")
    with Session(engine) as session, session.begin():
        domain = session.scalar(
            select(OrganisationDomain).where(OrganisationDomain.domain_ascii == TEST_DOMAIN)
        )
        domain.revoked_at = datetime.now(UTC)
    with pytest.raises(VerificationError):
        redeem(revoked_token)
    with Session(engine) as session, session.begin():
        domain = session.scalar(
            select(OrganisationDomain).where(OrganisationDomain.domain_ascii == TEST_DOMAIN)
        )
        domain.revoked_at = None

    def fail_delivery(*args):
        raise DeliveryError("synthetic SMTP failure")

    monkeypatch.setattr("app.dev_email.send_verification", fail_delivery)
    with pytest.raises(DeliveryError):
        request("delivery-failure@university.test")
    with Session(engine) as session:
        assert (
            session.scalar(
                select(DevEmailVerification).where(
                    DevEmailVerification.email == "delivery-failure@university.test"
                )
            )
            is None
        )
