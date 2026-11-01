from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import (
    CreditLedgerEntry,
    ModerationDecision,
    NotificationOutbox,
    Project,
    ProjectModerator,
    ProjectVersion,
    RemovalRequest,
    Submission,
    User,
)
from app.integrations.storage import ObjectStore
from app.schemas.moderation import Capacity, DecisionRequest, ReviewItem, ReviewPage
from app.schemas.projects import ProjectDefinition
from app.services.auth import AuthError
from app.services.submissions import validate_answers, view
from app.services.wallet import remaining


def permission(user: User) -> ColumnElement[bool]:
    return or_(
        Project.owner_id == user.id,
        exists().where(
            ProjectModerator.project_id == Project.id,
            ProjectModerator.user_id == user.id,
            ProjectModerator.revoked_at.is_(None),
        ),
    )


def review_row(session: Session, user: User, ident: UUID, lock: bool = False) -> Submission:
    pid = session.scalar(
        select(Submission.project_id).where(
            Submission.id == ident, Submission.workflow_version == 1
        )
    )
    query = select(Project).where(Project.id == pid, permission(user))
    project = session.scalar(query.with_for_update() if lock else query)
    if not project:
        raise AuthError("Submission not found.", 404)
    row = session.scalar(select(Submission).where(Submission.id == ident).with_for_update())
    if row.contributor_id == user.id:
        raise AuthError("You cannot review your own image.", 403)
    return row


def item(session: Session, row: Submission) -> ReviewItem:
    decision = session.scalar(
        select(ModerationDecision).where(ModerationDecision.submission_id == row.id)
    )
    return ReviewItem(
        submission=view(session, row),
        contributor_name=session.get(User, row.contributor_id).display_name or "Contributor",
        reviewer_id=decision.reviewer_id if decision else None,
        reviewed_at=decision.created_at if decision else None,
    )


def decide(
    session: Session, user: User, ident: UUID, body: DecisionRequest, store: ObjectStore
) -> Submission:
    row = review_row(session, user, ident, True)
    existing = session.scalar(
        select(ModerationDecision).where(ModerationDecision.submission_id == row.id)
    )
    if existing:
        if (existing.outcome, existing.reason) != (body.outcome, body.reason):
            raise AuthError("This image already has a different final decision.", 409)
        return row  # canonical per-submission idempotency, including exact rejection reason
    project = session.get(Project, row.project_id)
    if project.status not in {"published", "paused"} or row.status != "pending":
        raise AuthError("This submission is not pending in an open review collection.", 409)
    reward, entry = 0, None
    if body.outcome == "approved":
        if (
            row.hidden_at
            or row.image_deleted_at
            or session.scalar(
                select(RemovalRequest.id).where(RemovalRequest.submission_id == row.id)
            )
        ):
            raise AuthError("This image is restricted by a removal request.", 409)
        try:
            data = store.read(row.object_key)
        except (OSError, ValueError):
            raise AuthError("Image unavailable. Approval was not recorded.", 409) from None
        if len(data) != row.byte_size:
            raise AuthError("Image unavailable. Approval was not recorded.", 409)
        import io

        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.size != (row.width, row.height) or image.format != row.image_format:
                    raise ValueError("Stored image mismatch")
                image.verify()
        except (OSError, ValueError, UnidentifiedImageError):
            raise AuthError("Image integrity check failed.", 409) from None
        version = session.scalar(
            select(ProjectVersion).where(
                ProjectVersion.project_id == row.project_id,
                ProjectVersion.version == row.criteria_version,
            )
        )
        definition = ProjectDefinition.model_validate(version.definition)
        validate_answers(definition, row.label_key, row.metadata_values)
        reward = definition.reward_per_image
        approved = session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.project_id == project.id,
                Submission.status == "approved",
                (Submission.workflow_version != 2) | Submission.hidden_at.is_(None),
            )
        )
        if remaining(session, project) < reward or approved >= definition.image_count:
            raise AuthError("Insufficient reserved approval capacity.", 409)
        entry = CreditLedgerEntry(
            user_id=row.contributor_id,
            project_id=project.id,
            amount=reward,
            reason="collection_reward",
            idempotency_key=f"reward:v1:{row.id}",
        )
        session.add(entry)
        session.flush()
    decision = ModerationDecision(
        submission_id=row.id,
        reviewer_id=user.id,
        outcome=body.outcome,
        reason=body.reason,
        reward=reward,
        reward_entry_id=entry.id if entry else None,
    )
    session.add(decision)
    session.flush()
    row.status = body.outcome
    session.add(NotificationOutbox(decision_id=decision.id))
    session.flush()
    return row


