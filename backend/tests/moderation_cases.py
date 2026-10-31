"""Real PostgreSQL/API moderation, escrow conservation and concurrency scenarios."""

import io
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AuthSession,
    CreditLedgerEntry,
    ModerationDecision,
    NotificationOutbox,
    Project,
    ProjectReservation,
    Submission,
    User,
)
from app.integrations.email import DeliveryError
from app.integrations.storage import LocalObjectStore
from app.jobs.upload_cleanup import cleanup
from app.main import create_app
from app.schemas.moderation import DecisionRequest
from app.schemas.projects import Label, ProjectDefinition
from app.services import auth, moderation, projects, wallet
from app.services.dev_email import DEV_ISSUER
from app.services.notifications import deliver_pending


def exercise_moderation(engine, monkeypatch, tmp_path):
    settings = Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        environment="development",
        dev_email_enabled=True,
        auth_enabled=True,
        uploads_enabled=True,
        storage_root=str(tmp_path),
    )
    store = LocalObjectStore(str(tmp_path))

    def actor(name):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with Session(engine) as s, s.begin():
            u = User(
                identity_issuer=DEV_ISSUER,
                identity_subject=name,
                email=name + "@university.test",
                email_verified_at=datetime.now(UTC),
                display_name=name,
            )
            s.add(u)
            s.flush()
            auth.grant_welcome(s, u, settings)
            s.add(
                AuthSession(
                    user_id=u.id,
                    token_hash=auth.digest(token),
                    csrf_hash=auth.digest(csrf),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    last_seen_at=datetime.now(UTC),
                )
            )
            return u.id, token, csrf

    owner = actor("moderation-owner")
    contributor = actor("moderation-contributor")
    other = actor("moderation-other")
    moderator = actor("moderation-designated")

    def project(count=3):
        with Session(engine) as s, s.begin():
            d = ProjectDefinition(
                name="Moderation fixture",
                description="Synthetic",
                research_purpose="Testing",
                instructions="Original only",
                accepted_content="Scenes",
                prohibited_content="Personal data",
                licence="CC0-1.0",
                reuse_terms="Research",
                min_width=8,
                min_height=8,
                image_count=count,
                reward_per_image=2,
                labels=[Label(key="scene", name="Scene")],
            )
            p = projects.create(s, s.get(User, owner[0]), d)
            projects.transition(s, s.get(User, owner[0]), p.id, "published", 1)
            return p.id

    pid = project()

    def headers(who):
        return {"Origin": settings.frontend_url, "X-CSRF-Token": who[2]}

    def login(c, who):
        c.cookies.set("qpq_session", who[1])

    def upload(c, pid, color):
        login(c, contributor)
        r = c.post(
            f"/api/v1/projects/{pid}/submissions",
            headers=headers(contributor),
            json={
                "request_key": str(uuid.uuid4()),
                "criteria_version": 1,
                "label_key": "scene",
                "answers": {},
                "consent": True,
                "privacy_acknowledgement": True,
            },
        )
        assert r.status_code == 201, r.text
        ident = r.json()["id"]
        b = io.BytesIO()
        Image.new("RGB", (16, 16), color).save(b, "PNG")
        r = c.put(
            f"/api/v1/submissions/{ident}/image", headers=headers(contributor), content=b.getvalue()
        )
        assert r.status_code == 200, r.text
        return uuid.UUID(ident)

    def action(c, ident, outcome="approved", reason="", who=owner):
        login(c, who)
        return c.post(
            f"/api/v1/moderation/{ident}/decision",
            json={"outcome": outcome, "reason": reason},
            headers=headers(who),
        )

    with TestClient(create_app(settings)) as c, TestClient(create_app(settings)) as guest:
        a, b, hidden = [upload(c, pid, color) for color in ["red", "green", "blue"]]
        endpoint = f"/api/v1/moderation/{a}/decision"
        assert (
            guest.post(endpoint, json={"outcome": "approved"}, headers=headers(owner)).status_code
            == 401
        )
        assert action(c, a, who=other).status_code == 404
        assert action(c, a, who=contributor).status_code == 404
        login(c, owner)
        assert c.get(f"/api/v1/submissions/{a}/image").status_code == 404
        assert c.get(f"/api/v1/moderation/{a}/image").status_code == 200
        assert (
            c.post(
                endpoint, json={"outcome": "approved"}, headers={"Origin": settings.frontend_url}
            ).status_code
            == 403
        )
        assert action(c, b, "rejected", "   ").status_code == 422
        assert action(c, b, "rejected", "Wrong scene").status_code == 200
        assert action(c, b, "rejected", "Wrong scene").status_code == 200
        assert action(c, b, "rejected", "Changed reason").status_code == 409
        assert action(c, b).status_code == 409
        login(c, contributor)
        result = c.get(f"/api/v1/submissions/{b}").json()
        assert result["rejection_reason"] == "Wrong scene" and result["qc_earned"] == 0
        assert c.get(f"/api/v1/submissions/{b}/image").status_code == 200
        # Pause stops new contributions but permits resolving existing reviews.
        with Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner[0]), pid, "paused", 1)
        # Approval and credit roll back together if any later step fails.
        with monkeypatch.context() as patch:

            def fail(*_, **__):
                raise RuntimeError("synthetic failure after posting")

            patch.setattr("app.services.moderation.NotificationOutbox", fail)
            with pytest.raises(RuntimeError), Session(engine) as s, s.begin():
                moderation.decide(
                    s, s.get(User, owner[0]), a, DecisionRequest(outcome="approved"), store
                )
        with Session(engine) as s:
            assert s.get(Submission, a).status == "pending"
            assert not s.scalar(
                select(ModerationDecision).where(ModerationDecision.submission_id == a)
            )
            assert not s.scalar(
                select(CreditLedgerEntry).where(
                    CreditLedgerEntry.idempotency_key == f"reward:v1:{a}"
                )
            )
        # A missing/corrupted private image cannot earn QC.
        with monkeypatch.context() as patch:
            patch.setattr(LocalObjectStore, "read", lambda *_: b"corrupt")
            assert action(c, a).status_code == 409

        # Concurrent identical decisions produce one ledger event, including retries.
        same_gate = Barrier(2)

        def approve(_):
            with Session(engine) as s, s.begin():
                same_gate.wait(timeout=10)
                return moderation.decide(
                    s, s.get(User, owner[0]), a, DecisionRequest(outcome="approved"), store
                ).status

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(approve, range(2))) == ["approved", "approved"]
        assert action(c, a).json()["qc_earned"] == 2
        assert action(c, a, "rejected", "Later change").status_code == 409
        login(c, contributor)
        assert c.get(f"/api/v1/submissions/{a}").json()["qc_earned"] == 2
        assert c.get("/api/v1/wallet").json()["available"] == 52
        # Suppression before approval blocks payout; rejection resolves pending funding.
        assert (
            c.post(
                f"/api/v1/submissions/{hidden}/removal-request",
                headers=headers(contributor),
                json={"reason": "privacy"},
            ).status_code
            == 200
        )
        assert action(c, hidden).status_code == 409
        assert action(c, hidden, "rejected", "Removed at contributor request").status_code == 200
        login(c, owner)
        assert c.get(f"/api/v1/moderation/{hidden}/image").status_code == 404
        dashboard = c.get(
            "/api/v1/moderation", params={"project_id": str(pid), "page_size": 1}
        ).json()
        assert (
            dashboard["approved"],
            dashboard["pending"],
            dashboard["rejected"],
            dashboard["total"],
        ) == (1, 0, 2, 3)
        assert (
            len(dashboard["items"]) == 1
            and dashboard["collections"][0]["remaining_reserved_qc"] == 4
        )
        assert (
            c.get(
                "/api/v1/moderation", params={"project_id": str(pid), "status": "approved"}
            ).json()["total"]
            == 1
        )
        held = c.get("/api/v1/wallet").json()
        assert held["available"] == 44 and held["reserved"] == 4
        # Closing after resolution refunds only the unspent 4QC; approved rewards stay earned.
        with Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner[0]), pid, "closed", 1)
        assert action(c, a).status_code == 200  # exact retry remains safe after close
        assert c.get("/api/v1/wallet").json()["available"] == 48
        assert c.get("/api/v1/wallet").json()["reserved"] == 0
        # Approved removal revokes access immediately and retains all QC/audit history.
        login(c, contributor)
        assert (
            c.post(
                f"/api/v1/submissions/{a}/removal-request",
                json={"reason": "copyright"},
                headers=headers(contributor),
            ).status_code
            == 200
        )
        assert c.get(f"/api/v1/submissions/{a}/image").status_code == 404
        history = c.get("/api/v1/wallet").json()
        rewards = [e for e in history["items"] if e["reason"] == "collection_reward"]
        assert (
            len(rewards) == 1
            and rewards[0]["submission_id"] == str(a)
            and history["available"] == 52
        )
        # Designation/revocation, self-review denial and two distinct simultaneous approvals.
        second = project(2)
        x = upload(c, second, "purple")
        y = upload(c, second, "yellow")
        login(c, owner)
        assert (
            c.post(
                f"/api/v1/projects/{second}/moderators",
                json={"user_id": str(moderator[0]), "active": True},
                headers=headers(owner),
            ).status_code
            == 204
        )
        assert action(c, x, who=moderator).status_code == 200
        login(c, other)
        assert c.get(f"/api/v1/moderation/{y}/image").status_code == 404
        assert (
            c.post(
                f"/api/v1/projects/{second}/moderators",
                json={"user_id": str(other[0]), "active": True},
                headers=headers(other),
            ).status_code
            == 404
        )
        login(c, owner)
        assert (
            c.post(
                f"/api/v1/projects/{second}/moderators",
                json={"user_id": str(contributor[0]), "active": True},
                headers=headers(owner),
            ).status_code
            == 204
        )
        assert action(c, y, who=contributor).status_code == 403
        login(c, owner)
        assert (
            c.post(
                f"/api/v1/projects/{second}/moderators",
                json={"user_id": str(moderator[0]), "active": False},
                headers=headers(owner),
            ).status_code
            == 204
        )
        assert action(c, y, who=moderator).status_code == 404
        with pytest.raises(auth.AuthError), Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner[0]), second, "closed", 1)
        assert action(c, y).status_code == 200
        with Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner[0]), second, "closed", 1)
        with Session(engine) as s:
            reservation = s.scalar(
                select(ProjectReservation).where(ProjectReservation.project_id == second)
            )
            assert reservation.release_entry_id is None  # no zero-value ledger event
            assert wallet.remaining(s, s.get(Project, second)) == 0
        third = project(2)
        x = upload(c, third, "orange")
        y = upload(c, third, "pink")

        distinct_gate = Barrier(2)

        def approve_distinct(ident):
            with Session(engine) as s, s.begin():
                distinct_gate.wait(timeout=10)
                moderation.decide(
                    s, s.get(User, owner[0]), ident, DecisionRequest(outcome="approved"), store
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(approve_distinct, [x, y]))
        with Session(engine) as s:
            assert wallet.remaining(s, s.get(Project, third)) == 0
            assert (
                s.scalar(
                    select(func.sum(ModerationDecision.reward))
                    .join(Submission, Submission.id == ModerationDecision.submission_id)
                    .where(Submission.project_id == third)
                )
                == 4
            )
        # SQL cannot mint an orphan reward, fabricate approval or rewrite decisions.
        for statement, params in [
            (
                "INSERT INTO credit_ledger_entries"
                "(id,user_id,project_id,amount,reason,idempotency_key) "
                "VALUES (:id,:user,:project,2,'collection_reward',:key)",
                {
                    "id": uuid.uuid4(),
                    "user": contributor[0],
                    "project": third,
                    "key": "reward:v1:" + str(uuid.uuid4()),
                },
            ),
            ("UPDATE moderation_decisions SET reward=reward+1 WHERE submission_id=:id", {"id": a}),
            ("DELETE FROM moderation_decisions WHERE submission_id=:id", {"id": a}),
            ("UPDATE project_reservations SET amount=amount+1 WHERE project_id=:id", {"id": third}),
        ]:
            with pytest.raises(DBAPIError), engine.begin() as con:
                con.execute(text(statement), params)
        # Explicit insufficient escrow branch cannot write any reward (no invalid DB fixture).
        fourth = project(1)
        z = upload(c, fourth, "brown")
        with monkeypatch.context() as patch:
            patch.setattr("app.services.moderation.remaining", lambda *_: 0)
            assert action(c, z).status_code == 409
        with Session(engine) as s:
            assert s.get(Submission, z).status == "pending"
        # Forged reward amounts/recipients cannot consume or mint escrow credits.
        for amount, recipient in [(999, contributor[0]), (2, owner[0])]:
            with pytest.raises(DBAPIError) as rejected, Session(engine) as s, s.begin():
                entry = CreditLedgerEntry(
                    user_id=recipient,
                    project_id=fourth,
                    amount=amount,
                    reason="collection_reward",
                    idempotency_key=f"reward:v1:{z}",
                )
                s.add(entry)
                s.flush()
                s.add(
                    ModerationDecision(
                        submission_id=z,
                        reviewer_id=owner[0],
                        outcome="approved",
                        reason="",
                        reward=2,
                        reward_entry_id=entry.id,
                    )
                )
                s.flush()
            assert rejected.value.orig.sqlstate == "P0001"
        # Backend revalidates the recorded criteria before creating any reward.
        with monkeypatch.context() as patch:

            def invalid_answers(*_):
                raise auth.AuthError("Invalid recorded criteria answers.", 400)

            patch.setattr("app.services.moderation.validate_answers", invalid_answers)
            assert action(c, z).status_code == 400
        # Force auth to hold the recipient User lock while waiting for the
        # reviewer's eligibility lock. FK KEY SHARE must not deadlock payout.
        reviewer_ready, recipient_waiting = Event(), Event()
        real_eligible = auth.eligible
        with monkeypatch.context() as patch:

            def observed_eligible(session, config, user):
                if user.id == contributor[0]:
                    recipient_waiting.set()
                return real_eligible(session, config, user)

            patch.setattr(auth, "eligible", observed_eligible)

            def concurrent_auth(kind):
                with Session(engine) as s, s.begin():
                    s.execute(text("SET LOCAL lock_timeout = '5s'"))
                    if kind == "review":
                        reviewer = auth.authenticate(s, settings, owner[1], owner[2], True)
                        reviewer_ready.set()
                        assert recipient_waiting.wait(3)
                        moderation.decide(
                            s, reviewer, z, DecisionRequest(outcome="approved"), store
                        )
                        return "paid"
                    assert reviewer_ready.wait(3)
                    auth.authenticate(s, settings, contributor[1])
                    return "authenticated"

            with ThreadPoolExecutor(max_workers=2) as pool:
                assert list(pool.map(concurrent_auth, ["review", "recipient"])) == [
                    "paid",
                    "authenticated",
                ]
        # Authorised reviewers can also revoke access; unrelated users cannot.
        login(c, other)
        assert (
            c.post(
                f"/api/v1/moderation/{y}/removal-request",
                json={"reason": "privacy"},
                headers=headers(other),
            ).status_code
            == 404
        )
        login(c, owner)
        assert (
            c.post(
                f"/api/v1/moderation/{y}/removal-request",
                json={"reason": "privacy"},
                headers=headers(owner),
            ).status_code
            == 200
        )
        assert c.get(f"/api/v1/moderation/{y}/image").status_code == 404
        # Approval versus closure never releases an unresolved reward budget.
        race_project = project(1)
        race_image = upload(c, race_project, "cyan")
        close_gate = Barrier(2)

        def race(kind):
            with Session(engine) as s, s.begin():
                user = s.get(User, owner[0])
                close_gate.wait(timeout=10)
                if kind == "approve":
                    moderation.decide(
                        s, user, race_image, DecisionRequest(outcome="approved"), store
                    )
                    return "approved"
                try:
                    projects.transition(s, user, race_project, "closed", 1)
                    return "closed"
                except auth.AuthError:
                    return "blocked"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(race, ["approve", "close"]))
        assert results[0] == "approved" and results[1] in {"closed", "blocked"}
        with Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner[0]), race_project, "closed", 1)
            assert wallet.remaining(s, s.get(Project, race_project)) == 0
        # QC is conserved across available wallets and the remaining escrow.
        with Session(engine) as s:
            total = sum(
                auth.balance(s, s.get(User, actor[0]))
                for actor in [owner, contributor, other, moderator]
            ) + wallet.reserved(s, s.get(User, owner[0]))
            assert total == 200
        # Outbox retries SMTP failure without touching decisions/rewards.
        with monkeypatch.context() as patch:

            def unavailable(*_):
                raise DeliveryError("synthetic")

            patch.setattr("app.services.notifications.deliver_message", unavailable)
            assert deliver_pending(engine, settings) == 0
        with Session(engine) as s:
            assert s.scalar(select(NotificationOutbox).where(NotificationOutbox.attempts > 0))

        # Advance worker clock only, not immutable audit records.
        class Later(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(days=31)

        delivered = []
        with monkeypatch.context() as patch:
            patch.setattr("app.services.notifications.datetime", Later)
            patch.setattr(
                "app.services.notifications.deliver_message",
                lambda settings, message: delivered.append(message),
            )
            assert deliver_pending(engine, settings) >= 6
            assert deliver_pending(engine, settings) == 0
        assert delivered and all("/submissions" in m.get_content() for m in delivered)
        # Retention removes rejected/suppressed bytes, never decisions, consent or credits.
        cleanup(engine, str(tmp_path))
        with Session(engine) as s:
            assert all(s.get(Submission, i).image_deleted_at for i in [a, hidden])
            assert s.get(Submission, b).image_deleted_at is None  # Retained for 30 days
            assert s.get(Submission, a).status == "approved"
            assert (
                s.scalar(
                    select(CreditLedgerEntry.amount).where(
                        CreditLedgerEntry.idempotency_key == f"reward:v1:{a}"
                    )
                )
                == 2
            )
