from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CreditLedgerEntry, ModerationDecision, Project, ProjectReservation, User
from app.schemas.moderation import WalletEntry, WalletView
from app.services.auth import balance


def spent(session: Session, project_id: UUID) -> int:
    return session.scalar(
        select(func.coalesce(func.sum(CreditLedgerEntry.amount), 0)).where(
            CreditLedgerEntry.project_id == project_id,
            CreditLedgerEntry.reason == "collection_reward",
        )
    )


def remaining(session: Session, project: Project) -> int:
    reservation = session.scalar(
        select(ProjectReservation).where(ProjectReservation.project_id == project.id)
    )
    if not reservation or reservation.release_entry_id or project.status == "closed":
        return 0
    return reservation.amount - spent(session, project.id)


def reserved(session: Session, user: User) -> int:
    return sum(
        remaining(session, p)
        for p in session.scalars(
            select(Project).where(
                Project.owner_id == user.id, Project.status.in_(["published", "paused"])
            )
        )
    )


def history(session: Session, user: User, page: int, page_size: int) -> WalletView:
    q = (
        select(CreditLedgerEntry, ModerationDecision.submission_id)
        .outerjoin(ModerationDecision, ModerationDecision.reward_entry_id == CreditLedgerEntry.id)
        .where(CreditLedgerEntry.user_id == user.id)
    )
    total = session.scalar(select(func.count()).select_from(q.subquery()))
    return WalletView(
        available=balance(session, user),
        reserved=reserved(session, user),
        items=[
            WalletEntry(
                id=e.id,
                created_at=e.created_at,
                amount=e.amount,
                reason=e.reason,
                project_id=e.project_id,
                submission_id=sid,
            )
            for e, sid in session.execute(
                q.order_by(CreditLedgerEntry.created_at.desc(), CreditLedgerEntry.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
