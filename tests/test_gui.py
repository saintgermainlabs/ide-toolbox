import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QAbstractButton, QLabel, QTableWidget, QTabWidget, QTreeWidget, QApplication

from conftest import assert_no_secrets
from ide_toolbox.adapters.registry import all_adapters
from ide_toolbox.core.settings import Settings
from ide_toolbox.ui.main_window import MainWindow
from ide_toolbox.ui.tool_tab import INNER, ToolTab


def all_text(w):
    parts = []
    for c in w.findChildren(QLabel):
        parts += [c.text(), c.toolTip()]
    for c in w.findChildren(QAbstractButton):
        parts += [c.text(), c.toolTip()]
    for t in w.findChildren(QTableWidget):
        for r in range(t.rowCount()):
            for col in range(t.columnCount()):
                it = t.item(r, col)
                if it:
                    parts += [it.text(), it.toolTip()]
    for tr in w.findChildren(QTreeWidget):
        stack = [tr.topLevelItem(i) for i in range(tr.topLevelItemCount())]
        while stack:
            it = stack.pop()
            parts += [it.text(0), it.text(1)]
            stack += [it.child(i) for i in range(it.childCount())]
    for tw in w.findChildren(QTabWidget):
        parts += [tw.tabText(i) for i in range(tw.count())]
    return "\n".join(parts)


def make(qtbot, ctx, tmp_path):
    win = MainWindow(all_adapters(), ctx, Settings(tmp_path / "s.json"), persist=False)
    qtbot.addWidget(win)
    with qtbot.waitSignal(win.scan_finished, timeout=30000):
        win.scan_all()
    return win


def tabs(win):
    return [win.tabs.tabText(i) for i in range(win.tabs.count())]


def test_layout_and_states(qtbot, fake_home, tmp_path):
    win = make(qtbot, fake_home, tmp_path)
    names = tabs(win)
    for n in ["Cursor", "VS Code", "Claude Code", "OpenCode", "Aider", "Codex", "Gemini CLI", "Kiro", "Antigravity"]:
        assert n in names
    assert names[-1] == "Advanced"
    assert "Kimi Code" not in " ".join(names) and "GitHub CLI (gh)" not in names
    cur = win.tabs.widget(names.index("Cursor"))
    assert isinstance(cur, ToolTab)
    assert [cur.inner.tabText(i) for i in range(cur.inner.count())] == list(INNER)
    vs = win.tabs.widget(names.index("VS Code"))
    assert "Unsupported for this tool" in all_text(vs.inner.widget(1))
    codex = win.tabs.widget(names.index("Codex"))
    assert "Config found, application not detected" in all_text(codex.inner.widget(0))
    assert "Configured (not checked)" in all_text(cur.inner.widget(3))
    assert "Connected" not in all_text(win)
    win.show_missing.setChecked(True)
    assert "Kimi Code (missing)" in tabs(win)
    assert_no_secrets(all_text(win))


def test_path_buttons(qtbot, fake_home, tmp_path):
    win = make(qtbot, fake_home, tmp_path)
    names = tabs(win)
    cur = win.tabs.widget(names.index("Cursor"))
    rows = {r.entry.label: r for r in cur.path_rows}
    missing = rows["User settings"]
    assert not missing.open_file.isEnabled() and not missing.open_folder.isEnabled()
    assert missing.copy.isEnabled()
    missing.copy.click()
    assert QApplication.clipboard().text() == missing.entry.path
    present = rows["User MCP config"]
    assert present.open_file.isEnabled() and present.open_folder.isEnabled()
    adv = all_text(win.tabs.widget(names.index("Advanced")))
    assert "Not on PATH" in adv and "Found – no version output" in adv and "3.29.9" in adv


def test_add_project_writes_only_settings(qtbot, fake_home, tmp_path):
    proj = tmp_path / "proj"
    (proj / ".claude/skills/x").mkdir(parents=True)
    (proj / ".claude/skills/x/SKILL.md").write_text("---\nname: projskill\n---\n")
    win = MainWindow(all_adapters(), fake_home, Settings(tmp_path / "cfg/s.json"), persist=True)
    qtbot.addWidget(win)
    with qtbot.waitSignal(win.scan_finished, timeout=30000):
        win.add_project(str(proj))
    assert (tmp_path / "cfg/s.json").exists()
    assert list(proj.rglob("*.json")) == []
    cl = win.tabs.widget(tabs(win).index("Claude Code"))
    assert "projskill" in all_text(cl)


def test_example_screenshot(qtbot, fake_home, tmp_path):
    """Saves a grab of the window on SYNTHETIC fixture data when IDE_TOOLBOX_SHOT is set."""
    out = os.environ.get("IDE_TOOLBOX_SHOT")
    win = make(qtbot, fake_home, tmp_path)
    win.resize(1280, 760)
    names = tabs(win)
    win.tabs.setCurrentIndex(names.index("Cursor"))
    cur = win.tabs.currentWidget()
    for i, label in enumerate(INNER):
        cur.inner.setCurrentIndex(i)
        if out:
            win.grab().save(f"{out}-cursor-{label.lower()}.png")
    win.tabs.setCurrentIndex(names.index("Advanced"))
    if out:
        win.grab().save(f"{out}-advanced.png")
