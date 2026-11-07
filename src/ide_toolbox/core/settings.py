"""App-owned settings: the only file the app writes besides its log."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ide-toolbox"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "ide-toolbox"


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or config_dir() / "settings.json"
        self.project_roots: list[Path] = []
        self.show_undetected = False

    def load(self) -> "Settings":
        try:
            if self.path.is_file() and self.path.stat().st_size < 1_000_000:
                data = json.loads(self.path.read_text("utf-8"))
                roots = data.get("project_roots", [])
                self.project_roots = [Path(r) for r in roots
                                      if isinstance(r, str) and os.path.isabs(r)][:50]
                self.show_undetected = bool(data.get("show_undetected", False))
        except (OSError, ValueError):
            pass
        return self

    def add_root(self, p: Path) -> bool:
        p = p.expanduser()
        if not p.is_absolute() or not p.is_dir():
            return False
        if p in self.project_roots:
            return False
        self.project_roots.append(p)
        return True

    def remove_root(self, p: Path) -> None:
        self.project_roots = [r for r in self.project_roots if r != p]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"project_roots": [str(r) for r in self.project_roots],
                   "show_undetected": self.show_undetected}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".settings.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, self.path)
