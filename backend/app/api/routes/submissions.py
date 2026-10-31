import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_user, origin_check, transaction
from app.db.models import Submission
from app.integrations.storage import LocalObjectStore
from app.schemas.submissions import (
    MAX_BYTES,
    RemovalBody,
    SubmissionPage,
    SubmissionRequest,
    SubmissionView,
)
from app.services import submissions
from app.services.auth import AuthError, throttle
from app.services.image_processing import process_image

router = APIRouter(prefix="/api/v1", tags=["Submissions"])


def enabled(request):
    if not request.app.state.settings.uploads_enabled:
        raise HTTPException(404, "Not found")


@router.post(
    "/projects/{project_id}/submissions",
    response_model=SubmissionView,
    status_code=201,
    operation_id="initiateSubmission",
)
def initiate(project_id: uuid.UUID, body: SubmissionRequest, request: Request):
    enabled(request)
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        return submissions.view(session, submissions.initiate(session, user, project_id, body))


@router.get("/submissions", response_model=SubmissionPage, operation_id="listMySubmissions")
def mine(
    request: Request, page: int = Query(1, ge=1, le=100000), page_size: int = Query(10, ge=1, le=50)
):
    enabled(request)
    with transaction(request) as session:
        user = get_user(session, request)
        q = select(Submission).where(
            Submission.contributor_id == user.id, Submission.workflow_version == 1
        )
        total = session.scalar(select(func.count()).select_from(q.subquery()))
        rows = session.scalars(
            q.order_by(Submission.created_at.desc(), Submission.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return SubmissionPage(
            items=[submissions.view(session, row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/submissions/{ident}", response_model=SubmissionView, operation_id="getSubmission")
def detail(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as session:
        return submissions.view(
            session, submissions.own_submission(session, get_user(session, request), ident)
        )


def prepare(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        allowed = throttle(session, f"image-upload:{user.id}", 40)
        if allowed:
            definition = submissions.upload_definition(session, user, ident)
    if not allowed:
        raise HTTPException(429, "Upload rate limit reached. Retry in a minute.")
    return definition


def complete(ident: uuid.UUID, request: Request, image):
    store = LocalObjectStore(request.app.state.settings.storage_root)
    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image.format]
    key = f"objects/{ident.hex}/{uuid.uuid4().hex}.{extension}"
    try:
        with transaction(request) as session:
            user = get_user(session, request, True)
            row = submissions.finish_image(session, user, ident, image, store, key)
            result = submissions.view(session, row)
        return result
    except BaseException as error:
        try:
            store.delete(key)
        except (OSError, ValueError):
            pass  # The orphan sweep will reclaim a failed write if storage recovers.
        if isinstance(error, (OSError, ValueError)):
            raise HTTPException(503, "Private storage unavailable. Retry this upload.") from None
        raise


@router.put(
    "/submissions/{ident}/image",
    response_model=SubmissionView,
    operation_id="uploadSubmissionImage",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload(ident: uuid.UUID, request: Request):
    definition = await run_in_threadpool(prepare, ident, request)
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > MAX_BYTES):
        raise HTTPException(413, "Image exceeds 10 MiB.")
    gate = request.app.state.upload_gate
    try:
        await asyncio.wait_for(gate.acquire(), timeout=1)
    except TimeoutError:
        raise HTTPException(429, "Upload service busy. Retry shortly.") from None
    try:
        data = bytearray()
        try:
            async with asyncio.timeout(30):
                async for chunk in request.stream():
                    if len(data) + len(chunk) > MAX_BYTES:
                        raise HTTPException(413, "Image exceeds 10 MiB.")
                    data.extend(chunk)
        except TimeoutError:
            raise HTTPException(408, "Upload timed out. Retry this image.") from None
        try:
            image = await run_in_threadpool(process_image, bytes(data), definition)
        except AuthError as error:
            raise HTTPException(error.status, str(error)) from None
        return await run_in_threadpool(complete, ident, request, image)
    finally:
        gate.release()


@router.get(
    "/submissions/{ident}/image",
    operation_id="getPrivateSubmissionImage",
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}}},
)
def image(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as session:
        row = submissions.own_submission(session, get_user(session, request), ident, True)
        if (
            row.status not in {"pending", "approved", "rejected"}
            or row.hidden_at
            or row.image_deleted_at
        ):
            raise HTTPException(404, "Image unavailable.")
        try:
            data = LocalObjectStore(request.app.state.settings.storage_root).read(row.object_key)
        except (OSError, ValueError):
            raise HTTPException(404, "Image unavailable.") from None
        mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[row.image_format]
        return Response(
            data,
            media_type=mime,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": f'inline; filename="{row.id}.image"',
            },
        )


@router.post(
    "/submissions/{ident}/removal-request",
    response_model=SubmissionView,
    operation_id="requestSubmissionRemoval",
)
def removal(ident: uuid.UUID, body: RemovalBody, request: Request):
    enabled(request)
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        return submissions.view(
            session, submissions.suppress(session, user, ident, body.reason, body.details)
        )


@router.post(
    "/submissions/{ident}/cancel", response_model=SubmissionView, operation_id="cancelUpload"
)
def cancel(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        row = submissions.own_submission(session, user, ident, True)
        if row.status != "uploading":
            raise HTTPException(409, "Completed submissions require a removal request.")
        if row.abandoned_at is None:
            row.abandoned_at = datetime.now(UTC)
        session.flush()
        return submissions.view(session, row)
