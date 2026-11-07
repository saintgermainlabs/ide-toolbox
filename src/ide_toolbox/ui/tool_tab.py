from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFormLayout, QLabel, QPushButton, QSplitter, QTableWidget,
                               QTabWidget, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from ..core.models import PathState, ToolReport
from .widgets import PathRow, SectionView, SummaryTree, make_table

INNER = ("Overview", "Skills", "Plugins", "MCPs", "Configuration")


class ToolTab(QWidget):
    rescan_requested = Signal(str)

    def __init__(self, report: ToolReport, access: str = ""):
        super().__init__()
        self.report = report
        lay = QVBoxLayout(self)
        self.inner = QTabWidget()
        lay.addWidget(self.inner)
        self.inner.addTab(self._overview(report, access), "Overview")
        r = report
        self.inner.addTab(SectionView(r.skills, ["Name", "Description", "Scope", "Source"],
                                      [[i.name, i.description, i.scope, i.source] for i in r.skills.items]),
                          "Skills")
        self.inner.addTab(SectionView(r.plugins, ["Name / ID", "Version", "Enabled", "Scope", "Source"],
                                      [[i.name, i.version, i.enabled or "not declared", i.scope, i.source]
                                       for i in r.plugins.items]), "Plugins")
        self.inner.addTab(SectionView(r.mcps, ["Name", "Transport", "Enabled", "Scope", "Source",
                                               "Env keys", "Header keys", "State"],
                                      [[i.name, i.transport, i.enabled or "not declared", i.scope, i.source,
                                        ", ".join(f"{k}=•••" for k in i.env_keys),
                                        ", ".join(f"{k}=•••" for k in i.header_keys), i.state]
                                       for i in r.mcps.items]), "MCPs")
        self.inner.addTab(self._configuration(r), "Configuration")

    def _overview(self, r: ToolReport, access: str) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.addRow("Status:", QLabel(f"<b>{r.detection.label}</b>"))
        form.addRow("Confidence:", QLabel(r.detection.confidence.value))
        form.addRow("Version:", QLabel(r.version or "—"))
        sig = "\n".join(f"[{s.kind.value}] {s.detail}  {s.path}" for s in r.detection.signals) or "none"
        lbl = QLabel(sig)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Signals:", lbl)
        if access:
            a = QLabel(access)
            a.setWordWrap(True)
            form.addRow("Reads:", a)
        form.addRow("Last scan:", QLabel(r.scanned_at))
        if r.errors:
            form.addRow("Errors:", QLabel(str(r.errors)))
        btn = QPushButton("Rescan this tool")
        btn.clicked.connect(lambda: self.rescan_requested.emit(r.tool_id))
        form.addRow(btn)
        return w

    def _configuration(self, r: ToolReport) -> QWidget:
        split = QSplitter(Qt.Vertical)
        table = QTableWidget(len(r.config), 5)
        table.setHorizontalHeaderLabels(["Label", "Path", "Scope", "State", "Actions"])
        table.verticalHeader().setVisible(False)
        from PySide6.QtWidgets import QTableWidgetItem, QAbstractItemView
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.path_rows: list[PathRow] = []
        for i, e in enumerate(r.config):
            state = e.state.value + (f" → {e.link_target}" if e.state == PathState.BROKEN_SYMLINK else "")
            for c, v in enumerate([e.label, e.path, e.scope, state]):
                it = QTableWidgetItem(v)
                it.setToolTip(v)
                table.setItem(i, c, it)
            row = PathRow(e)
            self.path_rows.append(row)
            table.setCellWidget(i, 4, row)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        if not r.config:
            split.addWidget(QLabel("No known configuration locations for this tool in v1."))
        else:
            split.addWidget(table)
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.addWidget(QLabel("<b>Redacted view</b> – key names and value types only. "
                            "Use Open File to see or edit the raw file in your own editor."))
        bl.addWidget(SummaryTree(r.summaries))
        split.addWidget(box)
        return split
