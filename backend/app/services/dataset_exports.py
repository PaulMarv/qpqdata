"""Bounded disk-based ZIP generation, immutable manifests and revocable caching."""

import csv
import hashlib
import io
import json
import os
import time
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import Engine, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    DatasetBuild,
    DatasetMember,
    DatasetPublication,
    DatasetVersion,
    Submission,
)
from app.integrations.exports import ExportStore
from app.integrations.storage import LocalObjectStore
from app.services.auth import AuthError
from app.services.datasets import LICENSE_URLS, MAX_IMAGES, definition, valid_version

MAX_EXPORT_BYTES = 512 * 1024 * 1024
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_CACHE_BYTES = 1024 * 1024 * 1024
MAX_SECONDS = 120
CACHE_SECONDS = 900
CHUNK = 256 * 1024


def canonical_image(data: bytes) -> bytes:
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Source image too large")
    with Image.open(io.BytesIO(data)) as image:
        if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 24_000_000:
            raise ValueError("Unsupported image")
        image.load()
        oriented = ImageOps.exif_transpose(image)
        mode = "RGBA" if "A" in oriented.getbands() else "RGB"
        converted = oriented.convert(mode)
        clean = Image.frombytes(mode, converted.size, converted.tobytes())
        out = io.BytesIO()
        clean.save(out, "PNG", compress_level=6)
        result = out.getvalue()
        if len(result) > MAX_IMAGE_BYTES:
            raise ValueError("Export image exceeds limit")
        return result


def csv_cell(value) -> str:
    # Spreadsheet formula injection is distinct from CSV quoting.
    string = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if isinstance(value, (list, dict, bool))
        else ""
        if value is None
        else str(value)
    )
    return "'" + string if string.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else string


def check(engine: Engine, version_id: uuid.UUID) -> bool:
    with Session(engine) as s:
        v = s.get(DatasetVersion, version_id)
        return bool(v and valid_version(s, v))


def zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    # Fixed timestamps/permissions make regeneration byte-for-byte reproducible.
    if name.startswith("/") or ".." in name.split("/"):
        raise ValueError("Unsafe archive name")
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.external_attr = 0o100600 << 16
    info.compress_type = zipfile.ZIP_STORED
    archive.writestr(info, data)


