"""Path state inspection. Never reads file contents."""
from __future__ import annotations

import os
from pathlib import Path

from .models import PathEntry, PathState


def path_state(p: Path) -> PathState:
    try:
        if p.is_symlink() and not p.exists():
            return PathState.BROKEN_SYMLINK
        if not p.exists():
            return PathState.MISSING
        if p.is_dir():
            ok = os.access(p, os.R_OK | os.X_OK)
        else:
            ok = os.access(p, os.R_OK)
        return PathState.EXISTS if ok else PathState.UNREADABLE
    except OSError:
        return PathState.UNREADABLE


def make_entry(label: str, p: Path, kind: str, scope: str) -> PathEntry:
    st = path_state(p)
    target = ""
    if p.is_symlink():
        try:
            target = os.readlink(p)
        except OSError:
            target = ""
    return PathEntry(label=label, path=str(p), kind=kind, scope=scope, state=st, link_target=target)


def folder_for(entry_path: str, kind: str) -> Path:
    p = Path(entry_path)
    return p if kind == "dir" else p.parent
