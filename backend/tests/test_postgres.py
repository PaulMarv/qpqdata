"""Explicit opt-in; never run against a shared or valuable database."""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.models import Base, CreditLedgerEntry, User
from app.db.session import make_engine


@pytest.mark.postgres
def test_migration_and_ledger_guards(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable empty PostgreSQL database")
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.dialect.name == "postgresql"
            assert inspect(connection).get_table_names() == [], "Test database must be empty"
        monkeypatch.setenv("QPQ_DATABASE_URL", url)
        config = Config(str(Path("alembic.ini")))
        command.upgrade(config, "0004")
        # Exercise additive migration over real legacy rows, not just an empty schema.
        legacy_user, legacy_project, legacy_submission = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id,identity_issuer,identity_subject,email) "
                    "VALUES (:id,'synthetic:legacy','legacy','legacy@example.test')"
                ),
                {"id": legacy_user},
            )
            connection.execute(
                text(
                    "INSERT INTO projects (id,owner_id,name,description) "
                    "VALUES (:id,:owner,'Legacy draft','Original description')"
                ),
                {"id": legacy_project, "owner": legacy_user},
            )
            connection.execute(
                text(
                    "INSERT INTO submissions "
                    "(id,project_id,contributor_id,object_key,metadata_values) "
                    "VALUES (:id,:project,:user,'legacy/private-reference','{\"original\": true}')"
                ),
                {"id": legacy_submission, "project": legacy_project, "user": legacy_user},
            )
            before = dict(
                connection.execute(
                    text("SELECT * FROM submissions WHERE id=:id"), {"id": legacy_submission}
                )
                .mappings()
                .one()
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            after = (
                connection.execute(
                    text("SELECT * FROM submissions WHERE id=:id"), {"id": legacy_submission}
                )
                .mappings()
                .one()
            )
            assert all(after[key] == value for key, value in before.items())
            assert after["workflow_version"] is None and after["criteria_version"] is None
        with engine.connect() as connection:
            assert set(Base.metadata.tables) <= set(inspect(connection).get_table_names())
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        with Session(engine) as session, session.begin():
            user = User(
                identity_issuer="https://issuer.example",
                identity_subject="synthetic",
                email="synthetic@example.test",
            )
            session.add(user)
            session.flush()
            session.add(
                CreditLedgerEntry(
                    user_id=user.id,
                    amount=5,
                    reason="synthetic test",
                    idempotency_key=str(uuid.uuid4()),
                )
            )
        for sql in [
            "UPDATE credit_ledger_entries SET amount = 10",
            "DELETE FROM credit_ledger_entries",
            "TRUNCATE credit_ledger_entries, project_reservations, "
            "moderation_decisions, notification_outbox",
        ]:
            with pytest.raises(DBAPIError) as rejected, engine.begin() as connection:
                connection.execute(text(sql))
            assert rejected.value.orig.sqlstate == "P0001"
        with engine.connect() as connection:
            assert connection.execute(select(CreditLedgerEntry.amount)).scalar_one() == 5
        with engine.connect() as connection:
            original = connection.execute(select(CreditLedgerEntry.__table__)).mappings().one()

        def reject_entry(expected_state: str, **overrides: object) -> None:
            values = {
                "id": uuid.uuid4(),
                "user_id": original["user_id"],
                "amount": 1,
                "reason": "synthetic constraint test",
                "idempotency_key": str(uuid.uuid4()),
            }
            values.update(overrides)
            with pytest.raises(DBAPIError) as rejected, engine.begin() as connection:
                connection.execute(CreditLedgerEntry.__table__.insert().values(**values))
            assert rejected.value.orig.sqlstate == expected_state

        reject_entry("23514", amount=0)
        reject_entry("23505", idempotency_key=original["idempotency_key"])
        reject_entry("23503", user_id=uuid.uuid4())
        reject_entry("23503", reversal_of_id=uuid.uuid4())
        self_reference = uuid.uuid4()
        reject_entry("23514", id=self_reference, reversal_of_id=self_reference)
        with engine.begin() as connection:
            connection.execute(
                CreditLedgerEntry.__table__.insert().values(
                    user_id=original["user_id"],
                    amount=-5,
                    reason="synthetic compensation",
                    idempotency_key=str(uuid.uuid4()),
                    reversal_of_id=original["id"],
                )
            )
        reject_entry("23505", reversal_of_id=original["id"])
        with engine.connect() as connection:
            assert (
                connection.execute(select(func.count()).select_from(CreditLedgerEntry)).scalar()
                == 2
            )
            assert connection.execute(select(func.sum(CreditLedgerEntry.amount))).scalar() == 0
            assert (
                connection.execute(
                    select(CreditLedgerEntry.amount).where(CreditLedgerEntry.id == original["id"])
                ).scalar_one()
                == 5
            )
        from tests.dev_email_cases import exercise_verification

        exercise_verification(engine, monkeypatch)
        from tests.auth_cases import exercise_authentication

        exercise_authentication(engine, monkeypatch)
        from tests.project_cases import exercise_projects

        exercise_projects(engine, monkeypatch)
        from tests.submission_cases import exercise_submissions

        exercise_submissions(engine, monkeypatch, tmp_path)
        from tests.moderation_cases import exercise_moderation

        exercise_moderation(engine, monkeypatch, tmp_path / "moderation")
        from tests.dataset_cases import exercise_datasets

        exercise_datasets(engine, monkeypatch, tmp_path / "datasets")
        # Tables remain for inspection; use a fresh disposable database for each run.
    finally:
        engine.dispose()
