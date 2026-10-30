from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def make_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_timeout=5,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )


def session_for(engine: Engine) -> Session:
    # Callers own transaction boundaries; no automatic commits.
    return Session(engine)
