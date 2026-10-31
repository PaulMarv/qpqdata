import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.dev_email import deliver_message
from app.eligibility import domain_organisation, eligible, issuer_for
from app.models import AuthSession, AuthThrottle, CreditLedgerEntry, DevEmailVerification, User


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalise_email(value: str) -> str:
    try:
        parsed = validate_email(
            value, check_deliverability=False, test_environment=True, allow_smtputf8=False
        )
        return parsed.ascii_email.lower()
    except EmailNotValidError:
        raise AuthError("Use an approved school or work email address.", 400) from None


def throttle(session: Session, key: str, limit: int) -> bool:
    now = datetime.now(UTC)
    session.execute(
        insert(AuthThrottle)
        .values(key_hash=digest(key), window_start=now, attempts=0)
        .on_conflict_do_nothing(index_elements=["key_hash"])
    )
    row = session.get(AuthThrottle, digest(key), with_for_update=True)
    assert row is not None
    if row.window_start < now - timedelta(minutes=15):
        row.window_start = now
        row.attempts = 0
    row.attempts += 1
    return row.attempts <= limit


def send_link(settings: Settings, email: str, token: str) -> None:
    link = settings.frontend_url.rstrip("/") + "/verify-email#token=" + token
    message = EmailMessage()
    message["From"] = settings.email_sender
    message["To"] = email
    message["Subject"] = "Your QPQData sign-in link"
    message.set_content(
        "Confirm your email to sign in to QPQData. This single-use link expires in "
        + "600"
        + " seconds:\n\n"
        + link
    )
    message.add_alternative(
        '<p>Confirm your email to sign in to QPQData.</p><p><a href="'
        + link
        + '">Continue to QPQData</a></p><p>This link expires and can be used once.</p>',
        subtype="html",
    )
    deliver_message(settings, message)


def request_link(
    session: Session, settings: Settings, email: str, intent: str, name: str, browser_key: str
) -> None:
    email = normalise_email(email)
    domain = email.rsplit("@", 1)[-1]
    if not domain_organisation(session, settings, domain):
        return  # generic response; no challenge for ineligible organisations
    # Deliver the same challenge to eligible domains regardless of whether an
    # account exists. Redemption still requires a verified existing account for
    # login; this avoids an SMTP/no-SMTP account-existence timing discrepancy.
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    new_id = session.scalar(
        insert(DevEmailVerification)
        .values(
            email=email,
            token_hash=digest(token),
            requested_at=now,
            expires_at=now + timedelta(seconds=600),
            intent=intent,
            identity_issuer=issuer_for(domain),
            display_name=name.strip(),
            browser_hash=digest(browser_key),
        )
        .on_conflict_do_nothing(index_elements=["email"])
        .returning(DevEmailVerification.id)
    )
    challenge = session.scalar(
        select(DevEmailVerification).where(DevEmailVerification.email == email).with_for_update()
    )
    assert challenge is not None
    if new_id is None:
        if challenge.requested_at > now - timedelta(minutes=1):
            return
        challenge.token_hash = digest(token)
        challenge.requested_at = now
        challenge.expires_at = now + timedelta(seconds=600)
        challenge.consumed_at = None
        challenge.intent = intent
        challenge.identity_issuer = issuer_for(domain)
        challenge.display_name = name.strip()
        challenge.browser_hash = digest(browser_key)
    session.flush()
    send_link(settings, email, token)


def grant_welcome(session: Session, user: User, settings: Settings) -> None:
    session.get(User, user.id, with_for_update=True)
    if not eligible(session, settings, user):
        raise AuthError("Account eligibility unavailable.", 403)
    key = f"welcome:v1:{user.id}"
    session.execute(
        insert(CreditLedgerEntry)
        .values(user_id=user.id, amount=50, reason="welcome_grant", idempotency_key=key)
        .on_conflict_do_nothing()
    )
    row = session.scalar(select(CreditLedgerEntry).where(CreditLedgerEntry.idempotency_key == key))
    if row is None or row.user_id != user.id or row.amount != 50 or row.reason != "welcome_grant":
        raise AuthError("Account activation unavailable.", 503)


