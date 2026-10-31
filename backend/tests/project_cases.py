import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AuthSession,
    CreditLedgerEntry,
    Project,
    ProjectReservation,
    ProjectVersion,
    User,
)
from app.main import create_app
from app.schemas.projects import FormDefinition, Label, ProjectDefinition, Question
from app.services import auth, projects
from app.services.dev_email import DEV_ISSUER


def exercise_projects(engine, monkeypatch) -> None:
    settings = Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        environment="development",
        dev_email_enabled=True,
        auth_enabled=True,
    )

    def actor(email):
        raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with Session(engine) as session, session.begin():
            user = User(
                identity_issuer=DEV_ISSUER,
                identity_subject=email,
                email=email,
                email_verified_at=datetime.now(UTC),
            )
            session.add(user)
            session.flush()
            auth.grant_welcome(session, user, settings)
            session.add(
                AuthSession(
                    user_id=user.id,
                    token_hash=auth.digest(raw),
                    csrf_hash=auth.digest(csrf),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    last_seen_at=datetime.now(UTC),
                )
            )
            return user.id, raw, csrf

    owner, raw, csrf = actor("collections-owner@university.test")
    other, other_raw, other_csrf = actor("collections-other@university.test")
    definition = ProjectDefinition(
        name="Clean & Messy Kitchens",
        description="Original kitchen scenes",
        research_purpose="Synthetic classification study",
        category="science",
        instructions="Photograph the entire kitchen",
        accepted_content="Original household photos",
        prohibited_content="No people or private documents",
        licence="CC-BY-4.0",
        reuse_terms="Research reuse with attribution",
        keywords=["household"],
        labels=[
            Label(key="clean", name="Clean / organised"),
            Label(key="messy", name="Messy / dirty"),
        ],
        criteria=FormDefinition(
            questions=[
                Question(
                    key="condition",
                    title="How would you classify this kitchen?",
                    type="single_choice",
                    required=True,
                    options=["Clean", "Messy"],
                )
            ]
        ),
    )

    def make(value=definition, who=owner):
        with Session(engine) as s, s.begin():
            p = projects.create(s, s.get(User, who), value)
            return p.id, p.current_version

    def change(ident, state, who=owner):
        with Session(engine) as s, s.begin():
            return projects.transition(s, s.get(User, who), ident, state, 1).status

    def funds(who=owner):
        with Session(engine) as s:
            return auth.balance(s, s.get(User, who))

    first, version = make()
    second, _ = make()
    assert first != second and funds() == 50
    with Session(engine) as s, s.begin():
        p = projects.edit(s, s.get(User, owner), first, 1, definition)
        assert p.current_version == 2
    with Session(engine) as s, s.begin(), pytest.raises(auth.AuthError):
        projects.edit(s, s.get(User, owner), first, 1, definition)
    with Session(engine) as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(ProjectVersion)
                .where(ProjectVersion.project_id == first)
            )
            == 2
        )
    with pytest.raises(auth.AuthError):
        change(second, "published", other)
    assert change(second, "published") == "published" and funds() == 30
    assert change(second, "published") == "published" and funds() == 30
    assert change(second, "paused") == "paused" and funds() == 30
    assert change(second, "published") == "published" and funds() == 30
    with Session(engine) as s, s.begin(), pytest.raises(auth.AuthError):
        projects.edit(s, s.get(User, owner), second, 1, definition)
    with Session(engine) as s:
        page = projects.discover(s, "household", None, None, "relevance", 1, 1)
        assert page.total == 1 and page.items[0].id == second
        assert projects.discover(s, str(second), None, "published", "relevance", 1, 10).total == 1
        assert projects.discover(s, "", "environment", None, "newest", 1, 10).total == 0
        assert projects.discover(s, "%", None, None, "newest", 1, 10).total == 0
        assert projects.discover(s, "", None, None, "newest", 2, 1).items == []
    assert change(second, "closed") == "closed" and funds() == 50
    assert change(second, "closed") == "closed" and funds() == 50
    with pytest.raises(auth.AuthError):
        change(second, "published")
    expensive, _ = make(definition.model_copy(update={"image_count": 51}))
    with pytest.raises(auth.AuthError):
        change(expensive, "published")
    assert funds() == 50
    with Session(engine) as s:
        assert (
            s.scalar(select(ProjectReservation).where(ProjectReservation.project_id == expensive))
            is None
        )
    invalid, _ = make(ProjectDefinition(name="Incomplete draft"))
    with pytest.raises(auth.AuthError):
        change(invalid, "published")
    expired, _ = make(
        definition.model_copy(update={"closing_date": datetime.now(UTC).date() - timedelta(days=1)})
    )
    with pytest.raises(auth.AuthError):
        change(expired, "published")

    # Concurrent distinct publications compete for one wallet; only one can reserve 40.
    a, _ = make(definition.model_copy(update={"image_count": 40}))
    b, _ = make(definition.model_copy(update={"image_count": 40}))

    def race(ident):
        try:
            change(ident, "published")
            return ident
        except auth.AuthError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [p for p in pool.map(race, [a, b]) if p]
    assert len(winners) == 1 and funds() == 10
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: change(winners[0], "closed"), range(2))) == [
            "closed",
            "closed",
        ]
    assert funds() == 50
    with Session(engine) as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(CreditLedgerEntry)
                .where(CreditLedgerEntry.project_id == winners[0])
            )
            == 2
        )

    # Database commit guards reject bypasses and roll back all intermediate state.
    tamper, _ = make()
    with pytest.raises(DBAPIError), Session(engine) as s, s.begin():
        p = s.get(Project, tamper)
        p.status = "published"
        p.published_version = 1
    for query in [
        "UPDATE project_versions SET definition = '{}' WHERE project_id = :id",
        "DELETE FROM project_versions WHERE project_id = :id",
    ]:
        with pytest.raises(DBAPIError), engine.begin() as c:
            c.execute(text(query), {"id": tamper})
    with pytest.raises(DBAPIError), Session(engine) as s, s.begin():
        s.add(
            CreditLedgerEntry(
                user_id=owner,
                amount=-51,
                reason="synthetic debit",
                idempotency_key=secrets.token_hex(16),
            )
        )
    assert funds() == 50
    with pytest.raises(DBAPIError), Session(engine) as s, s.begin():
        s.add(
            CreditLedgerEntry(
                user_id=owner,
                project_id=tamper,
                amount=-20,
                reason="collection_reservation",
                idempotency_key=f"reservation:v1:{tamper}",
            )
        )
    assert funds() == 50
    with pytest.raises(DBAPIError), Session(engine) as s, s.begin():
        row = s.scalar(select(ProjectReservation).where(ProjectReservation.project_id == second))
        row.release_entry_id = None
    with pytest.raises(DBAPIError), Session(engine) as s, s.begin():
        p = s.get(Project, second)
        p.owner_id = other
    # Failure after a successful reserve must not commit its debit or state.
    rollback, _ = make()
    with pytest.raises(RuntimeError), Session(engine) as s, s.begin():
        projects.transition(s, s.get(User, owner), rollback, "published", 1)
        raise RuntimeError("Synthetic transaction failure")
    assert funds() == 50
    with Session(engine) as s:
        assert s.get(Project, rollback).status == "draft"

    # Real API auth/CSRF, private-draft visibility and public pages.
    with TestClient(create_app(settings)) as guest, TestClient(create_app(settings)) as client:
        public = guest.get("/api/v1/projects")
        assert public.status_code == 200
        assert public.headers["cache-control"] == "no-store"
        assert "cookie" in public.headers["vary"].lower()
        assert guest.get(f"/api/v1/projects/{first}").status_code == 404
        assert (
            guest.post(
                "/api/v1/projects",
                json=definition.model_dump(mode="json"),
                headers={"Origin": settings.frontend_url},
            ).status_code
            == 401
        )
        client.cookies.set("qpq_session", raw)
        client.cookies.set("qpq_csrf", csrf)
        headers = {"Origin": settings.frontend_url, "X-CSRF-Token": csrf}
        assert (
            client.post(
                "/api/v1/projects",
                json=definition.model_dump(mode="json"),
                headers={"Origin": settings.frontend_url},
            ).status_code
            == 403
        )
        response = client.post(
            "/api/v1/projects", json=definition.model_dump(mode="json"), headers=headers
        )
        assert response.status_code == 201
        ident = response.json()["id"]
        assert client.get("/api/v1/projects/mine").json()["total"] >= 1
        assert client.get(f"/api/v1/projects/{ident}").status_code == 200
        assert client.get("/api/v1/projects?page=0").status_code == 422
        assert (
            client.post(
                f"/api/v1/projects/{ident}/status",
                json={"status": "published", "expected_version": 1},
                headers=headers,
            ).status_code
            == 200
        )
        assert guest.get(f"/api/v1/projects/{ident}").status_code == 200
        wallet = client.get("/api/v1/auth/me").json()
        assert wallet["credit_balance"] == 30 and wallet["reserved_credits"] == 20
        assert (
            client.post(
                f"/api/v1/projects/{ident}/status",
                json={"status": "paused", "expected_version": 1},
                headers=headers,
            ).status_code
            == 200
        )
        assert guest.get("/api/v1/projects?status=paused").json()["total"] >= 1
        client.cookies.set("qpq_session", other_raw)
        headers["X-CSRF-Token"] = other_csrf
        assert (
            client.put(
                f"/api/v1/projects/{ident}",
                json={"expected_version": 1, "definition": definition.model_dump(mode="json")},
                headers=headers,
            ).status_code
            == 404
        )

    # Multiple result pages are stable and exclude drafts, even with similar names.
    for number in range(3):
        ident, _ = make(
            definition.model_copy(
                update={"name": f"Pagination kitchen {number}", "image_count": 10}
            )
        )
        change(ident, "published")
    with Session(engine) as s:
        one = projects.discover(s, "Pagination kitchen", "science", "published", "newest", 1, 2)
        two = projects.discover(s, "Pagination kitchen", "science", "published", "newest", 2, 2)
        assert one.total == two.total == 3 and len(one.items) == 2 and len(two.items) == 1
        assert not {p.id for p in one.items}.intersection(p.id for p in two.items)
        exact = projects.discover(s, "Pagination kitchen 1", None, None, "relevance", 1, 10)
        assert exact.items[0].definition.name == "Pagination kitchen 1"

    # Direct concurrent ledger writes also cannot overdraw the wallet.
    def direct_debit(_):
        try:
            with Session(engine) as s, s.begin():
                s.add(
                    CreditLedgerEntry(
                        user_id=other,
                        amount=-40,
                        reason="synthetic concurrency debit",
                        idempotency_key=secrets.token_hex(16),
                    )
                )
            return True
        except DBAPIError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(direct_debit, range(2))) == 1
    assert funds(other) == 10

    # A previously issued cookie cannot bypass current account eligibility.
    with Session(engine) as s, s.begin():
        s.get(User, other).email_verified_at = None
    with TestClient(create_app(settings)) as client:
        client.cookies.set("qpq_session", other_raw)
        response = client.post(
            "/api/v1/projects",
            json=definition.model_dump(mode="json"),
            headers={"Origin": settings.frontend_url, "X-CSRF-Token": other_csrf},
        )
        assert response.status_code == 403

    # Releases must match the original debit amount and owner, not just be positive.
    for wrong_amount, wrong_user in [(11, owner), (10, other)]:
        with pytest.raises(DBAPIError), Session(engine) as s, s.begin():
            p = s.get(Project, ident)
            reservation = s.scalar(
                select(ProjectReservation).where(ProjectReservation.project_id == ident)
            )
            release = CreditLedgerEntry(
                user_id=wrong_user,
                project_id=ident,
                amount=wrong_amount,
                reason="collection_release",
                idempotency_key=f"release:v1:{ident}",
                reversal_of_id=reservation.debit_entry_id,
            )
            s.add(release)
            s.flush()
            reservation.release_entry_id = release.id
            p.status = "closed"
    with Session(engine) as s:
        p = s.get(Project, ident)
        assert p.status == "published"
        reservation = s.scalar(
            select(ProjectReservation).where(ProjectReservation.project_id == ident)
        )
        assert reservation.release_entry_id is None and reservation.amount == 10

    with TestClient(create_app(settings.model_copy(update={"auth_enabled": False}))) as disabled:
        disabled.cookies.set("qpq_session", raw)
        assert disabled.get(f"/api/v1/projects/{first}").status_code == 404
        assert disabled.get(f"/api/v1/projects/{second}").status_code == 200
