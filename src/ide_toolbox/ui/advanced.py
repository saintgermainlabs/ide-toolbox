from __future__ import annotations

import os
import platform
import shutil
import sys

import PySide6
from PySide6.QtCore import qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from ..core.models import ProbeResult
from .widgets import make_table


class AdvancedPage(QWidget):
    def __init__(self, rows: list[tuple[str, ProbeResult]]):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>Command-line tools</b> (only fixed <code>--version</code> probes, "
                             "5 s timeout, no shell)"))
        lay.addWidget(make_table(
            ["Tool", "CLI", "State", "Version", "Path", "Resolved", "Install source", "Other copies"],
            [[tool, p.name, p.state.value, p.version, p.path, p.resolved if p.resolved != p.path else "",
              p.source if p.path else "", ", ".join(p.duplicates)] for tool, p in rows]))
        env = QWidget()
        f = QFormLayout(env)
        f.addRow("App Python:", QLabel(f"{platform.python_version()}  ({sys.executable})"))
        f.addRow("PySide6 / Qt:", QLabel(f"{PySide6.__version__} / {qVersion()}"))
        f.addRow("Qt platform:", QLabel(QGuiApplication.platformName()))
        f.addRow("Session type:", QLabel(os.environ.get("XDG_SESSION_TYPE", "unknown")))
        f.addRow("xdg-open:", QLabel(shutil.which("xdg-open") or "not found"))
        lay.addWidget(QLabel("<b>Environment</b>"))
        lay.addWidget(env)
