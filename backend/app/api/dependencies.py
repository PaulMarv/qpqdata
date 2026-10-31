from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import User
from app.integrations.email import DeliveryError
from app.services import auth


def cookie_names(request: Request) -> tuple[str, str]:
    local = request.app.state.settings.environment == "development"
    return ("qpq_session", "qpq_csrf") if local else ("__Host-qpq_session", "__Host-qpq_csrf")


def origin_check(request: Request) -> None:
    if request.headers.get("origin") != request.app.state.settings.frontend_url.rstrip("/"):
        raise HTTPException(403, "Request rejected.")


@contextmanager
def transaction(request: Request) -> Iterator[Session]:
    settings = getattr(request.app.state, "settings", None)
    if not settings or not settings.auth_enabled:
        raise HTTPException(404, "Not found")
    try:
        with Session(request.app.state.engine) as session, session.begin():
            yield session
    except auth.AuthError as error:
        raise HTTPException(error.status, str(error)) from None
    except (SQLAlchemyError, DeliveryError):
        raise HTTPException(503, "Account service unavailable. Try again later.") from None


def get_user(session: Session, request: Request, mutation: bool = False) -> User:
    name, _ = cookie_names(request)
    return auth.authenticate(
        session,
        request.app.state.settings,
        request.cookies.get(name),
        request.headers.get("x-csrf-token"),
        mutation,
    )
