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

from app.db import make_engine
from app.models import Base, CreditLedgerEntry, User


@pytest.mark.postgres
def test_migration_and_ledger_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable empty PostgreSQL database")
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.dialect.name == "postgresql"
            assert inspect(connection).get_table_names() == [], "Test database must be empty"
        monkeypatch.setenv("QPQ_DATABASE_URL", url)
        command.upgrade(Config(str(Path("alembic.ini"))), "head")
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
            "TRUNCATE credit_ledger_entries, project_reservations",
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
        # Tables remain for inspection; use a fresh disposable database for each run.
    finally:
        engine.dispose()
