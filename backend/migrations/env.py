from alembic import context

from app.config import Settings
from app.db import make_engine
from app.models import Base


def run() -> None:
    url = Settings().database_url.get_secret_value()
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = make_engine(url)
        try:
            with engine.connect() as connection:
                context.configure(connection=connection, target_metadata=Base.metadata)
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()


run()
