"""Real PostgreSQL personal access, audit, zero-QC and owner/community concurrency."""

import io
import secrets
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

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
    ImageAnnotation,
    Project,
    RemovalRequest,
    Submission,
    User,
)
from app.main import create_app
from app.services import auth, dataset_exports
from app.services.dev_email import DEV_ISSUER


def exercise_owner_images(engine, monkeypatch, tmp_path):
    settings = Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        environment="development",
        dev_email_enabled=True,
        auth_enabled=True,
        uploads_enabled=True,
        datasets_enabled=True,
        storage_root=str(tmp_path / "images"),
        export_root=str(tmp_path / "exports"),
    )

    def actor(name):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with Session(engine) as s, s.begin():
            u = User(
                identity_issuer=DEV_ISSUER,
                identity_subject=name,
                email=name + "@university.test",
                email_verified_at=datetime.now(UTC),
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

    owner, community = actor("personal-owner"), actor("personal-community")
    app = create_app(settings)

    def login(c, who):
        c.cookies.set("qpq_session", who[1])
        c.headers.update({"Origin": settings.frontend_url, "X-CSRF-Token": who[2]})

    def definition(mode="personal", count=5):
        return {
            "mode": mode,
            "name": "Owner synthetic collection",
            "description": "Synthetic",
            "research_purpose": "Synthetic tests",
            "instructions": "No personal data",
            "accepted_content": "Squares",
            "prohibited_content": "Faces",
            "licence": "CC0-1.0",
            "reuse_terms": "CC0",
            "image_count": count,
            "min_width": 1,
            "min_height": 1,
            "allowed_formats": ["PNG"],
            "labels": [{"key": "round", "name": "Round"}, {"key": "square", "name": "Square"}],
            "criteria": {
                "schema_version": 1,
                "questions": [{"key": "note", "title": "Note", "type": "short_text"}],
            },
        }

    def body():
        return {
            "request_key": str(uuid.uuid4()),
            "criteria_version": 1,
            "label_key": "round",
            "answers": {"note": "Private owner note"},
            "consent": True,
            "privacy_acknowledgement": True,
        }

    def image(colour):
        out = io.BytesIO()
        Image.new("RGB", (32, 32), colour).save(out, "PNG")
        return out.getvalue()

    def ledger():
        with Session(engine) as s:
            return [
                (str(e.id), e.amount, e.reason, e.idempotency_key)
                for e in s.scalars(select(CreditLedgerEntry).order_by(CreditLedgerEntry.id))
            ]

    def start(c, p, b=None):
        return c.post(f"/api/v1/projects/{p}/submissions", json=b or body())

    def upload(c, s, colour="red"):
        return c.put(f"/api/v1/submissions/{s}/image", content=image(colour))

    with TestClient(app) as c, TestClient(app) as other, TestClient(app) as guest:
        login(c, owner)
        login(other, community)
        before = ledger()
        r = c.post("/api/v1/projects", json=definition())
        assert r.status_code == 201, r.text
        p = r.json()["id"]
        assert (
            r.json()["mode"] == "personal"
            and r.json()["visibility"] == "private"
            and r.json()["budget"] == 0
        )
        assert guest.get(f"/api/v1/projects/{p}").status_code == 404
        assert other.get(f"/api/v1/projects/{p}").status_code == 404
        assert start(other, p).status_code == 404
        assert p not in [x["id"] for x in guest.get("/api/v1/projects").json()["items"]]
        b = body()
        slot = start(c, p, b)
        assert slot.status_code == 201
        sid = slot.json()["id"]
        assert start(c, p, b).json()["id"] == sid
        row = upload(c, sid)
        assert row.status_code == 200, row.text
        assert (
            row.json()["source"] == "owner"
            and row.json()["status"] == "approved"
            and row.json()["qc_earned"] == 0
        )
        assert upload(c, sid).status_code == 200
        assert upload(c, sid, "blue").status_code == 409
        assert (
            c.post(f"/api/v1/moderation/{sid}/decision", json={"outcome": "approved"}).status_code
            == 404
        )
        assert other.get(f"/api/v1/submissions/{sid}/image").status_code == 404
        assert guest.get(f"/api/v1/projects/{p}/private-export").status_code == 401
        assert other.get(f"/api/v1/projects/{p}/private-export").status_code == 404
        assert other.get(f"/api/v1/projects/{p}/owner-images").status_code == 404
        export = c.get(f"/api/v1/projects/{p}/private-export")
        assert export.status_code == 200, export.text
        z = zipfile.ZipFile(io.BytesIO(export.content))
        assert z.testzip() is None
        assert b"Private owner note" in z.read("manifest.json")
        assert b"owner-provided" in z.read("manifest.json")
        edit = {
            "label_key": "square",
            "answers": {},
            "expected_hash": row.json()["annotation_hash"],
        }
        assert (
            c.patch(
                f"/api/v1/submissions/{sid}/labels", json={**edit, "label_key": "unknown"}
            ).status_code
            == 400
        )
        assert other.patch(f"/api/v1/submissions/{sid}/labels", json=edit).status_code == 404
        assert c.patch(f"/api/v1/submissions/{sid}/labels", json=edit).status_code == 200
        assert c.patch(f"/api/v1/submissions/{sid}/labels", json=edit).status_code == 409
        with Session(engine) as s:
            assert (
                s.scalar(
                    select(func.count())
                    .select_from(ImageAnnotation)
                    .where(ImageAnnotation.submission_id == uuid.UUID(sid))
                )
                == 1
            )
        for sql in [
            "UPDATE image_annotations SET version=2",
            "DELETE FROM image_annotations",
            "UPDATE submissions SET metadata_values='{\"forged\": true}' WHERE id=:id",
        ]:
            with pytest.raises(DBAPIError), engine.begin() as conn:
                conn.execute(text(sql), {"id": sid})
        assert ledger() == before
        from app.services import personal_exports

        with monkeypatch.context() as patch:
            patch.setattr(personal_exports, "MAX_PRIVATE_BYTES", 1024)
            assert c.get(f"/api/v1/projects/{p}/private-export").status_code == 413
        pub = c.post(
            f"/api/v1/projects/{p}/dataset",
            json={
                "criteria_version": 1,
                "public_fields": [],
                "distribution_authorised": True,
                "privacy_reviewed": True,
            },
        ).json()["id"]
        consent = c.post(
            f"/api/v1/submissions/{sid}/export-consent",
            json={"publication_id": pub, "agree_public_distribution": True},
        )
        assert consent.status_code == 200, consent.text
        assert (
            c.post(
                f"/api/v1/datasets/{pub}/images/{sid}/authorise",
                json={
                    "consent_id": consent.json()["id"],
                    "distribution_authorised": True,
                    "privacy_reviewed": True,
                },
            ).status_code
            == 204
        )
        assert c.post(f"/api/v1/datasets/{pub}/versions").status_code == 200
        assert dataset_exports.run_one(engine, settings)
        public = guest.get(f"/api/v1/datasets/{pub}/versions/1/download")
        assert public.status_code == 200
        assert b"owner-provided" in zipfile.ZipFile(io.BytesIO(public.content)).read(
            "manifest.json"
        )
        assert ledger() == before
        current = c.get(f"/api/v1/submissions/{sid}").json()
        assert (
            c.patch(
                f"/api/v1/submissions/{sid}/labels",
                json={
                    "label_key": "round",
                    "answers": {},
                    "expected_hash": current["annotation_hash"],
                },
            ).status_code
            == 409
        )
        assert start(other, p).status_code == 404  # Public does not enable community capture.
        assert (
            c.post(
                f"/api/v1/submissions/{sid}/removal-request", json={"reason": "privacy"}
            ).status_code
            == 200
        )
        assert guest.get(f"/api/v1/datasets/{pub}/versions/1/download").status_code == 410
        assert c.get(f"/api/v1/projects/{p}/private-export").status_code == 409
        # A terminal project never reopens or recreates a reservation.
        assert (
            c.post(
                f"/api/v1/projects/{p}/status", json={"status": "closed", "expected_version": 1}
            ).status_code
            == 200
        )
        assert start(c, p).status_code == 409
        assert ledger() == before

        # Same-target owner/community allocations must serialize on the project.
        def crowdsourced(count):
            project = c.post("/api/v1/projects", json=definition("crowdsourced", count)).json()[
                "id"
            ]
            assert (
                c.post(
                    f"/api/v1/projects/{project}/status",
                    json={"status": "published", "expected_version": 1},
                ).status_code
                == 200
            )
            return project

        q = crowdsourced(1)
        barrier = Barrier(2)

        def race(who):
            with TestClient(create_app(settings)) as client:
                login(client, who)
                barrier.wait()
                return start(client, q)

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(race, [owner, community]))
        assert sorted(x.status_code for x in results) == [201, 409]
        # Idempotent same-key allocation under contention returns a single row.
        q2 = crowdsourced(2)
        barrier = Barrier(2)
        same = body()

        def retry(_):
            with TestClient(create_app(settings)) as client:
                login(client, owner)
                barrier.wait()
                return start(client, q2, same)

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(retry, range(2)))
        assert all(x.status_code == 201 for x in results)
        assert results[0].json()["id"] == results[1].json()["id"]
        owner_slot = results[0].json()["id"]
        community_slot = start(other, q2).json()["id"]
        assert upload(other, community_slot, "green").status_code == 200
        assert start(c, q2).status_code == 409  # Cannot displace pending funded submission.
        assert (
            c.post(
                f"/api/v1/projects/{q2}/status", json={"status": "paused", "expected_version": 1}
            ).status_code
            == 200
        )
        barrier = Barrier(2)

        def complete(which):
            with TestClient(create_app(settings)) as client:
                login(client, owner)
                barrier.wait()
                return (
                    upload(client, owner_slot, "blue")
                    if which == 0
                    else client.post(
                        f"/api/v1/moderation/{community_slot}/decision",
                        json={"outcome": "approved"},
                    )
                )

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(complete, range(2)))
        assert all(x.status_code == 200 for x in results), [x.status_code for x in results]
        assert c.get(f"/api/v1/projects/{q2}").json()["owner_images"] == 1
        assert c.get(f"/api/v1/projects/{q2}").json()["community_images"] == 1
        assert (
            c.post(
                f"/api/v1/projects/{q2}/status", json={"status": "closed", "expected_version": 1}
            ).status_code
            == 200
        )
        with Session(engine) as s:
            entries = s.scalars(
                select(CreditLedgerEntry).where(CreditLedgerEntry.project_id == uuid.UUID(q2))
            ).all()
            assert sorted((e.reason, e.amount) for e in entries) == [
                ("collection_release", 1),
                ("collection_reservation", -2),
                ("collection_reward", 1),
            ]
            assert (
                next(e for e in entries if e.reason == "collection_reward").user_id == community[0]
            )
            assert s.get(Project, uuid.UUID(p)).mode == "personal"
            assert s.get(Submission, uuid.UUID(owner_slot)).status == "approved"

        # Owner suppression frees a slot, but never releases a pending contributor's QC.
        q3 = crowdsourced(2)
        own3 = start(c, q3).json()["id"]
        assert upload(c, own3, "red").status_code == 200
        comm3 = start(other, q3).json()["id"]
        assert upload(other, comm3, "blue").status_code == 200
        assert (
            c.post(
                f"/api/v1/submissions/{own3}/removal-request", json={"reason": "privacy"}
            ).status_code
            == 200
        )
        comm4 = start(other, q3).json()["id"]
        assert upload(other, comm4, "green").status_code == 200
        for ident in [comm3, comm4]:
            assert (
                c.post(
                    f"/api/v1/moderation/{ident}/decision", json={"outcome": "approved"}
                ).status_code
                == 200
            )
        assert (
            c.post(
                f"/api/v1/projects/{q3}/status", json={"status": "closed", "expected_version": 1}
            ).status_code
            == 200
        )
        with Session(engine) as s:
            entries = s.scalars(
                select(CreditLedgerEntry).where(CreditLedgerEntry.project_id == uuid.UUID(q3))
            ).all()
            assert sorted(e.amount for e in entries) == [-2, 1, 1]
        # Failed storage does not create an owner image, status change or credit entry.
        personal = c.post("/api/v1/projects", json=definition()).json()["id"]
        failure = start(c, personal).json()["id"]
        before = ledger()
        from app.integrations.storage import LocalObjectStore

        with monkeypatch.context() as patch:

            def fail(*args):
                raise OSError("Synthetic owner storage failure")

            patch.setattr(LocalObjectStore, "put", fail)
            assert upload(c, failure).status_code == 503
        assert c.get(f"/api/v1/submissions/{failure}").json()["status"] == "uploading"
        assert ledger() == before
        assert upload(c, failure).status_code == 200
        assert ledger() == before
        # Closure versus an owner completion serialises; a live slot cannot lose funding.
        q4 = crowdsourced(1)
        own4 = start(c, q4).json()["id"]
        barrier = Barrier(2)

        def closing(which):
            with TestClient(create_app(settings)) as client:
                login(client, owner)
                barrier.wait()
                return (
                    upload(client, own4, "red")
                    if which == 0
                    else client.post(
                        f"/api/v1/projects/{q4}/status",
                        json={"status": "closed", "expected_version": 1},
                    )
                )

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(closing, range(2)))
        assert results[0].status_code == 200
        assert results[1].status_code in {200, 409}
        assert (
            c.post(
                f"/api/v1/projects/{q4}/status", json={"status": "closed", "expected_version": 1}
            ).status_code
            == 200
        )
        assert start(c, q4).status_code == 409

        # A raw removal restriction also interrupts a private archive, without
        # depending on the UI having already populated the hidden flag.
        restricted = c.post("/api/v1/projects", json=definition()).json()["id"]
        restricted_image = start(c, restricted).json()["id"]
        assert upload(c, restricted_image).status_code == 200
        original_generate = personal_exports.generate
        with monkeypatch.context() as patch:

            def interrupted(*args):
                source, size, signatures = original_generate(*args)

                class RestrictedStream:
                    changed = False

                    def read(self, amount):
                        data = source.read(16)
                        if not self.changed:
                            self.changed = True
                            with Session(engine) as s, s.begin():
                                s.add(
                                    RemovalRequest(
                                        submission_id=uuid.UUID(restricted_image),
                                        reporter_id=owner[0],
                                        reason="privacy",
                                        details="Synthetic restriction",
                                    )
                                )
                        return data

                    def close(self):
                        source.close()

                return RestrictedStream(), size, signatures

            patch.setattr(personal_exports, "generate", interrupted)
            interrupted_zip = c.get(f"/api/v1/projects/{restricted}/private-export")
            assert len(interrupted_zip.content) == 16
            with pytest.raises(zipfile.BadZipFile):
                zipfile.ZipFile(io.BytesIO(interrupted_zip.content))
        assert c.get(f"/api/v1/submissions/{restricted_image}/image").status_code == 404
        assert c.get(f"/api/v1/projects/{restricted}/private-export").status_code == 409

        # A verified owner with zero available QC can still create and repeatedly
        # capture into a personal collection; the community 20-image cap does not apply.
        available = c.get("/api/v1/auth/me").json()["credit_balance"]
        assert available > 0
        crowdsourced(available)
        assert c.get("/api/v1/auth/me").json()["credit_balance"] == 0
        zero_before = ledger()
        zero_personal = c.post("/api/v1/projects", json=definition("personal", 25))
        assert zero_personal.status_code == 201
        zero_id = zero_personal.json()["id"]
        for number in range(21):
            slot = start(c, zero_id)
            assert slot.status_code == 201
            assert upload(c, slot.json()["id"], (number, 120, 180)).status_code == 200
        assert c.get(f"/api/v1/projects/{zero_id}").json()["owner_images"] == 21
        assert c.get("/api/v1/auth/me").json()["credit_balance"] == 0
        assert ledger() == zero_before
