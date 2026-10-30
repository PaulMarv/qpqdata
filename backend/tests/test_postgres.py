"""Explicit opt-in; never run against a shared or valuable database."""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
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
            "TRUNCATE credit_ledger_entries",
        ]:
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(text(sql))
        with engine.connect() as connection:
            assert connection.execute(select(CreditLedgerEntry.amount)).scalar_one() == 5
        # Tables remain for inspection; use a fresh disposable database for each run.
    finally:
        engine.dispose()
