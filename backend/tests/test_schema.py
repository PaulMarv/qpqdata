from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base


def test_all_models_compile_for_postgres() -> None:
    assert len(Base.metadata.tables) == 9
    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_no_mutable_credit_balance_or_plaintext_password() -> None:
    columns = Base.metadata.tables["users"].columns
    assert "balance" not in columns
    assert "password" not in columns


def test_migration_matches_models() -> None:
    # Portable schema comparison; the PostgreSQL-only trigger is tested separately.
    import importlib.util
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location(
        "initial", Path("migrations/versions/0001_foundation.py")
    )
    assert spec and spec.loader
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            # SQLite intentionally cannot run PostgreSQL ledger triggers.
            original = revision.op.execute
            revision.op.execute = lambda *args, **kwargs: None
            try:
                revision.upgrade()
            finally:
                revision.op.execute = original
        assert compare_metadata(context, Base.metadata) == []
    engine.dispose()
