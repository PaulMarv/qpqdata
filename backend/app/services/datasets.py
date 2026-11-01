"""Explicit public distribution and immutable image/label snapshots. No ledger access."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from PIL import __version__ as pillow_version
from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    DatasetBuild,
    DatasetConsent,
    DatasetMember,
    DatasetPublication,
    DatasetVersion,
    Project,
    ProjectVersion,
    RemovalRequest,
    Submission,
    User,
)
from app.schemas.datasets import (
    AuthoriseImageRequest,
    ConsentView,
    DatasetPage,
    DatasetView,
    ExportConsentRequest,
    ExportReview,
    PublicationRequest,
    VersionView,
)
from app.schemas.projects import FormDefinition, ProjectDefinition
from app.services.auth import AuthError
from app.services.submissions import own_submission, validate_answers

LICENSE_URLS = {
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}
MAX_IMAGES = 500


def definition(session: Session, pub: DatasetPublication) -> ProjectDefinition:
    v = session.scalar(
        select(ProjectVersion).where(
            ProjectVersion.project_id == pub.project_id,
            ProjectVersion.version == pub.criteria_version,
        )
    )
    return ProjectDefinition.model_validate(v.definition)


def publication(session: Session, ident: uuid.UUID, lock: bool = False) -> DatasetPublication:
    q = select(DatasetPublication).where(
        DatasetPublication.id == ident, DatasetPublication.withdrawn_at.is_(None)
    )
    row = session.scalar(q.with_for_update() if lock else q)
    if not row:
        raise AuthError("Dataset not found.", 404)
    return row


def owner(session: Session, user: User, pub: DatasetPublication) -> None:
    if session.get(Project, pub.project_id).owner_id != user.id:
        raise AuthError("Dataset not found.", 404)


def publish(
    session: Session, user: User, project_id: uuid.UUID, body: PublicationRequest
) -> DatasetPublication:
    p = session.scalar(
        select(Project)
        .where(Project.id == project_id, Project.owner_id == user.id)
        .with_for_update()
    )
    if not p:
        raise AuthError("Collection not found.", 404)
    if p.published_version != body.criteria_version or p.status == "draft":
        raise AuthError("A frozen published collection is required.", 409)
    existing = session.scalar(
        select(DatasetPublication).where(DatasetPublication.project_id == p.id)
    )
    if existing:
        if existing.withdrawn_at or existing.public_fields != body.public_fields:
            raise AuthError("Publication policy is frozen or withdrawn.", 409)
        return existing
    v = session.scalar(
        select(ProjectVersion).where(
            ProjectVersion.project_id == p.id, ProjectVersion.version == body.criteria_version
        )
    )
    d = ProjectDefinition.model_validate(v.definition)
    if d.licence not in LICENSE_URLS:
        raise AuthError("Custom or missing licences require separate distribution review.", 400)
    allowed = {q.key for q in d.criteria.questions if q.type != "short_text"}
    if (
        len(set(body.public_fields)) != len(body.public_fields)
        or not set(body.public_fields) <= allowed
    ):
        raise AuthError(
            "Only unique declared structured fields may be exported. Text answers stay private.",
            400,
        )
    policy = {
        "version": 1,
        "project": str(p.id),
        "criteria_version": body.criteria_version,
        "licence": d.licence,
        "reuse_terms": d.reuse_terms,
        "public_fields": body.public_fields,
        "public_distribution": True,
        "privacy_reviewed": True,
    }
    pub = DatasetPublication(
        project_id=p.id,
        criteria_version=body.criteria_version,
        authorised_by=user.id,
        public_fields=body.public_fields,
        policy_digest=hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
    )
    session.add(pub)
    session.flush()
    return pub


def consent_view(session: Session, row: Submission) -> ConsentView:
    pub = session.scalar(
        select(DatasetPublication).where(
            DatasetPublication.project_id == row.project_id,
            DatasetPublication.withdrawn_at.is_(None),
        )
    )
    grant = session.scalar(select(DatasetConsent).where(DatasetConsent.submission_id == row.id))
    return ConsentView(
        id=grant.id if grant else None,
        publication_id=pub.id if pub else None,
        public_fields=pub.public_fields if pub else [],
        withdrawn=bool(grant and grant.withdrawn_at),
        authorised=bool(grant and grant.authorised_at and not grant.withdrawn_at),
        public_attribution=grant.public_attribution if grant else "",
    )


def consent(
    session: Session, user: User, ident: uuid.UUID, body: ExportConsentRequest
) -> ConsentView:
    row = own_submission(session, user, ident, True)
    pub = publication(session, body.publication_id)
    if (
        pub.project_id != row.project_id
        or row.status not in {"pending", "approved"}
        or row.hidden_at
        or row.image_deleted_at
    ):
        raise AuthError("This image cannot be authorised for distribution.", 409)
    d = definition(session, pub)
    if (
        row.consent_record.get("licence") != d.licence
        or row.consent_record.get("reuse_terms") != d.reuse_terms
    ):
        raise AuthError("Recorded licence/consent mismatch.", 409)
    if d.licence != "CC0-1.0" and not body.public_attribution.strip():
        raise AuthError("Choose a public attribution pseudonym for this licence.", 400)
    existing = session.scalar(select(DatasetConsent).where(DatasetConsent.submission_id == row.id))
    if existing:
        if existing.withdrawn_at or existing.public_attribution != body.public_attribution.strip():
            raise AuthError("This export consent is final or withdrawn.", 409)
    else:
        session.add(
            DatasetConsent(
                publication_id=pub.id,
                submission_id=row.id,
                contributor_id=user.id,
                statement=(
                    "I permit worldwide public distribution of this image and selected labels "
                    "under the recorded licence, confirm my rights, and understand "
                    "downloaded copies "
                    "cannot be recalled and existing open licence grants may remain effective."
                ),
                public_attribution=body.public_attribution.strip(),
                policy_digest=pub.policy_digest,
            )
        )
        session.flush()
    return consent_view(session, row)


def withdraw_consent(session: Session, user: User, ident: uuid.UUID) -> ConsentView:
    row = own_submission(session, user, ident, True)
    grant = session.scalar(
        select(DatasetConsent).where(DatasetConsent.submission_id == row.id).with_for_update()
    )
    if grant and not grant.withdrawn_at:
        grant.withdrawn_at = datetime.now(UTC)
    session.flush()
    return consent_view(session, row)


def review(session: Session, user: User, ident: uuid.UUID) -> list[ExportReview]:
    pub = publication(session, ident)
    owner(session, user, pub)
    rows = session.scalars(
        select(Submission)
        .where(
            Submission.project_id == pub.project_id,
            Submission.workflow_version.in_([1, 2]),
            Submission.status == "approved",
        )
        .order_by(Submission.id)
        .limit(501)
    ).all()
    return [
        ExportReview(
            submission_id=s.id,
            label=s.label_key,
            answers={k: v for k, v in s.metadata_values.items() if k in pub.public_fields},
            consent=consent_view(session, s),
        )
        for s in rows
    ]


def authorise(
    session: Session,
    user: User,
    ident: uuid.UUID,
    submission_id: uuid.UUID,
    body: AuthoriseImageRequest,
) -> None:
    pub = publication(session, ident)
    owner(session, user, pub)
    row = session.scalar(
        select(Submission)
        .where(Submission.id == submission_id, Submission.project_id == pub.project_id)
        .with_for_update()
    )
    grant = session.scalar(
        select(DatasetConsent)
        .where(
            DatasetConsent.id == body.consent_id,
            DatasetConsent.publication_id == pub.id,
            DatasetConsent.submission_id == submission_id,
        )
        .with_for_update()
    )
    if (
        not row
        or not grant
        or grant.withdrawn_at
        or row.hidden_at
        or row.image_deleted_at
        or row.status != "approved"
    ):
        raise AuthError(
            "An approved unrestricted image and current contributor opt-in are required.", 409
        )
    validate_answers(definition(session, pub), row.label_key, row.metadata_values)
    if not grant.authorised_at:
        grant.authorised_at = datetime.now(UTC)
        grant.authorised_by = user.id
    session.flush()


def eligible_query(pub: DatasetPublication):
    return (
        select(Submission, DatasetConsent)
        .join(DatasetConsent, DatasetConsent.submission_id == Submission.id)
        .where(
            Submission.project_id == pub.project_id,
            Submission.criteria_version == pub.criteria_version,
            Submission.workflow_version.in_([1, 2]),
            Submission.status == "approved",
            Submission.hidden_at.is_(None),
            Submission.image_deleted_at.is_(None),
            DatasetConsent.publication_id == pub.id,
            DatasetConsent.withdrawn_at.is_(None),
            DatasetConsent.authorised_at.is_not(None),
            ~exists().where(RemovalRequest.submission_id == Submission.id),
        )
    )


def valid_version(session: Session, v: DatasetVersion) -> bool:
    pub = session.get(DatasetPublication, v.publication_id)
    if v.revoked_at or not pub or pub.withdrawn_at:
        return False
    count = session.scalar(
        select(func.count()).select_from(DatasetMember).where(DatasetMember.version_id == v.id)
    )
    current = eligible_query(pub).with_only_columns(Submission.id).subquery()
    invalid = session.scalar(
        select(func.count())
        .select_from(DatasetMember)
        .where(
            DatasetMember.version_id == v.id, ~DatasetMember.submission_id.in_(select(current.c.id))
        )
    )
    return bool(count) and not invalid


def snapshot(session: Session, pub: DatasetPublication) -> DatasetVersion:
    # Serialise per-publication version numbers and concurrent retry fingerprints.
    pub = publication(session, pub.id, True)
    rows = session.execute(eligible_query(pub).order_by(Submission.id).limit(MAX_IMAGES + 1)).all()
    if not rows:
        raise AuthError("No approved, opted-in, export-authorised images are available.", 409)
    if len(rows) > MAX_IMAGES:
        raise AuthError("Export limit is 500 images per dataset. Split the collection.", 413)
    d = definition(session, pub)
    items = []
    for row, grant in rows:
        validate_answers(d, row.label_key, row.metadata_values)
        items.append(
            {
                "source": "owner-provided"
                if row.workflow_version == 2
                else "community-contributed",
                "submission": str(row.id),
                "consent": str(grant.id),
                "label": row.label_key,
                "answers": {key: row.metadata_values.get(key) for key in pub.public_fields},
                "attribution": grant.public_attribution,
            }
        )
    if (
        any(len(json.dumps(item).encode()) > 8192 for item in items)
        or len(json.dumps(items).encode()) > 2 * 1024 * 1024
    ):
        raise AuthError("Public annotations exceed the export metadata limit.", 413)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "format": 2,
                "encoder": pillow_version,
                "images": items,
                "licence_sha256": hashlib.sha256(
                    (
                        Path(__file__).parents[1] / "resources" / "licences" / (d.licence + ".txt")
                    ).read_bytes()
                ).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    existing = session.scalar(
        select(DatasetVersion).where(
            DatasetVersion.publication_id == pub.id, DatasetVersion.fingerprint == fingerprint
        )
    )
    if existing:
        if existing.revoked_at:
            raise AuthError("This snapshot was revoked. Authorise a new eligible image set.", 410)
        return existing
    number = 1 + session.scalar(
        select(func.coalesce(func.max(DatasetVersion.version), 0)).where(
            DatasetVersion.publication_id == pub.id
        )
    )
    v = DatasetVersion(publication_id=pub.id, version=number, fingerprint=fingerprint)
    session.add(v)
    session.flush()
    for data in items:
        session.add(
            DatasetMember(
                version_id=v.id,
                submission_id=uuid.UUID(data["submission"]),
                consent_id=uuid.UUID(data["consent"]),
                image_id=uuid.uuid5(pub.id, data["submission"]),
                annotations={
                    "source": data["source"],
                    "label": data["label"],
                    "answers": data["answers"],
                    "attribution": data["attribution"],
                },
            )
        )
    session.flush()
    session.add(DatasetBuild(version_id=v.id))
    session.flush()
    return v


def version_view(session: Session, v: DatasetVersion) -> VersionView:
    b = session.scalar(select(DatasetBuild).where(DatasetBuild.version_id == v.id))
    return VersionView(
        downloadable=bool(
            b.state == "ready"
            and b.expires_at
            and b.expires_at > datetime.now(UTC)
            and valid_version(session, v)
        ),
        version=v.version,
        image_count=session.scalar(
            select(func.count()).select_from(DatasetMember).where(DatasetMember.version_id == v.id)
        ),
        created_at=v.created_at,
        revoked=bool(v.revoked_at),
        state=b.state,
        expires_at=b.expires_at,
        byte_size=b.byte_size,
        sha256=b.sha256,
    )


def view(session: Session, pub: DatasetPublication) -> DatasetView:
    d = definition(session, pub)
    versions = session.scalars(
        select(DatasetVersion)
        .where(DatasetVersion.publication_id == pub.id)
        .order_by(DatasetVersion.version.desc())
    ).all()
    return DatasetView(
        id=pub.id,
        collection_id=pub.project_id,
        name=d.name,
        description=d.description,
        purpose=d.research_purpose,
        category=d.category,
        image_count=next(
            (
                len(v.manifest["images"])
                for v in versions
                if v.manifest and not v.revoked_at and valid_version(session, v)
            ),
            0,
        ),
        criteria_version=pub.criteria_version,
        criteria=FormDefinition(
            questions=[q for q in d.criteria.questions if q.key in pub.public_fields]
        ),
        labels=d.labels,
        licence=d.licence,
        licence_url=LICENSE_URLS[d.licence],
        reuse_terms=d.reuse_terms,
        updated_at=max([pub.created_at, *[v.created_at for v in versions]]),
        versions=[version_view(session, v) for v in versions],
    )


def discover(
    session: Session,
    q: str,
    category: str | None,
    licence: str | None,
    sort: str,
    page: int,
    size: int,
) -> DatasetPage:
    query = (
        select(DatasetPublication)
        .join(Project, Project.id == DatasetPublication.project_id)
        .where(DatasetPublication.withdrawn_at.is_(None))
    )
    if category:
        query = query.where(Project.category == category)
    if licence:
        query = query.join(
            ProjectVersion,
            (ProjectVersion.project_id == Project.id)
            & (ProjectVersion.version == DatasetPublication.criteria_version),
        ).where(ProjectVersion.definition["licence"].as_string() == licence)
    term = q.strip().lower()
    for word in term.split()[:10]:
        query = query.where(
            or_(
                func.lower(Project.name).contains(word, autoescape=True),
                func.lower(Project.search_text).contains(word, autoescape=True),
                cast(Project.id, String).contains(word, autoescape=True),
                cast(DatasetPublication.id, String).contains(word, autoescape=True),
            )
        )
    latest = (
        select(func.max(DatasetVersion.created_at))
        .where(DatasetVersion.publication_id == DatasetPublication.id)
        .scalar_subquery()
    )
    order = [func.coalesce(latest, DatasetPublication.created_at).desc(), DatasetPublication.id]
    if sort == "newest":
        order = [DatasetPublication.created_at.desc(), DatasetPublication.id]
    if sort == "relevance" and term:
        order = [(func.lower(Project.name) == term).desc(), *order]
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    return DatasetPage(
        items=[
            view(session, p)
            for p in session.scalars(query.order_by(*order).offset((page - 1) * size).limit(size))
        ],
        total=total,
        page=page,
        page_size=size,
    )
