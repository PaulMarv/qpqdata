import asyncio
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_user, origin_check, transaction
from app.db.models import (
    DatasetBuild,
    DatasetConsent,
    DatasetMember,
    DatasetPublication,
    DatasetReport,
    DatasetVersion,
    Submission,
)
from app.integrations.exports import ExportStore
from app.schemas.datasets import (
    AuthoriseImageRequest,
    ConsentView,
    DatasetPage,
    DatasetReportRequest,
    DatasetReportView,
    DatasetView,
    ExportConsentRequest,
    ExportReview,
    PublicationRequest,
    VersionView,
)
from app.services import dataset_exports, datasets
from app.services.auth import AuthError, throttle

router = APIRouter(prefix="/api/v1", tags=["Datasets"])


def enabled(request: Request) -> None:
    if not request.app.state.settings.datasets_enabled:
        raise HTTPException(404, "Not found")


def rate(request: Request, scope: str, limit: int) -> None:
    enabled(request)
    peer = request.client.host if request.client else "unknown"
    with transaction(request) as s:
        allowed = throttle(s, f"dataset:{scope}:{peer}", limit)
    if not allowed:
        raise HTTPException(429, "Dataset request limit reached. Try again later.")


@router.get("/datasets", response_model=DatasetPage, operation_id="listDatasets")
def library(
    request: Request,
    q: str = Query("", max_length=200),
    category: str | None = None,
    licence: str | None = None,
    sort: Literal["updated", "newest", "relevance"] = "updated",
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(12, ge=1, le=50),
):
    rate(request, "browse", 300)
    with transaction(request) as s:
        return datasets.discover(s, q, category, licence, sort, page, page_size)


@router.get("/datasets/{ident}", response_model=DatasetView, operation_id="getDataset")
def detail(ident: uuid.UUID, request: Request):
    rate(request, "browse", 300)
    with transaction(request) as s:
        return datasets.view(s, datasets.publication(s, ident))


@router.post(
    "/projects/{project_id}/dataset", response_model=DatasetView, operation_id="publishDataset"
)
def publish(project_id: uuid.UUID, body: PublicationRequest, request: Request):
    enabled(request)
    with transaction(request) as s:
        origin_check(request)
        user = get_user(s, request, True)
        return datasets.view(s, datasets.publish(s, user, project_id, body))


