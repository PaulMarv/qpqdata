import hashlib
import json
import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import AuthError
from app.image_processing import ProcessedImage
from app.models import Project, ProjectReservation, ProjectVersion, RemovalRequest, Submission, User
from app.project_schemas import ProjectDefinition
from app.storage import ObjectStore
from app.submission_schemas import MAX_BATCH, PER_USER_LIMIT, SubmissionRequest, SubmissionView


def validate_answers(definition: ProjectDefinition, label: str, answers: dict) -> None:
    if label not in {x.key for x in definition.labels}:
        raise AuthError("Choose a valid collection label.", 400)
    questions = {q.key: q for q in definition.criteria.questions}
    if set(answers) - questions.keys():
        raise AuthError("Answers contain unknown questions.", 400)
    for key, q in questions.items():
        value = answers.get(key)
        absent = value is None or value == "" or value == []
        if absent:
            if q.required:
                raise AuthError(f"Required answer: {q.title}", 400)
            continue
        valid = False
        if q.type == "single_choice":
            valid = isinstance(value, str) and value in q.options
        elif q.type == "multiple_choice":
            valid = isinstance(value, list) and all(isinstance(x, str) for x in value)
            if valid:
                valid = len(set(value)) == len(value) and set(value) <= set(q.options)
                valid = valid and (q.min_selections or 0) <= len(value) <= (
                    q.max_selections or len(q.options)
                )
        elif q.type == "short_text":
            valid = (
                isinstance(value, str)
                and bool(value.strip())
                and (q.min_length or 0) <= len(value) <= (q.max_length or 2000)
            )
        elif q.type == "number":
            valid = type(value) in {int, float} and abs(value) <= 1e15 and math.isfinite(value)
            if valid:
                valid = (q.min_value is None or value >= q.min_value) and (
                    q.max_value is None or value <= q.max_value
                )
                valid = valid and (not q.integer_only or value == int(value))
        elif q.type == "yes_no":
            valid = type(value) is bool
        if not valid:
            raise AuthError(f"Invalid answer: {q.title}", 400)


def active(now):
    return or_(
        Submission.status.in_(["pending", "approved"]),
        (Submission.status == "uploading")
        & Submission.abandoned_at.is_(None)
        & (Submission.upload_expires_at > now),
    )


def accepting(session: Session, user: User, project: Project) -> ProjectDefinition:
    if project.owner_id == user.id:
        raise AuthError("You cannot contribute to your own collection.", 403)
    if project.status != "published" or project.published_version is None:
        raise AuthError("This collection is not accepting new images.", 409)
    reservation = session.scalar(
        select(ProjectReservation).where(ProjectReservation.project_id == project.id)
    )
    if not reservation or reservation.release_entry_id:
        raise AuthError("Collection funding is unavailable.", 409)
    version = session.scalar(
        select(ProjectVersion).where(
            ProjectVersion.project_id == project.id,
            ProjectVersion.version == project.published_version,
        )
    )
    definition = ProjectDefinition.model_validate(version.definition)
    if definition.closing_date and definition.closing_date < datetime.now(UTC).date():
        raise AuthError("The collection closing date has passed.", 409)
    return definition


def initiate(
    session: Session, user: User, project_id: uuid.UUID, body: SubmissionRequest
) -> Submission:
    digest = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing = session.scalar(
        select(Submission).where(
            Submission.contributor_id == user.id, Submission.request_key == body.request_key
        )
    )
    if existing:
        if existing.project_id != project_id or existing.request_hash != digest:
            raise AuthError("This retry key belongs to different submission data.", 409)
        return existing
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if not project:
        raise AuthError("Collection not found.", 404)
    definition = accepting(session, user, project)
    if body.criteria_version != project.published_version:
        raise AuthError("Reload the published collection requirements.", 409)
    validate_answers(definition, body.label_key, body.answers)
    now = datetime.now(UTC)
    query = (
        select(func.count())
        .select_from(Submission)
        .where(Submission.project_id == project.id, active(now))
    )
    if session.scalar(query) >= definition.image_count:
        raise AuthError("Collection capacity has been reached.", 409)
    if session.scalar(query.where(Submission.contributor_id == user.id)) >= PER_USER_LIMIT:
        raise AuthError("You reached the 20-image limit for this collection.", 409)
    if (
        session.scalar(
            query.where(Submission.contributor_id == user.id, Submission.status == "uploading")
        )
        >= MAX_BATCH
    ):
        raise AuthError("Finish or wait for your existing upload slots to expire.", 409)
    ident = uuid.uuid4()
    row = Submission(
        id=ident,
        project_id=project.id,
        contributor_id=user.id,
        status="uploading",
        object_key=f"reserved/{ident.hex}",
        metadata_values=body.answers,
        workflow_version=1,
        criteria_version=body.criteria_version,
        label_key=body.label_key,
        request_key=body.request_key,
        request_hash=digest,
        upload_expires_at=now + timedelta(minutes=15),
        consent_record={
            "policy_version": 1,
            "confirmed_at": now.isoformat(),
            "ownership_or_permission": True,
            "privacy_acknowledgement": True,
            "licence": definition.licence,
            "reuse_terms": definition.reuse_terms,
            "statement": (
                "I own or have permission to submit this image and agree to "
                "this collection's licence and reuse terms."
            ),
        },
    )
    session.add(row)
    session.flush()
    return row


