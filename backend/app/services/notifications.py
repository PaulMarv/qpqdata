"""Durable moderation outcome emails; no private image, answer or token payloads."""

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ModerationDecision, NotificationOutbox, Submission, User
from app.integrations.email import DeliveryError, deliver_message


def deliver_pending(engine: Engine, settings: Settings) -> int:
    sent = 0
    # Short bounded batches. Row locks prevent two workers sending concurrently.
    for _ in range(20):
        with Session(engine) as session, session.begin():
            row = session.scalar(
                select(NotificationOutbox)
                .where(
                    NotificationOutbox.sent_at.is_(None),
                    NotificationOutbox.next_attempt_at <= datetime.now(UTC),
                )
                .order_by(NotificationOutbox.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not row:
                break
            decision = session.get(ModerationDecision, row.decision_id)
            submission = session.get(Submission, decision.submission_id)
            user = session.get(User, submission.contributor_id)
            message = EmailMessage()
            message["From"] = settings.email_sender
            message["To"] = user.email
            message["Subject"] = "Your QPQData submission has been reviewed"
            message["Message-ID"] = f"<decision-{decision.id}@qpqdata.test>"
            message.set_content(
                "Your submission was "
                + decision.outcome
                + ".\n"
                + (f"You earned {decision.reward} QC.\n" if decision.reward else "")
                + "Sign in to My Submissions to see the decision and any rejection reason:\n"
                + settings.frontend_url.rstrip("/")
                + "/submissions\n"
            )
            row.attempts += 1
            try:
                deliver_message(settings, message)
            except DeliveryError:
                row.next_attempt_at = datetime.now(UTC) + timedelta(
                    minutes=min(60, 2 ** min(row.attempts, 6))
                )
            else:
                row.sent_at = datetime.now(UTC)
                sent += 1
    return sent
