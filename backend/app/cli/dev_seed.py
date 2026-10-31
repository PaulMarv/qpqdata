"""Explicit development fixture command; never runs at import time."""

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import make_engine
from app.services.dev_seed import require_development, seed


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
