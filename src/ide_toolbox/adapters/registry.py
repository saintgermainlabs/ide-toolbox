"""All v1 tool definitions. Paths follow each tool's documented user/project locations
(checked against public docs at design time; see docs/ADAPTERS.md). Change here only."""
from __future__ import annotations

from .base import Loc, McpSource, PluginSource, SpecAdapter, ToolSpec

EDITOR_EXT_NOTE = ("AI extensions (e.g. Cline, Kilo Code) are listed as plugins; their own MCP "
                   "settings live in extension storage and are not read in v1.")

SPECS: list[ToolSpec] = [
    ToolSpec(
        id="cursor", name="Cursor", clis=("cursor", "cursor-agent"),
        desktop_files=("cursor.desktop",),
        config=(Loc("Cursor home", ".cursor", "dir"), Loc("User MCP config", ".cursor/mcp.json"),
                Loc("User settings", ".config/Cursor/User/settings.json"),
                Loc("App config folder", ".config/Cursor", "dir"),
                Loc("Skills folder", ".cursor/skills", "dir"),
                Loc("Project .cursor", ".cursor", "dir", project=True),
                Loc("Project MCP config", ".cursor/mcp.json", project=True)),
        skill_dirs=(Loc("", ".cursor/skills", "dir"), Loc("", ".cursor/skills", "dir", project=True)),
        plugins=(PluginSource("ext_dir", ".cursor/extensions"),),
        mcps=(McpSource(".cursor/mcp.json", ("mcpServers",)),
              McpSource(".cursor/mcp.json", ("mcpServers",), project=True)),
        notes={"mcps_extra": EDITOR_EXT_NOTE},
        access="~/.cursor/mcp.json, ~/.cursor/skills/*/SKILL.md, ~/.cursor/extensions/*/package.json"),
    ToolSpec(
        id="vscode", name="VS Code", clis=("code",),
        desktop_files=("code.desktop", "com.microsoft.VSCode.desktop", "code_code.desktop"),
        config=(Loc("User settings", ".config/Code/User/settings.json"),
                Loc("User MCP config", ".config/Code/User/mcp.json"),
                Loc("App config folder", ".config/Code", "dir"),
                Loc("Extensions folder", ".vscode/extensions", "dir"),
                Loc("Project .vscode", ".vscode", "dir", project=True),
                Loc("Project MCP config", ".vscode/mcp.json", project=True)),
        skill_dirs=None,
        plugins=(PluginSource("cli_list", keys=("code", "--list-extensions", "--show-versions")),
                 PluginSource("ext_dir", ".vscode/extensions")),
        mcps=(McpSource(".config/Code/User/mcp.json", ("servers",)),
              McpSource(".vscode/mcp.json", ("servers",), project=True)),
        notes={"skills": "VS Code has no skills concept in v1.", "mcps_extra": EDITOR_EXT_NOTE},
        access="code --list-extensions --show-versions; ~/.config/Code/User/mcp.json"),
    ToolSpec(
        id="claude", name="Claude Code", clis=("claude",),
        desktop_files=("claude-code-url-handler.desktop",),
        config=(Loc("Claude home", ".claude", "dir"), Loc("User state/MCP file", ".claude.json"),
                Loc("User settings", ".claude/settings.json"),
                Loc("Skills folder", ".claude/skills", "dir"),
                Loc("Plugins folder", ".claude/plugins", "dir"),
                Loc("Project .claude", ".claude", "dir", project=True),
                Loc("Project MCP config", ".mcp.json", project=True),
                Loc("Project settings", ".claude/settings.json", project=True)),
        skill_dirs=(Loc("", ".claude/skills", "dir"), Loc("", ".claude/skills", "dir", project=True)),
        plugins=(PluginSource("manifest_glob", ".claude/plugins",
                              pattern="cache/*/*/*/.claude-plugin/plugin.json"),),
        mcps=(McpSource(".claude.json", ("mcpServers",)),
              McpSource(".mcp.json", ("mcpServers",), project=True)),
        access="~/.claude.json (top-level mcpServers only), .mcp.json, plugin.json manifests"),
    ToolSpec(
        id="codex", name="Codex", clis=("codex",),
        config=(Loc("Codex home", ".codex", "dir"), Loc("Config", ".codex/config.toml"),
                Loc("Skills folder", ".codex/skills", "dir")),
        skill_dirs=(Loc("", ".codex/skills", "dir"),),
        plugins=None,
        mcps=(McpSource(".codex/config.toml", ("mcp_servers",)),),
        access="~/.codex/config.toml [mcp_servers.*], ~/.codex/skills/*/SKILL.md"),
    ToolSpec(
        id="opencode", name="OpenCode", clis=("opencode",),
        desktop_files=("ai.opencode.desktop.desktop", "opencode-desktop.desktop"),
        config=(Loc("Config folder", ".config/opencode", "dir"),
                Loc("Global config", ".config/opencode/opencode.json"),
                Loc("Data folder", ".opencode", "dir"),
                Loc("Project config", "opencode.json", project=True),
                Loc("Project .opencode", ".opencode", "dir", project=True)),
        skill_dirs=None,
        plugins=(PluginSource("json_list", ".config/opencode/opencode.json", ("plugin",)),
                 PluginSource("json_list", "opencode.json", ("plugin",), project=True)),
        mcps=(McpSource(".config/opencode/opencode.json", ("mcp",)),
              McpSource("opencode.json", ("mcp",), project=True)),
        access="opencode.json keys 'plugin' and 'mcp'"),
    ToolSpec(
        id="gemini", name="Gemini CLI", clis=("gemini",),
        config=(Loc("Gemini home", ".gemini", "dir"), Loc("User settings", ".gemini/settings.json"),
                Loc("Extensions folder", ".gemini/extensions", "dir"),
                Loc("Project settings", ".gemini/settings.json", project=True)),
        skill_dirs=None,
        plugins=(PluginSource("manifest_glob", ".gemini/extensions", pattern="*/gemini-extension.json"),),
        mcps=(McpSource(".gemini/settings.json", ("mcpServers",)),
              McpSource(".gemini/settings.json", ("mcpServers",), project=True)),
        access="~/.gemini/settings.json mcpServers; extensions/*/gemini-extension.json"),
    ToolSpec(
        id="aider", name="Aider", clis=("aider",),
        config=(Loc("User config", ".aider.conf.yml"),
                Loc("Project config", ".aider.conf.yml", project=True)),
        skill_dirs=None, plugins=None, mcps=None,
        notes={"skills": "Aider has no skills concept.", "plugins": "Aider has no plugin system.",
               "mcps": "Aider has no documented MCP configuration."},
        access="~/.aider.conf.yml (key names only)"),
    ToolSpec(
        id="kiro", name="Kiro", clis=("kiro",), desktop_files=("kiro.desktop",),
        config=(Loc("Kiro home", ".kiro", "dir"),),
        skill_dirs=None, unknown=("plugins", "mcps"), access="~/.kiro presence only"),
    ToolSpec(
        id="crush", name="Crush", clis=("crush",),
        config=(Loc("Config folder", ".config/crush", "dir"),),
        skill_dirs=None, unknown=("plugins", "mcps"), access="CLI and folder presence only"),
    ToolSpec(
        id="copilot", name="GitHub Copilot CLI", clis=("copilot",),
        config=(Loc("Copilot home", ".copilot", "dir"),),
        skill_dirs=None, unknown=("plugins", "mcps"), access="CLI and folder presence only"),
    ToolSpec(
        id="antigravity", name="Antigravity", clis=("antigravity",),
        desktop_files=("antigravity.desktop",),
        skill_dirs=None, unknown=("plugins", "mcps"), access="Desktop entry presence only"),
    ToolSpec(
        id="kimi", name="Kimi Code", clis=("kimi",), desktop_files=("kimi-code.desktop",),
        skill_dirs=None, unknown=("plugins", "mcps"), access="Desktop entry presence only"),
    ToolSpec(id="gh", name="GitHub CLI (gh)", clis=("gh",), advanced_only=True),
]


def all_adapters() -> list[SpecAdapter]:
    return [SpecAdapter(s) for s in SPECS]


def build_allowlist() -> set[tuple[str, ...]]:
    from .base import DPKG_SPEC
    allow = {DPKG_SPEC.argv}
    for s in SPECS:
        for v in s.version_specs:
            allow.add(v.argv)
        for p in s.plugins or ():
            if p.kind == "cli_list":
                allow.add(p.keys)
    return allow
