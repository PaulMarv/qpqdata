from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    CreditLedgerEntry,
    Project,
    ProjectReservation,
    ProjectVersion,
    Submission,
    User,
)
from app.schemas.projects import ProjectDefinition, ProjectPage, ProjectView
from app.services.auth import AuthError, balance
from app.services.wallet import remaining, spent


def owner_project(session: Session, user: User, project_id: UUID) -> Project:
    session.get(User, user.id, with_for_update={"key_share": True})
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if not project or project.owner_id != user.id:
        raise AuthError("Project not found.", 404)
    return project


def save_definition(session: Session, project: Project, definition: ProjectDefinition) -> None:
    project.current_version += 1
    session.add(
        ProjectVersion(
            project_id=project.id,
            version=project.current_version,
            definition=definition.model_dump(mode="json"),
        )
    )
    project.name, project.description, project.category = (
        definition.name,
        definition.description,
        definition.category,
    )
    project.search_text = " ".join(
        [
            definition.name,
            definition.description,
            definition.research_purpose,
            *definition.keywords,
            *(label.name for label in definition.labels),
        ]
    ).lower()
    session.flush()


def create(session: Session, user: User, definition: ProjectDefinition) -> Project:
    project = Project(
        owner_id=user.id,
        name=definition.name,
        description=definition.description,
        current_version=0,
    )
    session.add(project)
    session.flush()
    save_definition(session, project, definition)
    return project


def edit(
    session: Session, user: User, project_id: UUID, expected: int, definition: ProjectDefinition
) -> Project:
    project = owner_project(session, user, project_id)
    if project.status != "draft" or project.published_version is not None:
        raise AuthError(
            "Published definitions are frozen. Create a new project for different criteria.", 409
        )
    if project.current_version != expected:
        raise AuthError("This draft changed. Reload before saving.", 409)
    save_definition(session, project, definition)
    return project


def definition_for(session: Session, project: Project) -> ProjectDefinition:
    if project.current_version == 0:
        # Preserve Phase 1 drafts without inventing missing requirements.
        return ProjectDefinition(name=project.name, description=project.description)
    version = session.scalar(
        select(ProjectVersion).where(
            ProjectVersion.project_id == project.id,
            ProjectVersion.version == project.current_version,
        )
    )
    if not version:
        raise AuthError("Project definition unavailable.", 503)
    return ProjectDefinition.model_validate(version.definition)


def publication_checks(session: Session, project: Project, definition: ProjectDefinition) -> None:
    required = [
        definition.description,
        definition.research_purpose,
        definition.instructions,
        definition.accepted_content,
        definition.prohibited_content,
        definition.licence,
        definition.reuse_terms,
    ]
    if (
        project.current_version < 1
        or not all(value.strip() for value in required)
        or not definition.labels
    ):
        raise AuthError(
            "Complete the purpose, instructions, content rules, labels, licence "
            "and reuse terms before publishing.",
            400,
        )
    if definition.closing_date and definition.closing_date < datetime.now(UTC).date():
        raise AuthError("Closing date has passed.", 400)
    if project.published_version is None and session.scalar(
        select(func.count()).select_from(Submission).where(Submission.project_id == project.id)
    ):
        raise AuthError("Existing submissions require a separately reviewed transition.", 409)


def transition(
    session: Session, user: User, project_id: UUID, status: str, expected: int
) -> Project:
    project = owner_project(session, user, project_id)
    if project.current_version != expected:
        raise AuthError("This project changed. Reload before continuing.", 409)
    if project.status == status:
        return project
    allowed = {
        "draft": {"published", "closed"},
        "published": {"paused", "closed"},
        "paused": {"published", "closed"},
        "closed": set(),
    }
    if status not in allowed[project.status]:
        raise AuthError("This lifecycle transition is not allowed.", 409)
    definition = definition_for(session, project)
    reservation = session.scalar(
        select(ProjectReservation)
        .where(ProjectReservation.project_id == project.id)
        .with_for_update()
    )
    if status == "published":
        publication_checks(session, project, definition)
        if project.status == "draft":
            amount = definition.image_count * definition.reward_per_image
            if balance(session, user) < amount:
                raise AuthError(
                    "Insufficient QC. Reduce the image target or reward before publishing.", 409
                )
            debit = CreditLedgerEntry(
                user_id=user.id,
                project_id=project.id,
                amount=-amount,
                reason="collection_reservation",
                idempotency_key=f"reservation:v1:{project.id}",
            )
            session.add(debit)
            session.flush()
            reservation = ProjectReservation(
                project_id=project.id, amount=amount, debit_entry_id=debit.id
            )
            session.add(reservation)
            project.published_version = project.current_version
        elif not reservation or reservation.release_entry_id:
            raise AuthError("Project funding unavailable.", 409)
    if status == "closed" and reservation and reservation.release_entry_id is None:
        if session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.project_id == project.id,
                (Submission.status == "pending")
                | (
                    (Submission.status == "uploading")
                    & Submission.abandoned_at.is_(None)
                    & (Submission.upload_expires_at > datetime.now(UTC))
                ),
            )
        ):
            raise AuthError("Resolve pending reviews and active uploads before closing.", 409)
        unspent = reservation.amount - spent(session, project.id)
        if unspent:
            release = CreditLedgerEntry(
                user_id=user.id,
                project_id=project.id,
                amount=unspent,
                reason="collection_release",
                idempotency_key=f"release:v1:{project.id}",
                reversal_of_id=reservation.debit_entry_id,
            )
            session.add(release)
            session.flush()
            reservation.release_entry_id = release.id
    project.status = status
    session.flush()
    return project


def view(session: Session, project: Project) -> ProjectView:
    definition = definition_for(session, project)
    return ProjectView(
        id=project.id,
        owner_id=project.owner_id,
        status=project.status,
        version=project.current_version,
        published_version=project.published_version,
        definition=definition,
        reserved_credits=remaining(session, project),
        budget=definition.image_count * definition.reward_per_image,
        created_at=project.created_at,
        closing_date_passed=bool(
            definition.closing_date and definition.closing_date < datetime.now(UTC).date()
        ),
    )


def discover(
    session: Session,
    q: str,
    category: str | None,
    status: str | None,
    sort: str,
    page: int,
    page_size: int,
    owner: User | None = None,
) -> ProjectPage:
    query = select(Project)
    query = (
        query.where(Project.owner_id == owner.id)
        if owner
        else query.where(Project.published_version.is_not(None))
    )
    if category:
        query = query.where(Project.category == category)
    if status:
        query = query.where(Project.status == status)
    term = q.strip().lower()
    if term:
        for word in term.split()[:10]:
            query = query.where(
                or_(
                    func.lower(Project.search_text).contains(word, autoescape=True),
                    func.lower(Project.name).contains(word, autoescape=True),
                    cast(Project.id, String).contains(word, autoescape=True),
                )
            )
    rank = case(
        (cast(Project.id, String) == term, 100),
        (func.lower(Project.name) == term, 80),
        (func.lower(Project.name).startswith(term, autoescape=True), 40),
        else_=10,
    )
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    ordering = (
        [rank.desc(), Project.created_at.desc(), Project.id]
        if sort == "relevance" and term
        else [Project.created_at.desc(), Project.id]
    )
    projects = session.scalars(
        query.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ProjectPage(
        items=[view(session, p) for p in projects], total=total, page=page, page_size=page_size
    )