def generate(
    engine: Engine, settings: Settings, version_id: uuid.UUID, key: str
) -> tuple[dict, int, str]:
    started = time.monotonic()
    store = ExportStore(settings.export_root)
    sources = LocalObjectStore(settings.storage_root)
    with Session(engine) as s:
        v = s.get(DatasetVersion, version_id)
        pub = s.get(DatasetPublication, v.publication_id)
        d = definition(s, pub)
        members = s.scalars(
            select(DatasetMember)
            .where(DatasetMember.version_id == v.id)
            .order_by(DatasetMember.image_id)
        ).all()
        if not members or len(members) > MAX_IMAGES or not valid_version(s, v):
            raise ValueError("Snapshot unavailable")
        rows = [
            (m.image_id, m.annotations, s.get(Submission, m.submission_id).object_key)
            for m in members
        ]
        previous = v.manifest
        created = v.created_at.isoformat()
        number = v.version
        pub_id = str(pub.id)
        project_id = str(pub.project_id)
        criteria_version = pub.criteria_version
        fields = list(pub.public_fields)
    manifest = {
        "dataset_id": pub_id,
        "dataset_version": number,
        "collection_id": project_id,
        "export_timestamp": created,
        "image_count": len(rows),
        "criteria_version": criteria_version,
        "schema_version": 1,
        "label_definitions": [label.model_dump() for label in d.labels],
        "criteria": {
            "schema_version": 1,
            "questions": [q.model_dump() for q in d.criteria.questions if q.key in fields],
        },
        "licence": {"id": d.licence, "url": LICENSE_URLS[d.licence]},
        "permitted_use": d.reuse_terms,
        "provenance": {
            "consent_policy": 1,
            "distribution_policy": 1,
            "originality": (
                "Contributor permission attested and owner reviewed; not automatically proven."
            ),
            "processing": (
                "Metadata removed; decoded pixels re-encoded as PNG. "
                "Technical format conversion only."
            ),
        },
        "images": [],
    }
    table = io.StringIO(newline="")
    writer = csv.writer(table)
    writer.writerow(["image_id", "file", "label", *fields, "public_attribution"])
    tmp = key.removesuffix(".zip") + ".tmp"
    try:
        with store.create(tmp) as target, zipfile.ZipFile(target, "w", allowZip64=False) as archive:
            total = 0
            for image_id, annotations, source_key in rows:
                if time.monotonic() - started > MAX_SECONDS or not check(engine, version_id):
                    raise ValueError("Export interrupted or revoked")
                image = canonical_image(sources.read(source_key))
                total += len(image)
                if total > MAX_EXPORT_BYTES - 8 * 1024 * 1024:
                    raise ValueError("Export exceeds size limit")
                name = f"images/{image_id.hex}.png"
                zip_entry(archive, name, image)
                manifest["images"].append(
                    {
                        "image_id": str(image_id),
                        "file": name,
                        "sha256": hashlib.sha256(image).hexdigest(),
                        "label": annotations["label"],
                        "answers": annotations["answers"],
                        **({"source": annotations["source"]} if "source" in annotations else {}),
                        "public_attribution": annotations["attribution"],
                    }
                )
                writer.writerow(
                    [
                        image_id,
                        name,
                        csv_cell(annotations["label"]),
                        *[csv_cell(annotations["answers"].get(f)) for f in fields],
                        csv_cell(annotations["attribution"]),
                    ]
                )
            encoded = json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2).encode()
            csv_data = table.getvalue().encode("utf-8")
            if len(encoded) > 4 * 1024 * 1024 or len(csv_data) > 2 * 1024 * 1024:
                raise ValueError("Metadata limit exceeded")
            if previous is not None and previous != manifest:
                raise ValueError("Immutable snapshot content changed")
            zip_entry(archive, "labels.csv", csv_data)
            zip_entry(archive, "manifest.json", encoded)
            licence = (
                Path(__file__).parents[1] / "resources" / "licences" / (d.licence + ".txt")
            ).read_bytes()
            zip_entry(archive, "LICENSE.txt", licence)
            readme = (
                f"# {d.name}\n\nDataset {pub_id}, version {number}; collection {project_id}.\n\n"
                + f"{d.description}\n\nPurpose: {d.research_purpose}\n\n"
                + f"Licence: {d.licence} ({LICENSE_URLS[d.licence]}).\n"
                + f"Recorded reuse terms: {d.reuse_terms}\n\n"
                + (
                    "Attribution: retain the per-image public pseudonyms in manifest.j"
                    "son/labels.csv, the licence URL and this dataset/version referenc"
                    "e. Mark any changes; ShareAlike applies where required by CC-BY-S"
                    "A.\n\n"
                )
                + (
                    "CSV multi-choice/boolean values are JSON; cells beginning with sp"
                    "readsheet formula characters are prefixed with an apostrophe. Tex"
                    "t answers remain private.\n\n"
                )
                + (
                    "Originality is attested, not automatically proven. Images are met"
                    "adata-free PNG conversions. No contributor account identifiers ar"
                    "e included.\n\n"
                )
                + (
                    "Privacy/removal concerns: use this dataset's QPQData details page"
                    " to submit a report. QPQData may revoke distribution; copies alre"
                    "ady downloaded cannot be remotely revoked. An access restriction "
                    "does not automatically rescind rights already granted under an op"
                    "en licence.\n"
                )
            )
            zip_entry(archive, "README.md", readme.encode())
        size = store.path(tmp).stat().st_size
        if size > MAX_EXPORT_BYTES:
            raise ValueError("Export size limit exceeded")
        digest = hashlib.sha256()
        with store.open(tmp) as f:
            while data := f.read(CHUNK):
                digest.update(data)
        os.replace(store.path(tmp), store.path(key))
        return manifest, size, digest.hexdigest()
    except BaseException:
        store.delete(tmp)
        store.delete(key)
        raise


def cleanup(engine: Engine, settings: Settings) -> int:
    store = ExportStore(settings.export_root)
    removed = 0
    now = datetime.now(UTC)
    with Session(engine) as s, s.begin():
        rows = s.execute(
            select(DatasetBuild, DatasetVersion)
            .join(DatasetVersion, DatasetVersion.id == DatasetBuild.version_id)
            .where(or_(DatasetVersion.revoked_at.is_not(None), DatasetBuild.expires_at < now))
            .with_for_update(of=DatasetBuild, skip_locked=True)
        ).all()
        for b, v in rows:
            if b.artifact_key:
                store.delete(b.artifact_key)
                removed += 1
            b.artifact_key = None
            b.expires_at = None
            if v.revoked_at or b.state not in {"queued", "building"}:
                b.state = "failed"
    # Interrupted/uncommitted files are not referenced by a live build lease.
    with Session(engine) as s:
        keep = set(
            s.scalars(
                select(DatasetBuild.artifact_key).where(DatasetBuild.artifact_key.is_not(None))
            )
        )
    for p in (Path(settings.export_root) / "archives").glob("*/*"):
        if p.is_symlink() or not p.is_file() or p.stat().st_mtime > time.time() - 600:
            continue
        key = p.relative_to(Path(settings.export_root)).as_posix()
        if key not in keep:
            try:
                store.delete(key)
                removed += 1
            except ValueError:
                continue
    return removed


