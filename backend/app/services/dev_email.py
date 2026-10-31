"""Local mailbox-verification harness; no authentication or eligibility grant."""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import DevEmailVerification, OrganisationDomain, User
from app.integrations.email import deliver_message
from app.services.dev_seed import FIXTURE_REFERENCE, TEST_DOMAIN, require_development

DEV_ISSUER = "urn:qpqdata:development-email"


class VerificationError(Exception):
    pass


def normalise_address(value: str) -> str:
    # Deliberately bounded ASCII fixture syntax, not a production email parser.
    address = value.strip().lower()
    if len(address) > 254 or address.count("@") != 1:
        raise VerificationError("Use an approved development organisation address.")
    local, domain = address.split("@")
    if (
        not re.fullmatch(r"[a-z0-9!#$%&'*+/=?^_`{|}~.-]{1,64}", local)
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or domain != TEST_DOMAIN
    ):
        raise VerificationError("Use an approved development organisation address.")
    return address


def approved_domain(session: Session, settings: Settings) -> bool:
    require_development(settings)
    # A fixture marker is never sufficient without the explicit environment gate.
    return (
        session.scalar(
            select(OrganisationDomain.id).where(
                OrganisationDomain.domain_ascii == TEST_DOMAIN,
                OrganisationDomain.review_reference == FIXTURE_REFERENCE,
                OrganisationDomain.revoked_at.is_(None),
            )
        )
        is not None
    )


def send_verification(settings: Settings, email: str, token: str) -> None:
    require_development(settings)
    message = EmailMessage()
    message["From"] = "QPQData Development <noreply@qpqdata.test>"
    message["To"] = email
    message["Subject"] = "Verify your QPQData development email"
    # A fragment avoids putting the bearer token in HTTP request URLs or access logs.
    link = settings.frontend_url.rstrip("/") + "/dev-email/verify#token=" + token
    message.set_content(
        "Development only. Confirm control of your test mailbox using this link:\n\n"
        + link
        + "\n\nThis link is single-use and expires in "
        + str(settings.verification_ttl_seconds)
        + " seconds. "
        + "It does not grant production eligibility or create a login session.\n"
    )
    message.add_alternative(
        "<p>Development only. Confirm your test mailbox:</p>"
        + '<p><a href="'
        + link
        + '">Verify development email</a></p>'
        + "<p>This link expires and can be used once. "
        + "No login session or production eligibility is granted.</p>",
        subtype="html",
    )
    deliver_message(settings, message)


def register(session: Session, settings: Settings, email: str) -> None:
    require_development(settings)
    email = normalise_address(email)
    if not approved_domain(session, settings):
        raise VerificationError("Use an approved development organisation address.")
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    # ON CONFLICT and row locking also serialise concurrent requests for one mailbox.
    new_id = session.scalar(
        insert(DevEmailVerification)
        .values(
            email=email,
            token_hash=digest,
            requested_at=now,
            expires_at=now + timedelta(seconds=settings.verification_ttl_seconds),
        )
        .on_conflict_do_nothing(index_elements=["email"])
        .returning(DevEmailVerification.id)
    )
    challenge = session.scalar(
        select(DevEmailVerification).where(DevEmailVerification.email == email).with_for_update()
    )
    assert challenge is not None
    if new_id is None:
        if now < challenge.requested_at + timedelta(seconds=60):
            raise VerificationError("Please wait one minute before requesting another email.")
        challenge.token_hash = digest
        challenge.requested_at = now
        challenge.expires_at = now + timedelta(seconds=settings.verification_ttl_seconds)
        challenge.consumed_at = None
        challenge.intent = "verify"
        challenge.identity_issuer = DEV_ISSUER
    session.flush()
    send_verification(settings, email, token)
    # The caller commits. SMTP failure rolls back the challenge. A commit failure
    # can leave an unusable email in Mailpit; no valid challenge is published.


def verify(session: Session, settings: Settings, token: str) -> None:
    require_development(settings)
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise VerificationError("Link invalid or expired. Request a new verification email.")
    digest = hashlib.sha256(token.encode()).hexdigest()
    challenge = session.scalar(
        select(DevEmailVerification)
        .where(DevEmailVerification.token_hash == digest)
        .with_for_update()
    )
    now = datetime.now(UTC)
    if (
        challenge is None
        or challenge.intent != "verify"
        or challenge.identity_issuer != DEV_ISSUER
        or challenge.consumed_at is not None
        or challenge.expires_at <= now
        or not approved_domain(session, settings)
    ):
        raise VerificationError("Link invalid or expired. Request a new verification email.")
    user = session.scalar(
        select(User)
        .where(User.identity_issuer == DEV_ISSUER, User.identity_subject == challenge.email)
        .with_for_update()
    )
    if user is None:
        user = User(
            identity_issuer=DEV_ISSUER,
            identity_subject=challenge.email,
            email=challenge.email,
            email_verified_at=now,
        )
        session.add(user)
        session.flush()
    else:
        user.email_verified_at = now
    challenge.user_id = user.id
    challenge.consumed_at = now

    if settings.auth_enabled:
        from app.services.auth import grant_welcome
        from app.services.eligibility import eligible

        if eligible(session, settings, user):
            grant_welcome(session, user, settings)
