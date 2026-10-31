"""Atomic JSON publication with a bounded retry for transient Windows file locks."""

import json
import os
import tempfile
from pathlib import Path
from time import sleep


def atomic_write_json(path: Path, value: dict) -> None:
    """Publish fully flushed JSON; callers own their transaction/writer locks."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = handle.name
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                sleep(min(0.02 * (attempt + 1), 0.05))
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
