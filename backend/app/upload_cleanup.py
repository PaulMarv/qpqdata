"""Expire abandoned slots and reclaim unreferenced objects; no ledger writes."""

import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Submission
from app.storage import LocalObjectStore


def cleanup(engine, root: str) -> tuple[int, int]:
    now = datetime.now(UTC)
    expired = 0
    removed = 0
    with Session(engine) as session, session.begin():
        rows = session.scalars(
            select(Submission)
            .where(
                Submission.workflow_version == 1,
                Submission.status == "uploading",
                Submission.abandoned_at.is_(None),
                Submission.upload_expires_at < now,
            )
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.abandoned_at = now
            expired += 1
    store = LocalObjectStore(root)
    for path in (Path(root) / "objects").glob("*/*"):
        if path.is_symlink() or not path.is_file() or path.stat().st_mtime > time.time() - 3600:
            continue
        key = path.relative_to(Path(root)).as_posix()
        try:
            candidate = UUID(path.parent.name)
            store.path(key)
        except ValueError:
            continue
        # Writers hold this same row lock across put+database commit. Do not
        # reclaim an object whose reference is still being committed.
        with Session(engine) as session, session.begin():
            row = session.scalar(
                select(Submission).where(Submission.id == candidate).with_for_update()
            )
            if row and row.object_key == key:
                continue
            store.delete(key)
            removed += 1
    return expired, removed


def main():
    import sys

    from app.config import Settings
    from app.db import make_engine

    settings = Settings()
    if not settings.uploads_enabled:
        return
    engine = make_engine(settings.database_url.get_secret_value())
    try:
        while True:
            try:
                expired, removed = cleanup(engine, settings.storage_root)
                Path("/tmp/qpq-upload-cleaner-heartbeat").touch(mode=0o600, exist_ok=True)
                print(
                    f"Upload cleanup: {expired} expired slots, {removed} orphan objects", flush=True
                )
            except Exception:
                # Never log exceptions/SQL parameters/private object references.
                print("Upload cleanup unavailable; retry scheduled", flush=True)
                if "--once" in sys.argv:
                    raise SystemExit(1) from None
            if "--once" in sys.argv:
                return
            time.sleep(60)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
