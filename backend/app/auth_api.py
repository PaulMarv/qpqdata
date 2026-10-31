import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import auth
from app.dev_email import DeliveryError
from app.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: str = Field(max_length=254)
    intent: Literal["signup", "login"]
    display_name: str = Field(default="", max_length=100)


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    token: SecretStr = Field(max_length=100)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    display_name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")


class Message(BaseModel):
    message: str


class Profile(BaseModel):
    id: UUID
    email: str
    display_name: str
    credit_balance: int


class VerificationResult(BaseModel):
    status: Literal["authenticated", "pending_review"]


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


def profile(session: Session, user: User) -> Profile:
    return Profile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        credit_balance=auth.balance(session, user),
    )


@router.post("/request-link", response_model=Message, operation_id="requestAuthLink")
def request_link(body: LinkRequest, request: Request, response: Response) -> Message:
    with transaction(request) as session:
        origin_check(request)
        # Use actual peer identity, never caller-supplied X-Forwarded-For.
        peer = request.client.host if request.client else "unknown"
        allowed = auth.throttle(session, "link-peer:" + peer, 100)
        allowed = auth.throttle(session, "link-email:" + body.email.strip().lower(), 5) and allowed
    if not allowed:
        raise HTTPException(429, "Too many requests. Try again later.")
    prefix = "qpq" if request.app.state.settings.environment == "development" else "__Host-qpq"
    browser_key = request.cookies.get(prefix + "_login_nonce")
    if not browser_key or len(browser_key) != 43:
        browser_key = secrets.token_urlsafe(32)
    with transaction(request) as session:
        auth.request_link(
            session,
            request.app.state.settings,
            body.email,
            body.intent,
            body.display_name,
            browser_key,
        )
    prefix = "qpq" if request.app.state.settings.environment == "development" else "__Host-qpq"
    response.set_cookie(
        prefix + "_login_nonce",
        browser_key,
        httponly=True,
        path="/",
        samesite="lax",
        secure=request.app.state.settings.environment != "development",
        max_age=900,
    )
    return Message(
        message="If this account can continue, a sign-in link has been sent. Check your email."
    )


@router.post("/verify", response_model=VerificationResult, operation_id="verifyAuthLink")
def verify(body: TokenRequest, request: Request, response: Response) -> VerificationResult:
    with transaction(request) as session:
        origin_check(request)
        peer = request.client.host if request.client else "unknown"
        allowed = auth.throttle(session, "verify-peer:" + peer, 100)
    if not allowed:
        raise HTTPException(429, "Too many requests. Try again later.")
    with transaction(request) as session:
        name, csrf_name = cookie_names(request)
        user, token, csrf = auth.complete(
            session,
            request.app.state.settings,
            body.token.get_secret_value(),
            request.cookies.get(name),
            request.cookies.get(
                "qpq_login_nonce"
                if request.app.state.settings.environment == "development"
                else "__Host-qpq_login_nonce"
            ),
        )
    # Cookies are emitted only after the transaction (including the grant) commits.
    if token and csrf:
        settings = request.app.state.settings
        for key, value in [(name, token), (csrf_name, csrf)]:
            response.set_cookie(
                key,
                value,
                max_age=settings.session_seconds,
                httponly=True,
                secure=settings.environment != "development",
                samesite="lax",
                path="/",
            )
        return VerificationResult(status="authenticated")
    for key in (name, csrf_name):
        response.delete_cookie(
            key,
            path="/",
            httponly=True,
            secure=request.app.state.settings.environment != "development",
            samesite="lax",
        )
    return VerificationResult(status="pending_review")


@router.get("/me", response_model=Profile, operation_id="getCurrentUser")
def me(request: Request) -> Profile:
    with transaction(request) as session:
        return profile(session, get_user(session, request))


@router.patch("/profile", response_model=Profile, operation_id="updateProfile")
def update_profile(body: ProfileUpdate, request: Request) -> Profile:
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        user.display_name = body.display_name.strip()
        return profile(session, user)


@router.post("/logout", response_model=Message, operation_id="logout")
def logout(request: Request, response: Response) -> Message:
    with transaction(request) as session:
        origin_check(request)
        name, csrf_name = cookie_names(request)
        auth.authenticate(
            session,
            request.app.state.settings,
            request.cookies.get(name),
            request.headers.get("x-csrf-token"),
            True,
            check_eligibility=False,
        )
        auth.revoke(session, request.cookies.get(name))
    for key in (name, csrf_name):
        response.delete_cookie(
            key,
            path="/",
            httponly=True,
            secure=request.app.state.settings.environment != "development",
            samesite="lax",
        )
    return Message(message="Signed out.")
