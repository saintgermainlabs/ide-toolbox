import json
import os
import stat
from pathlib import Path

import pytest

from ide_toolbox.adapters.registry import build_allowlist
from ide_toolbox.core.context import ScanContext
from ide_toolbox.core.probe import ProbeRunner

# Planted fake secrets: none of these may ever reach models, UI text or logs.
SECRETS = [
    "sk-PLANTEDsecretVALUE1234567890",
    "ghp_PLANTEDtokenABCDEFGHIJ123456",
    "hunter2-planted-password",
    "PLANTED_ARG_VALUE_zz9",
    "planted-query-token-qq7",
    "plantedUser:plantedPass",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJwbGFudGVkIn0.c2lnbmF0dXJlcGxhbnRlZA",
]


def _w(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def exe(d: Path, name: str, body: str):
    p = d / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return p


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    apps = home / ".local/share/applications"
    s = SECRETS
    # Cursor: CLI, desktop entry (Exec must never run), skills, extensions, MCP with secrets
    exe(bin_, "cursor", "echo 3.29.9")
    _w(apps / "cursor.desktop", f"[Desktop Entry]\nName=Cursor\nExec=/bin/sh -c 'touch {tmp_path}/EXEC_RAN'\n")
    _w(home / ".cursor/skills/brainstorm/SKILL.md", "---\nname: brainstorm\ndescription: Ideas first\n---\nbody\n")
    _w(home / ".cursor/skills/plain/SKILL.md", "no front matter\n")
    _w(home / ".cursor/extensions/anthropic.claude-code-1.0/package.json",
       json.dumps({"publisher": "anthropic", "name": "claude-code", "version": "1.0.0"}))
    _w(home / ".cursor/mcp.json", """{
      // comment with "quotes"
      "mcpServers": {
        "github": {"command": "npx", "args": ["--token", "%s"], "env": {"GITHUB_TOKEN": "%s"}},
        "remote": {"url": "https://%s@example.com/mcp?token=%s", "headers": {"Authorization": "Bearer %s"}},
        "off": {"command": "x", "disabled": true},
      },
    }""" % (s[3], s[1], s[5], s[4], s[0]))
    # VS Code: code CLI lists extensions; MCP uses "servers"
    exe(bin_, "code", 'if [ "$1" = "--version" ]; then echo 1.145.2; else echo "ms-python.python@2025.1.0"; echo "saoudrizwan.claude-dev@4.1.24"; fi')
    _w(home / ".config/Code/User/mcp.json", json.dumps({"servers": {"fs": {"type": "stdio", "command": "n", "env": {"PASSWORD": s[2]}}}}))
    # Claude Code
    exe(bin_, "claude", "echo '2.1.319 (Claude Code)'")
    _w(home / ".claude/skills/review/SKILL.md", "---\nname: review\ndescription: Review code\n---\n")
    _w(home / ".claude.json", json.dumps({"oauthAccount": {"accessToken": s[6]},
                                          "mcpServers": {"sse-one": {"type": "sse", "url": "https://x/?k=" + s[4]}},
                                          "projects": {"/p": {"mcpServers": {"hidden": {}}}}}))
    _w(home / ".claude/plugins/cache/mk/superpowers/1.0/.claude-plugin/plugin.json",
       json.dumps({"name": "superpowers", "version": "1.0"}))
    # Codex config-only, TOML MCP
    _w(home / ".codex/config.toml", f'model = "x"\n[mcp_servers.docs]\ncommand = "npx"\nargs = ["{s[3]}"]\n[mcp_servers.docs.env]\nAPI_KEY = "{s[0]}"\n')
    _w(home / ".codex/skills/plan/SKILL.md", "---\nname: plan\n---\n")
    # OpenCode: malformed config
    exe(bin_, "opencode", "echo 1.18.16")
    _w(home / ".config/opencode/opencode.json", '{"mcp": {"a": ')
    # Gemini: config only
    _w(home / ".gemini/settings.json", json.dumps({"mcpServers": {"g": {"httpUrl": "https://h/" + s[4]}}}))
    # Aider: CLI with no version output
    exe(bin_, "aider", "true")
    _w(home / ".aider.conf.yml", f"model: gpt\nopenai-api-key: {s[0]}\n")
    # Kiro config-only; Antigravity desktop-only
    (home / ".kiro").mkdir(parents=True)
    _w(apps / "antigravity.desktop", "[Desktop Entry]\nName=Antigravity\nExec=antigravity\n")
    # broken symlink
    (home / ".copilot").parent.mkdir(parents=True, exist_ok=True)
    os.symlink(tmp_path / "nowhere", home / ".copilot")
    path_env = str(bin_)
    ctx = ScanContext(home=home, path_env=path_env, desktop_dirs=[apps],
                      runner=ProbeRunner(path_env, build_allowlist()))
    ctx.tmp = tmp_path
    ctx.bin = bin_
    return ctx


def assert_no_secrets(text: str):
    for s in SECRETS:
        assert s not in text, f"secret leaked: {s[:6]}…"
    for frag in ("PLANTED", "planted", "hunter2"):
        assert frag not in text, f"secret fragment leaked: {frag}"
