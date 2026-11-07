from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QInputDialog, QLabel, QMainWindow,
                               QTabWidget, QToolBar, QWidget)

from ..adapters.base import SpecAdapter
from ..core.context import ScanContext
from ..core.models import Confidence, ToolReport
from ..core.scanner import scan_tool
from ..core.settings import Settings
from .advanced import AdvancedPage
from .tool_tab import ToolTab

log = logging.getLogger("ide_toolbox")


class _Signals(QObject):
    done = Signal(object)


class ScanJob(QRunnable):
    def __init__(self, adapter: SpecAdapter, ctx: ScanContext):
        super().__init__()
        self.adapter, self.ctx = adapter, ctx
        self.signals = _Signals()

    def run(self):
        self.signals.done.emit(scan_tool(self.adapter, self.ctx))


class MainWindow(QMainWindow):
    scan_finished = Signal()

    def __init__(self, adapters: list[SpecAdapter], ctx: ScanContext, settings: Settings,
                 persist: bool = True):
        super().__init__()
        self.setWindowTitle("IDE Toolbox (read-only)")
        self.resize(1200, 760)
        self.adapters = {a.id: a for a in adapters}
        self.order = [a.id for a in adapters]
        self.ctx, self.settings, self.persist = ctx, settings, persist
        self.ctx.project_roots = list(settings.project_roots)
        self.reports: dict[str, ToolReport] = {}
        self.pending = 0
        self.pool = QThreadPool.globalInstance()
        self.jobs: list[ScanJob] = []

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        tb = QToolBar("Main")
        self.addToolBar(tb)
        tb.addAction("Rescan all", self.scan_all)
        tb.addAction("Add project folder…", self.add_project)
        tb.addAction("Remove project folder…", self.remove_project)
        self.show_missing = QCheckBox("Show undetected tools")
        self.show_missing.setChecked(settings.show_undetected)
        self.show_missing.toggled.connect(self._toggle_missing)
        tb.addWidget(self.show_missing)
        self.projects_label = QLabel()
        tb.addWidget(self.projects_label)
        self._update_projects_label()
        self.tabs.addTab(QLabel("Scanning…"), "Scanning…")

    # ---- scanning --------------------------------------------------------
    def scan_all(self):
        for tid in self.order:
            self.scan(tid)

    def scan(self, tool_id: str):
        self.pending += 1
        self.statusBar().showMessage(f"Scanning… ({self.pending} pending)")
        job = ScanJob(self.adapters[tool_id], self.ctx)
        job.signals.done.connect(self._on_done)
        self.jobs.append(job)
        self.pool.start(job)

    def _on_done(self, report: ToolReport):
        self.reports[report.tool_id] = report
        self.pending -= 1
        if self.pending <= 0:
            self.pending = 0
            self.jobs.clear()
            self.rebuild()
            errs = sum(r.errors for r in self.reports.values())
            self.statusBar().showMessage(f"Scan complete – {len(self.reports)} tools checked, {errs} errors")
            self.scan_finished.emit()
        else:
            self.statusBar().showMessage(f"Scanning… ({self.pending} pending)")

    # ---- tabs ------------------------------------------------------------
    def rebuild(self):
        current = self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else ""
        self.tabs.clear()
        for tid in self.order:
            r = self.reports.get(tid)
            if r is None or self.adapters[tid].spec.advanced_only:
                continue
            if r.detection.confidence == Confidence.NONE and not self.show_missing.isChecked():
                continue
            tab = ToolTab(r, self.adapters[tid].spec.access)
            tab.rescan_requested.connect(self.scan)
            label = r.name if r.detection.confidence != Confidence.NONE else f"{r.name} (missing)"
            self.tabs.addTab(tab, label)
        rows = [(r.name, p) for tid in self.order if (r := self.reports.get(tid)) for p in r.probes]
        self.tabs.addTab(AdvancedPage(rows), "Advanced")
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == current:
                self.tabs.setCurrentIndex(i)

    def _toggle_missing(self, on: bool):
        self.settings.show_undetected = on
        self._save()
        if self.reports:
            self.rebuild()

    # ---- projects --------------------------------------------------------
    def add_project(self, path: str | None = None):
        if path is None:
            path = QFileDialog.getExistingDirectory(self, "Choose a project folder", str(Path.home()))
        if not path:
            return
        if self.settings.add_root(Path(path)):
            self._save()
            self.ctx.project_roots = list(self.settings.project_roots)
            self._update_projects_label()
            self.scan_all()

    def remove_project(self):
        roots = [str(r) for r in self.settings.project_roots]
        if not roots:
            return
        choice, ok = QInputDialog.getItem(self, "Remove project folder", "Folder:", roots, 0, False)
        if ok and choice:
            self.settings.remove_root(Path(choice))
            self._save()
            self.ctx.project_roots = list(self.settings.project_roots)
            self._update_projects_label()
            self.scan_all()

    def _update_projects_label(self):
        n = len(self.settings.project_roots)
        self.projects_label.setText(f"  Project folders: {n}" if n else "  Project folders: none (user scope only)")
        self.projects_label.setToolTip("\n".join(str(r) for r in self.settings.project_roots))

    def _save(self):
        if self.persist:
            try:
                self.settings.save()
            except OSError:
                log.warning("settings_save_failed")
