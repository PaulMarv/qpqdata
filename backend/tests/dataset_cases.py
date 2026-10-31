"""Real PostgreSQL dataset permissions, ZIP reproducibility, races and zero-QC downloads."""

import csv
import io
import json
import secrets
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AuthSession,
    CreditLedgerEntry,
    DatasetBuild,
    DatasetPublication,
    DatasetVersion,
    Submission,
    User,
)
from app.integrations.exports import ExportStore
from app.main import create_app
from app.schemas.projects import FormDefinition, Label, ProjectDefinition, Question
from app.services import auth, dataset_exports, datasets, projects
from app.services.dev_email import DEV_ISSUER


def exercise_datasets(engine, monkeypatch, tmp_path):
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

    owner, contributor, other = [actor("dataset-" + x) for x in ["owner", "contributor", "other"]]

    def headers(who):
        return {"Origin": settings.frontend_url, "X-CSRF-Token": who[2]}

    def login(c, who):
        c.cookies.set("qpq_session", who[1])

    d = ProjectDefinition(
        name="Public synthetic scenes",
        description="Synthetic fixtures",
        research_purpose="Testing datasets",
        instructions="Original",
        accepted_content="Scenes",
        prohibited_content="Private data",
        licence="CC0-1.0",
        reuse_terms="Open reuse",
        image_count=5,
        min_width=8,
        min_height=8,
        labels=[Label(key="scene", name="Scene")],
        criteria=FormDefinition(
            questions=[
                Question(
                    key="kind",
                    title="Kind",
                    type="single_choice",
                    required=True,
                    options=["Normal", "=formula"],
                ),
                Question(key="count", title="Count", type="number"),
                Question(key="yes", title="Yes?", type="yes_no"),
                Question(key="private", title="Private note", type="short_text"),
            ]
        ),
    )

    def project(licence="CC0-1.0"):
        with Session(engine) as s, s.begin():
            p = projects.create(s, s.get(User, owner[0]), d.model_copy(update={"licence": licence}))
            projects.transition(s, s.get(User, owner[0]), p.id, "published", 1)
            return p.id

    pid = project()
    policy = {
        "criteria_version": 1,
        "public_fields": ["kind", "count", "yes"],
        "distribution_authorised": True,
        "privacy_reviewed": True,
    }
    with TestClient(create_app(settings)) as c, TestClient(create_app(settings)) as public:

        def upload(color, pid=pid):
            login(c, contributor)
            body = {
                "request_key": str(uuid.uuid4()),
                "criteria_version": 1,
                "label_key": "scene",
                "answers": {
                    "kind": "=formula",
                    "count": 2,
                    "yes": False,
                    "private": "private-account@example.test",
                },
                "consent": True,
                "privacy_acknowledgement": True,
            }
            r = c.post(
                f"/api/v1/projects/{pid}/submissions", json=body, headers=headers(contributor)
            )
            assert r.status_code == 201, r.text
            ident = uuid.UUID(r.json()["id"])
            b = io.BytesIO()
            meta = PngImagePlugin.PngInfo()
            meta.add_text("GPS", "private coordinates")
            Image.new("RGB", (32, 24), color).save(b, "PNG", pnginfo=meta)
            assert (
                c.put(
                    f"/api/v1/submissions/{ident}/image",
                    content=b.getvalue(),
                    headers=headers(contributor),
                ).status_code
                == 200
            )
            return ident

        def approve(ident, reject=False):
            login(c, owner)
            r = c.post(
                f"/api/v1/moderation/{ident}/decision",
                json={
                    "outcome": "rejected" if reject else "approved",
                    "reason": "Not suitable" if reject else "",
                },
                headers=headers(owner),
            )
            assert r.status_code == 200, r.text

        a, b, rejected = [upload(color) for color in ["red", "green", "blue"]]
        approve(a)
        approve(rejected, True)
        assert public.get("/api/v1/datasets").json()["total"] == 0
        assert (
            public.post(
                f"/api/v1/projects/{pid}/dataset",
                json=policy,
                headers={"Origin": settings.frontend_url},
            ).status_code
            == 401
        )
        login(c, other)
        assert (
            c.post(
                f"/api/v1/projects/{pid}/dataset", json=policy, headers=headers(other)
            ).status_code
            == 404
        )
        login(c, owner)
        for invalid in [
            {"public_fields": ["private"]},
            {"privacy_reviewed": False},
            {"criteria_version": 2},
        ]:
            assert c.post(
                f"/api/v1/projects/{pid}/dataset",
                json={**policy, **invalid},
                headers=headers(owner),
            ).status_code in {400, 409, 422}
        response = c.post(f"/api/v1/projects/{pid}/dataset", json=policy, headers=headers(owner))
        assert response.status_code == 200, response.text
        pub_id = response.json()["id"]
        assert (
            c.post(f"/api/v1/datasets/{pub_id}/versions", headers=headers(owner)).status_code == 409
        )
        assert c.get(f"/api/v1/datasets/{pub_id}/review").status_code == 200
        login(c, other)
        assert c.get(f"/api/v1/datasets/{pub_id}/review").status_code == 404
        assert c.get(f"/api/v1/submissions/{a}/export-consent").status_code == 404

        def consent(ident, pub=pub_id, alias=""):
            login(c, contributor)
            return c.post(
                f"/api/v1/submissions/{ident}/export-consent",
                json={
                    "publication_id": pub,
                    "agree_public_distribution": True,
                    "public_attribution": alias,
                },
                headers=headers(contributor),
            )

        assert consent(rejected).status_code == 409
        grants = {}
        for ident in [a, b]:
            r = consent(ident)
            assert r.status_code == 200, r.text
            grants[ident] = r.json()["id"]

        def authorise(ident, pub=pub_id):
            login(c, owner)
            return c.post(
                f"/api/v1/datasets/{pub}/images/{ident}/authorise",
                json={
                    "consent_id": grants[ident],
                    "distribution_authorised": True,
                    "privacy_reviewed": True,
                },
                headers=headers(owner),
            )

        assert authorise(b).status_code == 409  # Pending cannot be exported
        assert authorise(a).status_code == 204
        login(c, owner)
        r = c.post(f"/api/v1/datasets/{pub_id}/versions", headers=headers(owner))
        assert r.status_code == 200, r.text
        assert r.json()["version"] == 1 and r.json()["image_count"] == 1
        gate = Barrier(2)

        def same_snapshot(_):
            with Session(engine) as s, s.begin():
                gate.wait(5)
                return datasets.snapshot(s, s.get(DatasetPublication, uuid.UUID(pub_id))).id

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert len(set(pool.map(same_snapshot, range(2)))) == 1
        gate = Barrier(2)

        def build(_):
            gate.wait(5)
            return dataset_exports.run_one(engine, settings)

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sum(pool.map(build, range(2))) == 1
        with Session(engine) as s:
            ledger_before = [
                tuple(row)
                for row in s.execute(
                    select(CreditLedgerEntry.__table__).order_by(CreditLedgerEntry.id)
                )
            ]
        url = f"/api/v1/datasets/{pub_id}/versions/1/download"
        download = public.get(url)
        assert download.status_code == 200 and download.headers["cache-control"] == "no-store"
        original_zip = download.content
        with zipfile.ZipFile(io.BytesIO(original_zip)) as z:
            assert z.testzip() is None
            assert {"labels.csv", "manifest.json", "README.md", "LICENSE.txt"} <= set(z.namelist())
            manifest = json.loads(z.read("manifest.json"))
            assert manifest["image_count"] == 1 and manifest["dataset_version"] == 1
            assert (
                len(manifest["images"]) == 1 and "private" not in manifest["images"][0]["answers"]
            )
            file = manifest["images"][0]["file"]
            assert file.startswith("images/") and ".." not in file
            with Image.open(io.BytesIO(z.read(file))) as image:
                assert not image.info and not image.getexif()
            csv_rows = list(csv.DictReader(io.StringIO(z.read("labels.csv").decode())))
            assert csv_rows[0]["kind"] == "'=formula" and csv_rows[0]["yes"] == "false"
            for name in ["manifest.json", "labels.csv", "README.md"]:
                content = z.read(name).decode()
                assert (
                    "@university.test" not in content
                    and "private-account" not in content
                    and "objects/" not in content
                )
            assert "CC0" in z.read("LICENSE.txt").decode()
        # No ledger entry changes at all, including when a signed-in user downloads.
        login(c, contributor)
        assert c.get(url).status_code == 200
        with Session(engine) as s:
            assert [
                tuple(row)
                for row in s.execute(
                    select(CreditLedgerEntry.__table__).order_by(CreditLedgerEntry.id)
                )
            ] == ledger_before
        # Expired cache is inaccessible; regeneration preserves exact ZIP and manifest.
        with Session(engine) as s, s.begin():
            v = s.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.publication_id == uuid.UUID(pub_id), DatasetVersion.version == 1
                )
            )
            version_id = v.id
            build = s.scalar(select(DatasetBuild).where(DatasetBuild.version_id == v.id))
            build.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        assert public.get(url).status_code == 410
        assert (
            public.post(
                f"/api/v1/datasets/{pub_id}/versions/1/prepare",
                headers={"Origin": settings.frontend_url},
            ).status_code
            == 200
        )
        assert dataset_exports.run_one(engine, settings)
        assert public.get(url).content == original_zip
        # Missing cache files can be recovered without changing the version.
        with Session(engine) as s:
            cache = s.scalar(select(DatasetBuild).where(DatasetBuild.version_id == version_id))
            ExportStore(settings.export_root).delete(cache.artifact_key)
        assert public.get(url).status_code == 410
        assert (
            public.post(
                f"/api/v1/datasets/{pub_id}/versions/1/prepare",
                headers={"Origin": settings.frontend_url},
            ).status_code
            == 200
        )
        assert dataset_exports.run_one(engine, settings)
        assert public.get(url).content == original_zip
        approve(b)
        assert authorise(b).status_code == 204
        login(c, owner)
        r = c.post(f"/api/v1/datasets/{pub_id}/versions", headers=headers(owner))
        assert r.json()["version"] == 2 and r.json()["image_count"] == 2
        assert dataset_exports.run_one(engine, settings)
        assert public.get(url).content == original_zip
        results = public.get(
            "/api/v1/datasets",
            params={
                "q": str(pid),
                "page_size": 1,
                "category": "other",
                "licence": "CC0-1.0",
                "sort": "relevance",
            },
        ).json()
        assert results["total"] == 1 and len(results["items"]) == 1
        assert public.get("/api/v1/datasets", params={"q": "absent"}).json()["total"] == 0
        # Manifest and snapshot membership cannot be silently edited.
        for sql in [
            "UPDATE dataset_versions SET manifest='{}' WHERE id=:id",
            "UPDATE dataset_versions SET archive_sha256='bad' WHERE id=:id",
            "DELETE FROM dataset_members WHERE version_id=:id",
            "UPDATE dataset_members SET annotations='{}' WHERE version_id=:id",
        ]:
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(text(sql), {"id": version_id})
        # Restriction during an active stream halts subsequent chunks. Previously
        # downloaded copies remain local; a partial ZIP cannot be used as a dataset.
        real_check = dataset_exports.check
        checks = 0

        def restrict_during_stream(db, version_id):
            nonlocal checks
            checks += 1
            if checks == 2:
                login(c, contributor)
                assert (
                    c.post(
                        f"/api/v1/submissions/{a}/removal-request",
                        json={"reason": "privacy"},
                        headers=headers(contributor),
                    ).status_code
                    == 200
                )
            return real_check(db, version_id)

        with monkeypatch.context() as patch:
            patch.setattr(dataset_exports, "CHUNK", 16)
            patch.setattr(dataset_exports, "check", restrict_during_stream)
            partial = public.get(url)
            assert len(partial.content) < int(partial.headers["content-length"])
            with pytest.raises(zipfile.BadZipFile):
                zipfile.ZipFile(io.BytesIO(partial.content))
        assert public.get(url).status_code == 410
        assert public.get(f"/api/v1/datasets/{pub_id}/versions/2/download").status_code == 410
        login(c, owner)
        r = c.post(f"/api/v1/datasets/{pub_id}/versions", headers=headers(owner))
        assert r.json()["version"] == 3 and r.json()["image_count"] == 1
        # A concurrent removal inside generation cannot publish a ready artifact.
        real = dataset_exports.canonical_image

        def remove_during(data):
            login(c, contributor)
            assert (
                c.post(
                    f"/api/v1/submissions/{b}/removal-request",
                    json={"reason": "copyright"},
                    headers=headers(contributor),
                ).status_code
                == 200
            )
            return real(data)

        with monkeypatch.context() as patch:
            patch.setattr(dataset_exports, "canonical_image", remove_during)
            assert dataset_exports.run_one(engine, settings)
        assert public.get(f"/api/v1/datasets/{pub_id}/versions/3/download").status_code == 410
        with Session(engine) as s:
            assert all(
                v.revoked_at
                for v in s.scalars(
                    select(DatasetVersion).where(DatasetVersion.publication_id == uuid.UUID(pub_id))
                )
            )
        # Licence gates: custom rejected; BY requires deliberate public attribution.
        custom = project("custom")
        login(c, owner)
        assert (
            c.post(
                f"/api/v1/projects/{custom}/dataset", json=policy, headers=headers(owner)
            ).status_code
            == 400
        )
        by = project("CC-BY-4.0")
        login(c, owner)
        bypub = c.post(
            f"/api/v1/projects/{by}/dataset", json=policy, headers=headers(owner)
        ).json()["id"]
        image = upload("purple", by)
        approve(image)
        assert consent(image, bypub).status_code == 400
        r = consent(image, bypub, "Research Photo 1")
        assert r.status_code == 200
        grants[image] = r.json()["id"]
        assert authorise(image, bypub).status_code == 204
        login(c, owner)
        assert (
            c.post(f"/api/v1/datasets/{bypub}/versions", headers=headers(owner)).status_code == 200
        )
        assert dataset_exports.run_one(engine, settings)
        byzip = public.get(f"/api/v1/datasets/{bypub}/versions/1/download")
        assert byzip.status_code == 200
        with zipfile.ZipFile(io.BytesIO(byzip.content)) as z:
            assert (
                json.loads(z.read("manifest.json"))["images"][0]["public_attribution"]
                == "Research Photo 1"
            )
        # Public report queue never exposes private owner review records.
        assert (
            public.post(
                f"/api/v1/datasets/{bypub}/reports",
                json={"reason": "licence", "details": "Synthetic concern"},
                headers={"Origin": settings.frontend_url},
            ).status_code
            == 202
        )
        assert public.get(f"/api/v1/datasets/{bypub}/reports").status_code == 401
        login(c, owner)
        assert len(c.get(f"/api/v1/datasets/{bypub}/reports").json()) == 1
        # Withdrawal revokes access without changing approval, images or QC.
        login(c, contributor)
        assert (
            c.post(
                f"/api/v1/submissions/{image}/withdraw-export", headers=headers(contributor)
            ).status_code
            == 200
        )
        assert public.get(f"/api/v1/datasets/{bypub}/versions/1/download").status_code == 410
        with Session(engine) as s:
            assert (
                s.get(Submission, image).status == "approved"
                and s.get(Submission, image).hidden_at is None
            )
        # Resource limits and failure recovery use real files, no unsafe DB states.
        limited = project()
        c_image = upload("orange", limited)
        approve(c_image)
        login(c, owner)
        limited_pub = c.post(
            f"/api/v1/projects/{limited}/dataset", json=policy, headers=headers(owner)
        ).json()["id"]
        r = consent(c_image, limited_pub)
        grants[c_image] = r.json()["id"]
        assert authorise(c_image, limited_pub).status_code == 204
        with monkeypatch.context() as patch:
            patch.setattr(datasets, "MAX_IMAGES", 0)
            login(c, owner)
            assert (
                c.post(
                    f"/api/v1/datasets/{limited_pub}/versions", headers=headers(owner)
                ).status_code
                == 413
            )
        login(c, owner)
        assert (
            c.post(f"/api/v1/datasets/{limited_pub}/versions", headers=headers(owner)).status_code
            == 200
        )
        with monkeypatch.context() as patch:
            patch.setattr(dataset_exports, "MAX_EXPORT_BYTES", 1)
            assert dataset_exports.run_one(engine, settings)
        assert public.get(f"/api/v1/datasets/{limited_pub}/versions/1/download").status_code == 410
        assert (
            public.post(
                f"/api/v1/datasets/{limited_pub}/versions/1/prepare",
                headers={"Origin": settings.frontend_url},
            ).status_code
            == 200
        )
        assert dataset_exports.run_one(engine, settings)
        assert public.get(f"/api/v1/datasets/{limited_pub}/versions/1/download").status_code == 200
        login(c, owner)
        assert (
            c.post(f"/api/v1/datasets/{limited_pub}/withdraw", headers=headers(owner)).status_code
            == 204
        )
        assert public.get(f"/api/v1/datasets/{limited_pub}").status_code == 404
        assert public.get(f"/api/v1/datasets/{limited_pub}/versions/1/download").status_code == 404
        assert dataset_exports.cleanup(engine, settings) >= 1
        with monkeypatch.context() as patch:
            patch.setattr("app.api.routes.datasets.throttle", lambda *_: False)
            assert public.get("/api/v1/datasets").status_code == 429
