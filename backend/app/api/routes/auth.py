import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import cookie_names, get_user, origin_check, transaction
from app.db.models import Project, ProjectReservation, User
from app.schemas.auth import (
    LinkRequest,
    Message,
    Profile,
    ProfileUpdate,
    TokenRequest,
    VerificationResult,
)
from app.services import auth

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def profile(session: Session, user: User) -> Profile:
    return Profile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        credit_balance=auth.balance(session, user),
        reserved_credits=session.scalar(
            select(func.coalesce(func.sum(ProjectReservation.amount), 0))
            .join(Project, Project.id == ProjectReservation.project_id)
            .where(Project.owner_id == user.id, ProjectReservation.release_entry_id.is_(None))
        ),
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
