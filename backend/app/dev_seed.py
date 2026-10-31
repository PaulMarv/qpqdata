"""Explicit, idempotent development fixture. No users or credits are seeded."""

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import make_engine
from app.models import Organisation, OrganisationDomain

TEST_DOMAIN = "university.test"
TEST_ORGANISATION = "QPQData Test University"
FIXTURE_REFERENCE = "development-fixture:university.test:v1"


def require_development(settings: Settings) -> None:
    if settings.environment != "development" or not settings.dev_email_enabled:
        raise ValueError("Development email fixture is disabled")


def seed(session: Session, settings: Settings) -> None:
    require_development(settings)
    # Serialise explicit seed invocations without changing an existing reviewed record.
    session.execute(text("SELECT pg_advisory_xact_lock(71591023)"))
    existing = session.scalar(
        select(OrganisationDomain).where(OrganisationDomain.domain_ascii == TEST_DOMAIN)
    )
    if existing:
        organisation = session.get(Organisation, existing.organisation_id)
        if (
            existing.review_reference != FIXTURE_REFERENCE
            or existing.revoked_at
            or not organisation
            or organisation.name != TEST_ORGANISATION
        ):
            raise ValueError("Conflicting development fixture; review required")
        return
    organisation = Organisation(name=TEST_ORGANISATION, kind="university")
    session.add(organisation)
    session.flush()
    session.add(
        OrganisationDomain(
            organisation_id=organisation.id,
            domain_ascii=TEST_DOMAIN,
            reviewed_at=datetime.now(UTC),
            review_reference=FIXTURE_REFERENCE,
        )
    )


def main() -> None:
    settings = Settings()
    require_development(settings)
    engine = make_engine(settings.database_url.get_secret_value())
    try:
        with Session(engine) as session, session.begin():
            seed(session, settings)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
