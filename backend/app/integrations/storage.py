"""Private object-store port and development filesystem adapter. No user paths."""

import os
import re
from pathlib import Path
from typing import Protocol

_KEY = re.compile(r"objects/[0-9a-f]{32}/[0-9a-f]{32}\.(?:jpg|png|webp)\Z")


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalObjectStore:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise ValueError("Invalid object reference")
        path = self.root / key
        if any(p.is_symlink() for p in [self.root, path.parent.parent, path.parent, path]):
            raise ValueError("Symlink objects are not supported")
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Invalid object reference")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Never overwrite an object. No original filenames or temporary raw files.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def read(self, key: str) -> bytes:
        path = self.path(key)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            return stream.read(10 * 1024 * 1024 + 1)

    def delete(self, key: str) -> None:
        path = self.path(key)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass  # Another object may remain, or the directory was never created.