def dashboard(
    session: Session,
    user: User,
    project_id: UUID | None,
    status: str | None,
    page: int,
    page_size: int,
) -> ReviewPage:
    projects = session.scalars(
        select(Project)
        .where(permission(user), Project.mode == "crowdsourced")
        .order_by(Project.created_at.desc(), Project.id)
    ).all()
    if project_id and project_id not in {p.id for p in projects}:
        raise AuthError("Collection not found.", 404)
    selected = [p for p in projects if not project_id or p.id == project_id]
    capacities = []
    for p in selected:
        counts = dict(
            session.execute(
                select(Submission.status, func.count())
                .where(Submission.project_id == p.id, Submission.workflow_version == 1)
                .group_by(Submission.status)
            ).all()
        )
        uploading = session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.project_id == p.id,
                Submission.status == "uploading",
                Submission.abandoned_at.is_(None),
                Submission.upload_expires_at > datetime.now(UTC),
            )
        )
        if not p.published_version:
            continue
        version = session.scalar(
            select(ProjectVersion).where(
                ProjectVersion.project_id == p.id, ProjectVersion.version == p.published_version
            )
        )
        definition = ProjectDefinition.model_validate(version.definition)
        owner_count = session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.project_id == p.id,
                Submission.workflow_version == 2,
                Submission.status == "approved",
                Submission.hidden_at.is_(None),
            )
        )
        held = remaining(session, p)
        capacities.append(
            Capacity(
                project_id=p.id,
                project_name=p.name,
                requested=definition.image_count,
                owner_images=owner_count,
                uploading=uploading,
                pending=counts.get("pending", 0),
                approved=counts.get("approved", 0),
                rejected=counts.get("rejected", 0),
                remaining_reserved_qc=held,
                remaining_funded_approvals=min(
                    held // definition.reward_per_image,
                    definition.image_count - counts.get("approved", 0) - owner_count,
                ),
            )
        )
    q = select(Submission).where(
        Submission.project_id.in_([p.id for p in selected]),
        Submission.workflow_version == 1,
        Submission.status.in_(["pending", "approved", "rejected"]),
    )
    if status:
        q = q.where(Submission.status == status)
    total = session.scalar(select(func.count()).select_from(q.subquery()))
    rows = session.scalars(
        q.order_by(Submission.submitted_at.desc(), Submission.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ReviewPage(
        items=[item(session, row) for row in rows],
        collections=capacities,
        pending=sum(c.pending for c in capacities),
        approved=sum(c.approved for c in capacities),
        rejected=sum(c.rejected for c in capacities),
        total=total,
        page=page,
        page_size=page_size,
    )


def designate(session: Session, owner: User, project_id: UUID, user_id: UUID, active: bool):
    project = session.scalar(
        select(Project)
        .where(Project.id == project_id, Project.owner_id == owner.id)
        .with_for_update()
    )
    if not project:
        raise AuthError("Collection not found.", 404)
    target = session.get(User, user_id)
    if not target or target.id == owner.id or not target.email_verified_at or target.disabled_at:
        raise AuthError("Choose another verified reviewer account.", 400)
    row = session.scalar(
        select(ProjectModerator).where(
            ProjectModerator.project_id == project_id, ProjectModerator.user_id == user_id
        )
    )
    if not row:
        row = ProjectModerator(project_id=project_id, user_id=user_id, granted_by=owner.id)
        session.add(row)
    row.revoked_at = None if active else datetime.now(UTC)
    session.flush()