def run_one(engine: Engine, settings: Settings) -> bool:
    # One generator across all worker processes, not one per web request.
    with engine.connect() as lease:
        if not lease.execute(text("SELECT pg_try_advisory_lock(71591025)")).scalar():
            return False
        try:
            cleanup(engine, settings)
            with Session(engine) as s, s.begin():
                b = s.scalar(
                    select(DatasetBuild)
                    .join(DatasetVersion, DatasetVersion.id == DatasetBuild.version_id)
                    .where(
                        DatasetVersion.revoked_at.is_(None),
                        or_(
                            DatasetBuild.state == "queued",
                            (DatasetBuild.state == "building")
                            & (DatasetBuild.lease_until < datetime.now(UTC)),
                        ),
                    )
                    .order_by(DatasetBuild.created_at)
                    .with_for_update(of=DatasetBuild, skip_locked=True)
                    .limit(1)
                )
                if not b:
                    return False
                if b.attempts >= 3:
                    b.state = "failed"
                    return True
                b.state = "building"
                b.attempts += 1
                b.lease_until = datetime.now(UTC) + timedelta(minutes=5)
                version_id = b.version_id
                build_id = b.id
                key = f"archives/{version_id.hex}/{uuid.uuid4().hex}.zip"
            try:
                used = sum(
                    p.stat().st_size
                    for p in Path(settings.export_root).glob("archives/*/*")
                    if p.is_file() and not p.is_symlink()
                )
                if used > MAX_CACHE_BYTES - MAX_EXPORT_BYTES:
                    raise ValueError("Cache capacity reached")
                manifest, size, digest = generate(engine, settings, version_id, key)
                with Session(engine) as s, s.begin():
                    ids = s.scalars(
                        select(DatasetMember.submission_id).where(
                            DatasetMember.version_id == version_id
                        )
                    ).all()
                    # Removal takes Submission before Version. Match that lock order.
                    list(
                        s.scalars(
                            select(Submission)
                            .where(Submission.id.in_(ids))
                            .order_by(Submission.id)
                            .with_for_update(read=True)
                        )
                    )
                    v = s.get(DatasetVersion, version_id, with_for_update=True)
                    b = s.get(DatasetBuild, build_id, with_for_update=True)
                    if not valid_version(s, v):
                        raise ValueError("Snapshot revoked")
                    if v.manifest is not None and v.manifest != manifest:
                        raise ValueError("Immutable manifest mismatch")
                    if v.archive_sha256 and v.archive_sha256 != digest:
                        raise ValueError("Immutable archive checksum mismatch")
                    v.archive_sha256 = digest
                    v.manifest = manifest
                    b.state = "ready"
                    b.attempts = 0
                    b.artifact_key = key
                    b.byte_size = size
                    b.sha256 = digest
                    b.expires_at = datetime.now(UTC) + timedelta(seconds=CACHE_SECONDS)
                    b.lease_until = None
            except Exception:
                ExportStore(settings.export_root).delete(key)
                with Session(engine) as s, s.begin():
                    b = s.get(DatasetBuild, build_id, with_for_update=True)
                    b.state = "failed"
                    b.lease_until = (
                        datetime.now(UTC) + timedelta(minutes=15) if b.attempts >= 3 else None
                    )
            return True
        finally:
            lease.execute(text("SELECT pg_advisory_unlock(71591025)"))
            lease.commit()


def prepare(session: Session, v: DatasetVersion, export_root: str) -> None:
    if not valid_version(session, v):
        raise AuthError("Dataset version revoked or unavailable.", 410)
    b = session.scalar(
        select(DatasetBuild).where(DatasetBuild.version_id == v.id).with_for_update()
    )
    if b.state == "ready" and b.expires_at and b.expires_at > datetime.now(UTC):
        try:
            with ExportStore(export_root).open(b.artifact_key) as stream:
                if os.fstat(stream.fileno()).st_size == b.byte_size:
                    return
        except (OSError, ValueError, TypeError):
            pass
        b.expires_at = datetime.now(UTC)
    if b.state == "building" and b.lease_until and b.lease_until > datetime.now(UTC):
        return
    if b.attempts >= 3:
        if b.lease_until and b.lease_until > datetime.now(UTC):
            raise AuthError("Export retry cooldown active. Try again after 15 minutes.", 429)
        b.attempts = 0
    b.state = "queued"
