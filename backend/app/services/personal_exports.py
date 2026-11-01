"""Bounded private snapshots; reuse safe image/ZIP processing, never publish or post QC."""

import csv
import hashlib
import io
import json
import tempfile
import time
import uuid
import zipfile
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.db.models import RemovalRequest, Submission
from app.integrations.storage import LocalObjectStore
from app.services import dataset_exports, projects
from app.services.auth import AuthError

MAX_PRIVATE_BYTES = 128 * 1024 * 1024


def generate(session: Session, user, project_id, settings):
    project = projects.owner_project(session, user, project_id)
    if project.mode != "personal":
        raise AuthError("Private export is for personal collections.", 409)
    definition = projects.definition_for(session, project)
    rows = session.scalars(
        select(Submission)
        .where(
            Submission.project_id == project.id,
            Submission.workflow_version == 2,
            Submission.status == "approved",
            Submission.hidden_at.is_(None),
            Submission.image_deleted_at.is_(None),
            ~exists().where(RemovalRequest.submission_id == Submission.id),
        )
        .order_by(Submission.id)
        .limit(501)
        .with_for_update(read=True)
    ).all()
    if not rows or len(rows) > 500:
        raise AuthError("Private export requires 1–500 available images.", 409)
    # One disk-backed archive per existing download semaphore slot, never a ZIP in RAM.
    stream = tempfile.TemporaryFile(mode="w+b")
    started = time.monotonic()
    signatures = {}
    manifest = {
        "collection_id": str(project.id),
        "visibility": "private",
        "export_timestamp": datetime.now(UTC).isoformat(),
        "criteria_version": project.published_version,
        "criteria": definition.criteria.model_dump(),
        "label_definitions": [label.model_dump() for label in definition.labels],
        "licence": definition.licence,
        "reuse_terms": definition.reuse_terms,
        "images": [],
    }
    csv_out = io.StringIO(newline="")
    writer = csv.writer(csv_out)
    writer.writerow(["image_id", "file", "label", "answers", "source"])
    store = LocalObjectStore(settings.storage_root)
    try:
        with zipfile.ZipFile(stream, "w", allowZip64=False) as archive:
            for row in rows:
                if time.monotonic() - started > 120:
                    raise AuthError(
                        "Private export time limit exceeded; split the collection.", 413
                    )
                data = dataset_exports.canonical_image(store.read(row.object_key))
                if stream.tell() + len(data) > MAX_PRIVATE_BYTES - 4 * 1024 * 1024:
                    raise AuthError("Private export exceeds 128 MiB; split the collection.", 413)
                image_id = uuid.uuid5(project.id, str(row.id)).hex
                name = f"images/{image_id}.png"
                dataset_exports.zip_entry(archive, name, data)
                item = {
                    "image_id": image_id,
                    "file": name,
                    "label": row.label_key,
                    "answers": row.metadata_values,
                    "source": "owner-provided",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "annotation_version": row.annotation_version,
                }
                manifest["images"].append(item)
                signatures[str(row.id)] = row.annotation_version
                writer.writerow(
                    [
                        image_id,
                        name,
                        dataset_exports.csv_cell(row.label_key),
                        dataset_exports.csv_cell(row.metadata_values),
                        "owner-provided",
                    ]
                )
            manifest["image_count"] = len(rows)
            manifest["snapshot_id"] = hashlib.sha256(
                json.dumps(manifest["images"], sort_keys=True).encode()
            ).hexdigest()
            encoded = json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2).encode()
            if len(encoded) > 2 * 1024 * 1024 or len(csv_out.getvalue().encode()) > 2 * 1024 * 1024:
                raise AuthError("Private annotations exceed the export limit.", 413)
            dataset_exports.zip_entry(archive, "manifest.json", encoded)
            dataset_exports.zip_entry(archive, "labels.csv", csv_out.getvalue().encode())
            dataset_exports.zip_entry(
                archive,
                "README.md",
                (
                    b"Private owner snapshot. Not publicly published. "
                    b"Images re-encoded without original metadata. Rights are attested, "
                    b"not independently proven. Private text answers are included "
                    b"for the owner only."
                ),
            )
            dataset_exports.zip_entry(
                archive,
                "LICENSE.txt",
                (
                    "Private snapshot; no new public distribution grant. Recorded image licence: "
                    + definition.licence
                    + "\nRecorded terms: "
                    + definition.reuse_terms
                ).encode(),
            )
        size = stream.tell()
        stream.seek(0)
        return stream, size, signatures
    except (OSError, ValueError):
        stream.close()
        raise AuthError("Private image storage unavailable. Retry later.", 503) from None
    except BaseException:
        stream.close()
        raise
