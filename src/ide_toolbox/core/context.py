from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .probe import ProbeRunner


@dataclass
class ScanContext:
    home: Path
    path_env: str
    desktop_dirs: list[Path]
    project_roots: list[Path] = field(default_factory=list)
    runner: ProbeRunner | None = None
    probes_enabled: bool = True

    @classmethod
    def from_environment(cls, project_roots: list[Path] | None = None) -> "ScanContext":
        home = Path.home()
        path_env = os.environ.get("PATH", "")
        data_home = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
        desktop = [data_home / "applications", Path("/usr/share/applications"),
                   Path("/usr/local/share/applications"),
                   Path("/var/lib/snapd/desktop/applications"),
                   Path("/var/lib/flatpak/exports/share/applications"),
                   home / ".local/share/flatpak/exports/share/applications"]
        return cls(home=home, path_env=path_env, desktop_dirs=desktop,
                   project_roots=list(project_roots or []),
                   runner=ProbeRunner(path_env))
