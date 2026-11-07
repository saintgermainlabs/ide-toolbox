"""Desktop-entry presence. Reads only the Name= key; Exec= is never parsed or run."""
from __future__ import annotations

from pathlib import Path

from .parsers import MAX_BYTES
from .redact import safe_text


def find_desktop_entries(dirs: list[Path], filenames: tuple[str, ...]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for d in dirs:
        for fn in filenames:
            p = d / fn
            try:
                if not p.is_file() or p.stat().st_size > MAX_BYTES:
                    continue
                name = fn
                with p.open("r", encoding="utf-8", errors="replace") as fh:
                    for line in fh.read(65536).splitlines():
                        if line.startswith("Name="):
                            name = safe_text(line[5:], 80) or fn
                            break
                found.append((name, str(p)))
            except OSError:
                continue
    return found
