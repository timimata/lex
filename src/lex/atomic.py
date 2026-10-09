"""Writes that cannot half-happen, for the caches every run reads (ROADMAP, Phase 10).

A file is written beside its target under a temporary name and then put in its place with
os.replace, which is atomic on Windows as on POSIX: a run interrupted mid-write leaves the old
file or none, never half of one. An entry of the test cache cannot be opened to be repaired
(CLAUDE.md), so it must never be broken in the first place.
"""

import os
import tempfile
from pathlib import Path


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as f:
            f.write(data)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_text(path: Path, text: str) -> None:
    write_bytes(path, text.encode("utf-8"))


def set_aside(path: Path) -> None:
    """Move a cache entry that no longer reads to `<name>.broken`, so the next run asks again and
    a person can count, not read, what broke."""
    os.replace(path, path.with_name(f"{path.name}.broken"))
