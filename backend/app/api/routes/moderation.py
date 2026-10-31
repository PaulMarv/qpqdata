from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.api.dependencies import get_user, origin_check, transaction
from app.api.routes.submissions import enabled
from app.integrations.storage import LocalObjectStore
from app.schemas.moderation import DecisionRequest, ModeratorRequest, ReviewPage, WalletView
from app.schemas.submissions import RemovalBody, SubmissionView
from app.services import moderation, submissions, wallet
from app.services.auth import AuthError

router = APIRouter(prefix="/api/v1", tags=["Moderation"])


@router.get("/moderation", response_model=ReviewPage, operation_id="listReviews")
def reviews(
    request: Request,
    project_id: UUID | None = None,
    status: Literal["pending", "approved", "rejected"] | None = None,
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(10, ge=1, le=50),
):
    enabled(request)
    with transaction(request) as session:
        return moderation.dashboard(
            session, get_user(session, request), project_id, status, page, page_size
        )


@router.post(
    "/moderation/{ident}/decision", response_model=SubmissionView, operation_id="decideSubmission"
)
def decision(ident: UUID, body: DecisionRequest, request: Request):
    enabled(request)
    with transaction(request) as session:
        origin_check(request)
        row = moderation.decide(
            session,
            get_user(session, request, True),
            ident,
            body,
            LocalObjectStore(request.app.state.settings.storage_root),
        )
        return submissions.view(session, row)


@router.get(
    "/moderation/{ident}/image",
    operation_id="getReviewImage",
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}}},
)
def image(ident: UUID, request: Request):
    enabled(request)
    with transaction(request) as session:
        row = moderation.review_row(session, get_user(session, request), ident)
        if (
            row.hidden_at
            or row.image_deleted_at
            or row.status not in {"pending", "approved", "rejected"}
        ):
            raise AuthError("Image unavailable.", 404)
        try:
            data = LocalObjectStore(request.app.state.settings.storage_root).read(row.object_key)
        except (OSError, ValueError):
            raise AuthError("Image unavailable.", 404) from None
        return Response(
            data,
            media_type={"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[
                row.image_format
            ],
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )


@router.post(
    "/projects/{project_id}/moderators", status_code=204, operation_id="setProjectModerator"
)
def designate(project_id: UUID, body: ModeratorRequest, request: Request):
    enabled(request)
    with transaction(request) as session:
        origin_check(request)
        moderation.designate(
            session, get_user(session, request, True), project_id, body.user_id, body.active
        )
    return Response(status_code=204)


@router.get("/wallet", response_model=WalletView, operation_id="getWallet")
def history(
    request: Request, page: int = Query(1, ge=1, le=100000), page_size: int = Query(20, ge=1, le=50)
):
    with transaction(request) as session:
        return wallet.history(session, get_user(session, request), page, page_size)


@router.post(
    "/moderation/{ident}/removal-request",
    response_model=SubmissionView,
    operation_id="restrictReviewImage",
)
def restrict(ident: UUID, body: RemovalBody, request: Request):
    enabled(request)
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        row = moderation.review_row(session, user, ident, True)
        return submissions.view(
            session, submissions.suppress_row(session, user, row, body.reason, body.details)
        )