@router.get(
    "/projects/{project_id}/dataset",
    response_model=DatasetView | None,
    operation_id="getCollectionDataset",
)
def for_project(project_id: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as s:
        from app.db.models import Project

        user = get_user(s, request)
        p = s.get(Project, project_id)
        if not p or p.owner_id != user.id:
            raise AuthError("Collection not found.", 404)
        pub = s.scalar(
            select(DatasetPublication).where(
                DatasetPublication.project_id == project_id,
                DatasetPublication.withdrawn_at.is_(None),
            )
        )
        return datasets.view(s, pub) if pub else None


@router.post("/datasets/{ident}/withdraw", status_code=204, operation_id="withdrawDataset")
def withdraw(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as s:
        origin_check(request)
        user = get_user(s, request, True)
        pub = datasets.publication(s, ident)
        datasets.owner(s, user, pub)
        pub.withdrawn_at = datetime.now(UTC)
    return Response(status_code=204)


@router.get(
    "/submissions/{ident}/export-consent",
    response_model=ConsentView,
    operation_id="getExportConsent",
)
def get_consent(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as s:
        from app.services.submissions import own_submission

        return datasets.consent_view(s, own_submission(s, get_user(s, request), ident))


@router.post(
    "/submissions/{ident}/export-consent",
    response_model=ConsentView,
    operation_id="giveExportConsent",
)
def consent(ident: uuid.UUID, body: ExportConsentRequest, request: Request):
    enabled(request)
    with transaction(request) as s:
        origin_check(request)
        return datasets.consent(s, get_user(s, request, True), ident, body)


@router.post(
    "/submissions/{ident}/withdraw-export",
    response_model=ConsentView,
    operation_id="withdrawExportConsent",
)
def withdraw_consent(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as s:
        origin_check(request)
        return datasets.withdraw_consent(s, get_user(s, request, True), ident)


@router.get(
    "/datasets/{ident}/review",
    response_model=list[ExportReview],
    operation_id="reviewDatasetImages",
)
def review(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as s:
        return datasets.review(s, get_user(s, request), ident)


@router.post(
    "/datasets/{ident}/images/{submission_id}/authorise",
    status_code=204,
    operation_id="authoriseDatasetImage",
)
def authorise(
    ident: uuid.UUID, submission_id: uuid.UUID, body: AuthoriseImageRequest, request: Request
):
    enabled(request)
    with transaction(request) as s:
        origin_check(request)
        datasets.authorise(s, get_user(s, request, True), ident, submission_id, body)
    return Response(status_code=204)


@router.post(
    "/datasets/{ident}/versions", response_model=VersionView, operation_id="createDatasetVersion"
)
def snapshot(ident: uuid.UUID, request: Request):
    rate(request, "snapshot", 20)
    with transaction(request) as s:
        origin_check(request)
        user = get_user(s, request, True)
        pub = datasets.publication(s, ident)
        datasets.owner(s, user, pub)
        return datasets.version_view(s, datasets.snapshot(s, pub))


def version(s, ident, number):
    datasets.publication(s, ident)
    v = s.scalar(
        select(DatasetVersion).where(
            DatasetVersion.publication_id == ident, DatasetVersion.version == number
        )
    )
    if not v:
        raise AuthError("Version not found.", 404)
    return v


@router.post(
    "/datasets/{ident}/versions/{number}/prepare",
    response_model=VersionView,
    operation_id="prepareDatasetDownload",
)
def prepare(ident: uuid.UUID, number: int, request: Request):
    rate(request, "prepare", 20)
    origin_check(request)
    with transaction(request) as s:
        v = version(s, ident, number)
        dataset_exports.prepare(s, v, request.app.state.settings.export_root)
        return datasets.version_view(s, v)


def download_info(request, ident, number):
    rate(request, "download", 30)
    with transaction(request) as s:
        v = version(s, ident, number)
        if not datasets.valid_version(s, v):
            raise AuthError("Dataset version revoked.", 410)
        b = s.scalar(select(DatasetBuild).where(DatasetBuild.version_id == v.id))
        if (
            b.state != "ready"
            or not b.expires_at
            or b.expires_at <= datetime.now(UTC)
            or not b.artifact_key
        ):
            raise AuthError("ZIP expired or not ready. Prepare this version again.", 410)
        try:
            stream = ExportStore(request.app.state.settings.export_root).open(b.artifact_key)
        except (OSError, ValueError):
            raise AuthError("ZIP unavailable. Prepare it again.", 410) from None
        return v.id, b.expires_at, b.byte_size, stream


@router.get(
    "/datasets/{ident}/versions/{number}/download",
    operation_id="downloadDataset",
    responses={
        200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def download(ident: uuid.UUID, number: int, request: Request):
    enabled(request)
    gate = request.app.state.download_gate
    try:
        await asyncio.wait_for(gate.acquire(), 1)
    except TimeoutError:
        raise HTTPException(429, "Download service busy.") from None
    try:
        v_id, expires, size, stream = await run_in_threadpool(download_info, request, ident, number)
    except BaseException:
        gate.release()
        raise

    closed = False

    async def close():
        nonlocal closed
        if not closed:
            closed = True
            stream.close()
            gate.release()

    async def chunks():
        try:
            while datetime.now(UTC) < expires:
                if not await run_in_threadpool(
                    dataset_exports.check, request.app.state.engine, v_id
                ):
                    return
                data = await run_in_threadpool(stream.read, dataset_exports.CHUNK)
                if not data:
                    return
                yield data
        finally:
            await close()

    return StreamingResponse(
        chunks(),
        background=BackgroundTask(close),
        media_type="application/zip",
        headers={
            "Content-Length": str(size),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="qpqdata-{ident}-v{number}.zip"',
        },
    )


@router.post("/datasets/{ident}/reports", status_code=202, operation_id="reportDataset")
def report(ident: uuid.UUID, body: DatasetReportRequest, request: Request):
    rate(request, "report", 10)
    origin_check(request)
    with transaction(request) as s:
        datasets.publication(s, ident)
        if body.image_id and not s.scalar(
            select(DatasetMember.id)
            .join(DatasetVersion, DatasetVersion.id == DatasetMember.version_id)
            .where(DatasetVersion.publication_id == ident, DatasetMember.image_id == body.image_id)
        ):
            raise AuthError("Image not found.", 404)
        s.add(DatasetReport(publication_id=ident, **body.model_dump()))
    return {
        "message": (
            "Report recorded for owner review. For immediate safety, stop using the affected image."
        )
    }


@router.get(
    "/datasets/{ident}/reports",
    response_model=list[DatasetReportView],
    operation_id="listDatasetReports",
)
def reports(ident: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as s:
        pub = datasets.publication(s, ident)
        datasets.owner(s, get_user(s, request), pub)
        rows = s.scalars(
            select(DatasetReport)
            .where(DatasetReport.publication_id == ident)
            .order_by(DatasetReport.created_at.desc())
            .limit(100)
        ).all()
        return [
            DatasetReportView(
                id=r.id,
                created_at=r.created_at,
                image_id=r.image_id,
                reason=r.reason,
                details=r.details,
                submission_id=s.scalar(
                    select(DatasetMember.submission_id)
                    .join(DatasetVersion, DatasetVersion.id == DatasetMember.version_id)
                    .where(
                        DatasetVersion.publication_id == ident, DatasetMember.image_id == r.image_id
                    )
                    .limit(1)
                )
                if r.image_id
                else None,
            )
            for r in rows
        ]


@router.post(
    "/datasets/{ident}/images/{submission_id}/withdraw",
    status_code=204,
    operation_id="withdrawDatasetImage",
)
def withdraw_image(ident: uuid.UUID, submission_id: uuid.UUID, request: Request):
    enabled(request)
    with transaction(request) as s:
        origin_check(request)
        pub = datasets.publication(s, ident)
        datasets.owner(s, get_user(s, request, True), pub)
        row = s.scalar(
            select(Submission)
            .where(Submission.id == submission_id, Submission.project_id == pub.project_id)
            .with_for_update()
        )
        if not row:
            raise AuthError("Image not found.", 404)
        grant = s.scalar(
            select(DatasetConsent).where(DatasetConsent.submission_id == row.id).with_for_update()
        )
        if grant and not grant.withdrawn_at:
            grant.withdrawn_at = datetime.now(UTC)
    return Response(status_code=204)
