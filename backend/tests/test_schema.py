from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base


def test_all_models_compile_for_postgres() -> None:
    assert len(Base.metadata.tables) == 15
    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_no_mutable_credit_balance_or_plaintext_password() -> None:
    columns = Base.metadata.tables["users"].columns
    assert "balance" not in columns
    assert "password" not in columns


def test_migrations_render_postgres_guards(monkeypatch) -> None:
    import io

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    output = io.StringIO()
    config = Config("alembic.ini", output_buffer=output)
    assert ScriptDirectory.from_config(config).get_heads() == ["0005"]
    monkeypatch.setenv("QPQ_DATABASE_URL", "postgresql+psycopg://offline:offline@localhost/offline")
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    for guard in [
        "ledger_no_update_delete",
        "ledger_no_truncate",
        "ledger_wallet_lock",
        "project_funding_complete",
        "project_versions_immutable",
        "ledger_nonnegative",
    ]:
        assert guard in sql