def revoke(session: Session, token: str | None) -> None:
    if token:
        record = session.scalar(
            select(AuthSession).where(AuthSession.token_hash == digest(token)).with_for_update()
        )
        if record:
            record.revoked_at = datetime.now(UTC)


def complete(
    session: Session,
    settings: Settings,
    token: str,
    previous_token: str | None,
    browser_key: str | None,
) -> tuple[User, str | None, str | None]:
    if len(token) != 43:
        raise AuthError("Link invalid or expired. Request a new link.", 400)
    challenge = session.scalar(
        select(DevEmailVerification)
        .where(DevEmailVerification.token_hash == digest(token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if (
        not challenge
        or challenge.consumed_at
        or challenge.expires_at <= now
        or challenge.intent not in {"login", "signup"}
        or not browser_key
        or not challenge.browser_hash
        or not hmac.compare_digest(challenge.browser_hash, digest(browser_key))
    ):
        raise AuthError("Link invalid or expired. Request a new link.", 400)
    domain = challenge.email.rsplit("@", 1)[-1]
    if not domain_organisation(
        session, settings, domain
    ) or challenge.identity_issuer != issuer_for(domain):
        raise AuthError("Organisation approval unavailable.", 403)
    revoke(session, previous_token)
    user = session.scalar(
        select(User)
        .where(
            User.identity_issuer == challenge.identity_issuer,
            User.identity_subject == challenge.email,
        )
        .with_for_update()
    )
    if user is None:
        if challenge.intent != "signup":
            raise AuthError("Link invalid or expired. Request a new link.", 400)
        user = User(
            email=challenge.email,
            identity_issuer=challenge.identity_issuer,
            identity_subject=challenge.email,
            display_name=challenge.display_name,
            email_verified_at=now,
        )
        session.add(user)
        session.flush()
    if user.disabled_at:
        raise AuthError("Account unavailable.", 403)
    if challenge.intent == "login" and not user.email_verified_at:
        raise AuthError("Link invalid or expired. Request a new link.", 400)
    user.email_verified_at = now
    challenge.consumed_at = now
    challenge.user_id = user.id
    if not eligible(session, settings, user):
        return user, None, None  # email proof committed; membership review still required
    grant_welcome(session, user, settings)
    raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=digest(raw),
            csrf_hash=digest(csrf),
            expires_at=now + timedelta(seconds=settings.session_seconds),
            last_seen_at=now,
        )
    )
    return user, raw, csrf


def authenticate(
    session: Session,
    settings: Settings,
    token: str | None,
    csrf: str | None = None,
    mutation: bool = False,
    check_eligibility: bool = True,
) -> User:
    record = (
        None
        if not token or len(token) != 43
        else session.scalar(
            select(AuthSession).where(AuthSession.token_hash == digest(token)).with_for_update()
        )
    )
    now = datetime.now(UTC)
    if (
        record is None
        or record.revoked_at
        or record.expires_at <= now
        or record.last_seen_at + timedelta(seconds=settings.session_idle_seconds) <= now
    ):
        raise AuthError("Log in to continue.")
    if mutation and (not csrf or not hmac.compare_digest(record.csrf_hash, digest(csrf))):
        raise AuthError("Request rejected.", 403)
    user = session.get(User, record.user_id, with_for_update=True)
    if user is None or (check_eligibility and not eligible(session, settings, user)):
        raise AuthError("Account eligibility unavailable.", 403)
    record.last_seen_at = now
    return user


def balance(session: Session, user: User) -> int:
    return session.scalar(
        select(func.coalesce(func.sum(CreditLedgerEntry.amount), 0)).where(
            CreditLedgerEntry.user_id == user.id
        )
    )
