from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dev_email import DEV_ISSUER
from app.dev_seed import FIXTURE_REFERENCE
from app.models import Organisation, OrganisationDomain, OrganisationMembership, User

PERSONAL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "mail.com",
}
EMAIL_ISSUER = "urn:qpqdata:email"


def issuer_for(domain: str) -> str:
    return DEV_ISSUER if domain == "university.test" else EMAIL_ISSUER


def domain_organisation(
    session: Session, settings: Settings, domain: str, lock: bool = False
) -> OrganisationDomain | None:
    if domain in PERSONAL_DOMAINS:
        return None
    query = (
        select(OrganisationDomain)
        .join(Organisation)
        .where(
            OrganisationDomain.domain_ascii == domain,
            OrganisationDomain.revoked_at.is_(None),
            Organisation.kind.in_(["school", "university", "employer"]),
        )
    )
    record = session.scalar(query.with_for_update(of=OrganisationDomain) if lock else query)
    if not record:
        return None
    reserved = domain.split(".")[-1] in {"test", "invalid", "localhost", "example"}
    if reserved:
        if not (
            domain == "university.test"
            and settings.environment == "development"
            and settings.dev_email_enabled
            and record.review_reference == FIXTURE_REFERENCE
        ):
            return None
    elif record.review_reference.startswith("development-fixture:"):
        return None
    return record


def eligible(session: Session, settings: Settings, user: User) -> bool:
    if not user.email_verified_at or user.disabled_at:
        return False
    domain = user.email.rsplit("@", 1)[-1]
    record = domain_organisation(session, settings, domain, lock=True)
    if not record or user.identity_issuer != issuer_for(domain):
        return False
    if domain == "university.test":
        return True  # explicit local fixture, never a real affiliation claim
    return (
        session.scalar(
            select(OrganisationMembership.id)
            .where(
                OrganisationMembership.user_id == user.id,
                OrganisationMembership.organisation_id == record.organisation_id,
                OrganisationMembership.verified_at <= datetime.now(UTC),
                OrganisationMembership.expires_at > datetime.now(UTC),
                OrganisationMembership.revoked_at.is_(None),
            )
            .with_for_update()
        )
        is not None
    )
