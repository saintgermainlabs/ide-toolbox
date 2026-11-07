import logging
import os
import time

from conftest import assert_no_secrets
from ide_toolbox.adapters.registry import all_adapters
from ide_toolbox.core.models import MCP_STATE, Confidence, PathState, SectionStatus
from ide_toolbox.core import scanner
from ide_toolbox.core.scanner import scan_tool


def reports(ctx):
    return {a.id: scan_tool(a, ctx) for a in all_adapters()}


def test_detection_levels(fake_home):
    r = reports(fake_home)
    assert r["cursor"].detection.confidence == Confidence.HIGH
    assert r["cursor"].version == "3.29.9"
    assert r["codex"].detection.confidence == Confidence.LOW
    assert r["codex"].detection.label == "Config found, application not detected"
    assert r["gemini"].detection.confidence == Confidence.LOW
    assert r["kiro"].detection.confidence == Confidence.LOW
    assert r["antigravity"].detection.confidence == Confidence.MEDIUM
    assert r["aider"].detection.confidence == Confidence.MEDIUM
    assert r["kimi"].detection.confidence == Confidence.NONE
    assert not (fake_home.tmp / "EXEC_RAN").exists()


def test_skills_plugins(fake_home):
    r = reports(fake_home)
    assert {s.name for s in r["cursor"].skills.items} == {"brainstorm", "plain"}
    assert [s.name for s in r["claude"].skills.items] == ["review"]
    assert [s.name for s in r["codex"].skills.items] == ["plan"]
    assert r["vscode"].skills.status == SectionStatus.UNSUPPORTED
    assert r["aider"].mcps.status == SectionStatus.UNSUPPORTED
    assert r["kiro"].mcps.status == SectionStatus.UNKNOWN
    assert [p.name for p in r["cursor"].plugins.items] == ["anthropic.claude-code"]
    assert [p.name for p in r["vscode"].plugins.items] == ["ms-python.python", "saoudrizwan.claude-dev"]
    assert r["vscode"].plugins.items[0].version == "2025.1.0"
    assert [p.name for p in r["claude"].plugins.items] == ["superpowers"]
    assert r["codex"].plugins.status == SectionStatus.UNSUPPORTED


def test_mcps(fake_home):
    r = reports(fake_home)
    cur = {m.name: m for m in r["cursor"].mcps.items}
    assert set(cur) == {"github", "remote", "off"}
    assert cur["github"].transport == "stdio" and cur["github"].env_keys == ("GITHUB_TOKEN",)
    assert cur["remote"].transport == "http" and cur["remote"].header_keys == ("Authorization",)
    assert cur["off"].enabled == "No"
    assert all(m.state == MCP_STATE for m in cur.values())
    assert [m.name for m in r["claude"].mcps.items] == ["sse-one"]  # not project-nested
    assert r["claude"].mcps.items[0].transport == "sse"
    assert [m.name for m in r["codex"].mcps.items] == ["docs"]
    assert r["codex"].mcps.items[0].env_keys == ("API_KEY",)
    assert r["vscode"].mcps.items[0].name == "fs"
    assert r["gemini"].mcps.items[0].transport == "http"
    assert r["opencode"].mcps.status == SectionStatus.PARSE_ERROR


def test_no_secrets_anywhere(fake_home):
    assert_no_secrets(repr(reports(fake_home)))


def test_config_states_and_projects(fake_home, tmp_path):
    proj = tmp_path / "proj"
    (proj / ".cursor/skills/local").mkdir(parents=True)
    (proj / ".cursor/skills/local/SKILL.md").write_text("---\nname: local\n---\n")
    (proj / ".mcp.json").write_text('{"mcpServers": {"p": {"command": "x"}}}')
    fake_home.project_roots = [proj]
    r = reports(fake_home)
    scopes = {s.scope for s in r["cursor"].skills.items}
    assert f"Project: {proj}" in scopes and "User" in scopes
    assert r["claude"].mcps.items[-1].scope == f"Project: {proj}"
    cop = r["copilot"].config[0]
    assert cop.state == PathState.BROKEN_SYMLINK


def test_scan_is_read_only(fake_home):
    files = [p for p in fake_home.home.rglob("*") if p.is_file()]
    before = {p: p.stat().st_mtime_ns for p in files}
    reports(fake_home)
    assert {p: p.stat().st_mtime_ns for p in files} == before
    assert sorted(p for p in fake_home.home.rglob("*") if p.is_file()) == sorted(files)


def test_timeout_and_errors_isolated(fake_home, monkeypatch, caplog):
    a = next(x for x in all_adapters() if x.id == "cursor")
    monkeypatch.setattr(a, "skills", lambda ctx: time.sleep(5))
    def boom(ctx):
        raise RuntimeError("sk-PLANTEDsecretVALUE1234567890")
    monkeypatch.setattr(a, "plugins", boom)
    caplog.set_level(logging.INFO, logger="ide_toolbox")
    t = time.monotonic()
    rep = scan_tool(a, fake_home, deadline=0.5)
    assert time.monotonic() - t < 4
    assert rep.skills.status == SectionStatus.TIMED_OUT
    assert rep.plugins.status == SectionStatus.UNKNOWN
    assert rep.mcps.status == SectionStatus.OK
    assert rep.errors == 2
    assert_no_secrets(caplog.text + repr(rep))


def test_hanging_cli_probe(fake_home):
    from conftest import exe
    exe(fake_home.bin, "cursor", "sleep 30")
    a = next(x for x in all_adapters() if x.id == "cursor")
    import ide_toolbox.core.probe as pr
    old = pr.DEFAULT_TIMEOUT
    t = time.monotonic()
    rep = scan_tool(a, fake_home)
    assert time.monotonic() - t < 15
    assert rep.probes[0].state.value == "Probe timed out"