def own_submission(session: Session, user: User, ident: uuid.UUID, lock=False) -> Submission:
    query = select(Submission).where(
        Submission.id == ident,
        Submission.contributor_id == user.id,
        Submission.workflow_version == 1,
    )
    row = session.scalar(query.with_for_update() if lock else query)
    if not row:
        raise AuthError("Submission not found.", 404)
    return row


def view(session: Session, row: Submission) -> SubmissionView:
    version = session.scalar(
        select(ProjectVersion).where(
            ProjectVersion.project_id == row.project_id,
            ProjectVersion.version == row.criteria_version,
        )
    )
    definition = ProjectDefinition.model_validate(version.definition)
    return SubmissionView(
        id=row.id,
        project_id=row.project_id,
        project_name=session.get(Project, row.project_id).name,
        criteria_version=row.criteria_version,
        label_key=row.label_key,
        label_name=next(label.name for label in definition.labels if label.key == row.label_key),
        answer_titles={question.key: question.title for question in definition.criteria.questions},
        answers=row.metadata_values,
        consent_record=row.consent_record,
        status=row.status,
        expired=bool(
            row.abandoned_at
            or (row.status == "uploading" and row.upload_expires_at <= datetime.now(UTC))
        ),
        hidden=bool(row.hidden_at),
        width=row.width,
        height=row.height,
        image_format=row.image_format,
        byte_size=row.byte_size,
        created_at=row.created_at,
        submitted_at=row.submitted_at,
        upload_expires_at=row.upload_expires_at,
    )


def suppress(
    session: Session, user: User, ident: uuid.UUID, reason: str, details: str
) -> Submission:
    row = own_submission(session, user, ident, True)
    if not row.hidden_at:
        row.hidden_at = datetime.now(UTC)
        session.add(
            RemovalRequest(
                submission_id=row.id, reporter_id=user.id, reason=reason, details=details
            )
        )
        session.flush()
    return row


def upload_definition(session: Session, user: User, ident: uuid.UUID) -> ProjectDefinition:
    row = own_submission(session, user, ident)
    project = session.get(Project, row.project_id)
    if row.hidden_at or row.abandoned_at:
        raise AuthError("Upload is expired or suppressed.", 410)
    if row.status == "uploading" and row.upload_expires_at <= datetime.now(UTC):
        raise AuthError("Upload slot expired. Start again.", 410)
    if row.status == "pending":
        version = session.scalar(
            select(ProjectVersion).where(
                ProjectVersion.project_id == row.project_id,
                ProjectVersion.version == row.criteria_version,
            )
        )
        return ProjectDefinition.model_validate(version.definition)
    return accepting(session, user, project)


def finish_image(
    session: Session,
    user: User,
    ident: uuid.UUID,
    image: ProcessedImage,
    store: ObjectStore,
    key: str,
) -> Submission:
    row = own_submission(session, user, ident, True)
    if row.hidden_at or row.abandoned_at:
        raise AuthError("Upload is expired or suppressed.", 410)
    if row.status == "pending":
        if row.content_hash != image.content_hash:
            raise AuthError("This retry contains a different image.", 409)
        return row
    project = session.scalar(select(Project).where(Project.id == row.project_id).with_for_update())
    definition = accepting(session, user, project)
    if row.upload_expires_at <= datetime.now(UTC):
        raise AuthError("Upload slot expired. Start again.", 410)
    validate_answers(definition, row.label_key, row.metadata_values)
    duplicate = session.scalar(
        select(Submission.id).where(
            Submission.project_id == row.project_id,
            Submission.contributor_id == user.id,
            Submission.content_hash == image.content_hash,
            Submission.id != row.id,
        )
    )
    if duplicate:
        raise AuthError("You already submitted this image to this collection.", 409)
    store.put(key, image.data)
    row.object_key = key
    row.content_hash = image.content_hash
    row.image_format = image.format
    row.width, row.height, row.byte_size = image.width, image.height, len(image.data)
    row.submitted_at, row.status = datetime.now(UTC), "pending"
    session.flush()
    return row
