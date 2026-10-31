"""Private bounded export files. Keys are server-generated UUID paths only."""

import os
import re
from pathlib import Path

PATTERN = re.compile(r"archives/[0-9a-f]{32}/[0-9a-f]{32}\.(?:zip|tmp)\Z")


class ExportStore:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def path(self, key: str) -> Path:
        if not PATTERN.fullmatch(key):
            raise ValueError("Invalid export reference")
        path = self.root / key
        if any(p.is_symlink() for p in [self.root, path.parent.parent, path.parent, path]):
            raise ValueError("Symlinks are not supported")
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Invalid export reference")
        return path

    def create(self, key: str):
        path = self.path(key)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return os.fdopen(
            os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
        )

    def open(self, key: str):
        return os.fdopen(os.open(self.path(key), os.O_RDONLY | os.O_NOFOLLOW), "rb")

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)
