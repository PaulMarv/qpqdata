from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.email import DeliveryError
from app.schemas.dev_email import MessageResponse, RegisterRequest, VerifyRequest
from app.services.auth import AuthError
from app.services.dev_email import VerificationError, register, verify

router = APIRouter(prefix="/api/v1/dev-email", tags=["Development email only"])


def execute(request: Request, action: Callable[[Session, Settings, str], None], value: str) -> None:
    settings = getattr(request.app.state, "settings", None)
    if not settings or settings.environment != "development" or not settings.dev_email_enabled:
        raise HTTPException(404, "Not found")
    try:
        with Session(request.app.state.engine) as session, session.begin():
            action(session, settings, value)
    except VerificationError as error:
        raise HTTPException(400, str(error)) from None
    except (DeliveryError, SQLAlchemyError, AuthError):
        # Never expose database statements, parameters, addresses or SMTP messages.
        raise HTTPException(503, "Development verification unavailable. Try again later.") from None


@router.post("/register", response_model=MessageResponse, operation_id="registerDevelopmentEmail")
def register_email(body: RegisterRequest, request: Request) -> MessageResponse:
    execute(request, register, body.email)
    return MessageResponse(message="Check Mailpit for your verification email.")


@router.post("/verify", response_model=MessageResponse, operation_id="verifyDevelopmentEmail")
def verify_email(body: VerifyRequest, request: Request) -> MessageResponse:
    execute(request, verify, body.token.get_secret_value())
    return MessageResponse(
        message="Development account activated. Email verified; no login session created."
    )
