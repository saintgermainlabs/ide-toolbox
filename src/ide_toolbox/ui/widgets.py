from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..core.models import PathEntry, PathState, Section, SectionStatus
from ..core.paths import folder_for

STATUS_TEXT = {
    SectionStatus.UNSUPPORTED: "Unsupported for this tool",
    SectionStatus.UNKNOWN: "Unknown – not mapped to a documented source in v1",
    SectionStatus.MISSING: "Missing – nothing found at the known locations",
    SectionStatus.EMPTY: "Empty – source found but it lists nothing",
    SectionStatus.UNREADABLE: "Unreadable",
    SectionStatus.PARSE_ERROR: "Parse error",
    SectionStatus.TIMED_OUT: "Timed out",
}


def open_path(path: str) -> bool:
    url = QUrl.fromLocalFile(path)
    if QDesktopServices.openUrl(url):
        return True
    try:  # fallback: fixed argv, no shell
        subprocess.Popen(["xdg-open", path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def copy_path(path: str) -> None:
    QGuiApplication.clipboard().setText(path)


def make_table(headers: list[str], rows: list[list[str]]) -> QTableWidget:
    t = QTableWidget(len(rows), len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.verticalHeader().setVisible(False)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            it = QTableWidgetItem(val)
            it.setToolTip(val)
            t.setItem(r, c, it)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    t.horizontalHeader().setStretchLastSection(True)
    t.resizeColumnsToContents()
    return t


class SectionView(QWidget):
    def __init__(self, section: Section, headers: list[str], rows: list[list[str]]):
        super().__init__()
        lay = QVBoxLayout(self)
        if section.status != SectionStatus.OK:
            banner = QLabel(f"<b>{STATUS_TEXT.get(section.status, section.status.value)}</b>")
            banner.setObjectName("statusBanner")
            lay.addWidget(banner)
        for n in section.notes:
            lbl = QLabel(n)
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        if section.status == SectionStatus.OK:
            lay.addWidget(make_table(headers, rows))
        else:
            lay.addStretch(1)


class PathRow(QWidget):
    def __init__(self, entry: PathEntry):
        super().__init__()
        self.entry = entry
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        exists = entry.state == PathState.EXISTS
        self.open_file = QPushButton("Open File")
        self.open_folder = QPushButton("Open Folder")
        self.copy = QPushButton("Copy Path")
        self.open_file.setEnabled(exists and entry.kind == "file")
        folder = folder_for(entry.path, entry.kind)
        self.open_folder.setEnabled(exists and folder.is_dir())
        self.open_file.clicked.connect(lambda: open_path(entry.path))
        self.open_folder.clicked.connect(lambda: open_path(str(folder_for(entry.path, entry.kind))))
        self.copy.clicked.connect(lambda: copy_path(entry.path))
        tip = {PathState.UNREADABLE: "Permission denied",
               PathState.BROKEN_SYMLINK: f"Broken symlink → {entry.link_target}",
               PathState.MISSING: "Path does not exist"}.get(entry.state, "")
        for b in (self.open_file, self.open_folder, self.copy):
            b.setToolTip(tip)
            lay.addWidget(b)


class SummaryTree(QTreeWidget):
    def __init__(self, summaries):
        super().__init__()
        self.setHeaderLabels(["Key (values hidden)", "Type"])
        for s in summaries:
            top = QTreeWidgetItem([s.path, s.status.value + (f" – {s.note}" if s.note else "")])
            for k, v in s.rows:
                top.addChild(QTreeWidgetItem([k, v]))
            self.addTopLevelItem(top)
        self.resizeColumnToContents(0)
