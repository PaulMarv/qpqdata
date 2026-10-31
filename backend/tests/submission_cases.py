import io
import os
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AuthSession,
    CreditLedgerEntry,
    Project,
    ProjectReservation,
    Submission,
    User,
)
from app.integrations.storage import LocalObjectStore
from app.jobs.upload_cleanup import cleanup
from app.main import create_app
from app.schemas.projects import FormDefinition, Label, ProjectDefinition, Question
from app.services import auth, projects
from app.services.dev_email import DEV_ISSUER


def exercise_submissions(engine, monkeypatch, tmp_path):
    settings = Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        environment="development",
        dev_email_enabled=True,
        auth_enabled=True,
        uploads_enabled=True,
        storage_root=str(tmp_path),
    )

    def actor(prefix):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with Session(engine) as s, s.begin():
            user = User(
                identity_issuer=DEV_ISSUER,
                identity_subject=prefix,
                email=prefix + "@university.test",
                email_verified_at=datetime.now(UTC),
            )
            s.add(user)
            s.flush()
            auth.grant_welcome(s, user, settings)
            s.add(
                AuthSession(
                    user_id=user.id,
                    token_hash=auth.digest(token),
                    csrf_hash=auth.digest(csrf),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    last_seen_at=datetime.now(UTC),
                )
            )
            return user.id, token, csrf

    owner, owner_token, owner_csrf = actor("upload-owner")
    contributor, token, csrf = actor("upload-contributor")
    other, other_token, other_csrf = actor("upload-other")
    d = ProjectDefinition(
        name="Synthetic photo study",
        description="Synthetic scenes",
        research_purpose="Testing",
        instructions="Original scenes",
        accepted_content="Scenes",
        prohibited_content="Personal data",
        licence="CC0-1.0",
        reuse_terms="Research",
        min_width=8,
        min_height=8,
        image_count=3,
        labels=[Label(key="scene", name="Scene")],
        criteria=FormDefinition(
            questions=[
                Question(
                    key="condition",
                    title="Condition",
                    type="single_choice",
                    required=True,
                    options=["Clean", "Messy"],
                )
            ]
        ),
    )

    def project(count=3):
        with Session(engine) as s, s.begin():
            p = projects.create(s, s.get(User, owner), d.model_copy(update={"image_count": count}))
            projects.transition(s, s.get(User, owner), p.id, "published", 1)
            return p.id

    pid = project()

    def body():
        return {
            "request_key": str(uuid.uuid4()),
            "criteria_version": 1,
            "label_key": "scene",
            "answers": {"condition": "Clean"},
            "consent": True,
            "privacy_acknowledgement": True,
        }

    def photo(color="red"):
        out = io.BytesIO()
        Image.new("RGB", (16, 16), color).save(out, "PNG")
        return out.getvalue()

    with TestClient(create_app(settings)) as client, TestClient(create_app(settings)) as guest:
        client.cookies.set("qpq_session", token)
        headers = {"Origin": settings.frontend_url, "X-CSRF-Token": csrf}
        url = f"/api/v1/projects/{pid}/submissions"
        assert (
            guest.post(url, json=body(), headers={"Origin": settings.frontend_url}).status_code
            == 401
        )
        assert (
            client.post(url, json=body(), headers={"Origin": settings.frontend_url}).status_code
            == 403
        )
        for invalid in [
            {"criteria_version": 2},
            {"label_key": "unknown"},
            {"answers": {}},
            {"answers": {"condition": "No"}},
            {"consent": False},
            {"status": "approved"},
        ]:
            assert client.post(url, json={**body(), **invalid}, headers=headers).status_code in {
                400,
                409,
                422,
            }
        manifest = body()
        r = client.post(url, json=manifest, headers=headers)
        assert r.status_code == 201
        r = r.json()
        ident = r["id"]
        image_url = f"/api/v1/submissions/{ident}/image"
        assert r["status"] == "uploading" and r["criteria_version"] == 1
        assert client.post(url, json=manifest, headers=headers).json()["id"] == ident
        assert (
            client.post(
                url, json={**manifest, "answers": {"condition": "Messy"}}, headers=headers
            ).status_code
            == 409
        )
        assert client.put(image_url, content=b"bad", headers=headers).status_code == 400
        assert (
            client.put(
                image_url,
                content=b"x",
                headers={**headers, "Content-Length": str(10 * 1024 * 1024 + 1)},
            ).status_code
            == 413
        )
        assert (
            client.post(
                url, content=b"x" * 65537, headers={**headers, "Content-Type": "application/json"}
            ).status_code
            == 413
        )
        assert client.get(f"/api/v1/submissions/{ident}").json()["status"] == "uploading"
        with monkeypatch.context() as patch:

            def fail(*_):
                raise OSError("Synthetic storage failure")

            patch.setattr(LocalObjectStore, "put", fail)
            assert client.put(image_url, content=photo(), headers=headers).status_code == 503
        assert client.put(image_url, content=photo(), headers=headers).status_code == 200
        assert client.put(image_url, content=photo(), headers=headers).json()["id"] == ident
        assert client.put(image_url, content=photo("blue"), headers=headers).status_code == 409
        assert guest.get(image_url).status_code == 401
        assert client.get(image_url).headers["content-type"] == "image/png"
        assert (
            client.get(f"/api/v1/submissions/{ident}").json()["consent_record"]["licence"]
            == "CC0-1.0"
        )
        client.cookies.set("qpq_session", other_token)
        assert client.get(image_url).status_code == 404
        assert client.get(f"/api/v1/submissions/{ident}").status_code == 404
        assert (
            client.put(
                image_url, content=photo(), headers={**headers, "X-CSRF-Token": other_csrf}
            ).status_code
            == 404
        )
        client.cookies.set("qpq_session", owner_token)
        assert (
            client.post(
                url, json=body(), headers={**headers, "X-CSRF-Token": owner_csrf}
            ).status_code
            == 403
        )
        client.cookies.set("qpq_session", token)
        duplicate = client.post(url, json=body(), headers=headers).json()["id"]
        assert (
            client.put(
                f"/api/v1/submissions/{duplicate}/image", content=photo(), headers=headers
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/submissions/{duplicate}/cancel", json={}, headers=headers
            ).status_code
            == 200
        )
        # Pending images prevent closing/releasing reserved funding; pause and resume work.
        with Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner), pid, "paused", 1)
        assert client.post(url, json=body(), headers=headers).status_code == 409
        with Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner), pid, "published", 1)
        with pytest.raises(auth.AuthError), Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner), pid, "closed", 1)
        assert client.get("/api/v1/submissions?page_size=1").json()["total"] == 2
        # Removal pathway suppresses object access immediately, without payouts/decisions.
        assert (
            client.post(
                f"/api/v1/submissions/{ident}/removal-request",
                json={"reason": "privacy", "details": "Synthetic request"},
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/submissions/{ident}/removal-request",
                json={"reason": "privacy"},
                headers=headers,
            ).status_code
            == 200
        )
        assert client.get(image_url).status_code == 404
        # One remaining collection slot and two concurrent contributors: no overbooking.
        capacity_pid = project(1)

        def reserve(who):
            tok, cs = who
            with TestClient(create_app(settings)) as c:
                c.cookies.set("qpq_session", tok)
                return c.post(
                    f"/api/v1/projects/{capacity_pid}/submissions",
                    json=body(),
                    headers={"Origin": settings.frontend_url, "X-CSRF-Token": cs},
                ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(reserve, [(token, csrf), (other_token, other_csrf)])) == [
                201,
                409,
            ]

        # Upload lease expiry, cleanup and recoverable capacity use a controlled test clock.
        class Later(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(minutes=16)

        slot = client.post(url, json=body(), headers=headers).json()["id"]
        with monkeypatch.context() as patch:
            patch.setattr("app.services.submissions.datetime", Later)
            assert (
                client.put(
                    f"/api/v1/submissions/{slot}/image", content=photo("green"), headers=headers
                ).status_code
                == 410
            )
            patch.setattr("app.jobs.upload_cleanup.datetime", Later)
            expired, _ = cleanup(engine, str(tmp_path))
            assert expired >= 2
        # Orphan sweep removes only old unreferenced sanitized objects.
        orphan = f"objects/{uuid.UUID(ident).hex}/{uuid.uuid4().hex}.png"
        store = LocalObjectStore(str(tmp_path))
        store.put(orphan, photo())
        os.utime(store.path(orphan), (0, 0))
        with Session(engine) as s:
            referenced = s.get(Submission, uuid.UUID(ident)).object_key
        _, removed = cleanup(engine, str(tmp_path))
        assert removed == 1 and not store.path(orphan).exists()
        assert not store.path(
            referenced
        ).exists()  # Phase 2D purges suppressed bytes; keeps audit rows.
        assert client.post(url, json=body(), headers=headers).status_code == 201
        # Closing with an exact ledger refund still cannot release pending funding.
        with pytest.raises(DBAPIError), Session(engine) as s, s.begin():
            reservation = s.scalar(
                select(ProjectReservation).where(ProjectReservation.project_id == pid)
            )
            release = CreditLedgerEntry(
                user_id=owner,
                project_id=pid,
                amount=reservation.amount,
                reason="collection_release",
                idempotency_key=f"release:v1:{pid}",
                reversal_of_id=reservation.debit_entry_id,
            )
            s.add(release)
            s.flush()
            reservation.release_entry_id = release.id
            s.get(Project, pid).status = "closed"
        # SQL guards prohibit moderation or changing submitted provenance.
        for sql in [
            "UPDATE submissions SET status='approved' WHERE id=:id",
            "UPDATE submissions SET status='rejected' WHERE id=:id",
            "UPDATE submissions SET metadata_values='{}' WHERE id=:id",
            "UPDATE submissions SET content_hash='bad' WHERE id=:id",
            "DELETE FROM submissions WHERE id=:id",
        ]:
            with pytest.raises(DBAPIError), engine.begin() as c:
                c.execute(text(sql), {"id": ident})
        with Session(engine) as s:
            assert s.get(Submission, uuid.UUID(ident)).status == "pending"
            assert (
                s.scalar(
                    select(ProjectReservation).where(ProjectReservation.project_id == pid)
                ).release_entry_id
                is None
            )
            assert not s.scalar(
                select(CreditLedgerEntry).where(
                    CreditLedgerEntry.user_id == contributor,
                    CreditLedgerEntry.reason != "welcome_grant",
                )
            )

        # Twenty completed images per contributor, independently of collection capacity.
        limit_pid = project(21)
        for index in range(20):
            slot = client.post(
                f"/api/v1/projects/{limit_pid}/submissions", json=body(), headers=headers
            )
            assert slot.status_code == 201
            result = client.put(
                f"/api/v1/submissions/{slot.json()['id']}/image",
                content=photo((index, 40, 80)),
                headers=headers,
            )
            assert result.status_code == 200
        limited = client.post(
            f"/api/v1/projects/{limit_pid}/submissions", json=body(), headers=headers
        )
        assert limited.status_code == 409 and "20-image" in limited.json()["detail"]
        # Active upload slots have their own smaller bound; discards free capacity.
        lease_pid = project(6)
        slots = []
        for _ in range(5):
            response = client.post(
                f"/api/v1/projects/{lease_pid}/submissions", json=body(), headers=headers
            )
            assert response.status_code == 201
            slots.append(response.json()["id"])
        assert (
            client.post(
                f"/api/v1/projects/{lease_pid}/submissions", json=body(), headers=headers
            ).status_code
            == 409
        )
        for slot in slots:
            assert (
                client.post(
                    f"/api/v1/submissions/{slot}/cancel", json={}, headers=headers
                ).status_code
                == 200
            )
        with Session(engine) as s, s.begin():
            projects.transition(s, s.get(User, owner), lease_pid, "closed", 1)
        assert (
            client.post(
                f"/api/v1/projects/{lease_pid}/submissions", json=body(), headers=headers
            ).status_code
            == 409
        )
        # Eligibility is rechecked even with a previously issued contributor session.
        with Session(engine) as s, s.begin():
            s.get(User, contributor).email_verified_at = None
        assert client.post(url, json=body(), headers=headers).status_code == 403
