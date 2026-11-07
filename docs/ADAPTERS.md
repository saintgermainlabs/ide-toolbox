# Adapter access assumptions (v1)

Every adapter reads only the fixed locations below: `~` is $HOME and `<project>` is a folder you added explicitly. Nothing is searched recursively. Parsed formats are JSON/JSONC, TOML, YAML and Markdown front matter. Files over 2 MB are skipped, and each section lists at most 500 items.

| Tool | Detection | Skills | Plugins | MCPs |
|---|---|---|---|---|
| Cursor | `cursor`, `cursor-agent`; `cursor.desktop` | `~/.cursor/skills/*/SKILL.md`, `<project>/.cursor/skills` | `~/.cursor/extensions/*/package.json` | `mcpServers` in `~/.cursor/mcp.json`, `<project>/.cursor/mcp.json` |
| VS Code | `code`; `code.desktop`, `com.microsoft.VSCode.desktop` | Unsupported | `code --list-extensions --show-versions`, fallback `~/.vscode/extensions` | `servers` in `~/.config/Code/User/mcp.json`, `<project>/.vscode/mcp.json` |
| Claude Code | `claude`; URL-handler desktop entry | `~/.claude/skills`, `<project>/.claude/skills` | `~/.claude/plugins/cache/*/*/*/.claude-plugin/plugin.json` | top-level `mcpServers` in `~/.claude.json`, `<project>/.mcp.json` |
| Codex | `codex` | `~/.codex/skills` | Unsupported | `[mcp_servers.*]` in `~/.codex/config.toml` |
| OpenCode | `opencode`; desktop entries | Unsupported | `plugin` list in `opencode.json` | `mcp` in `~/.config/opencode/opencode.json`, `<project>/opencode.json` |
| Gemini CLI | `gemini` | Unsupported | `~/.gemini/extensions/*/gemini-extension.json` | `mcpServers` in `~/.gemini/settings.json` (+ project) |
| Aider | `aider` | Unsupported | Unsupported | Unsupported |
| Kiro / Crush / Copilot CLI | CLI + home folder | Unsupported | Unknown | Unknown |
| Antigravity / Kimi Code | desktop entry, CLI name | Unsupported | Unknown | Unknown |
| gh | `gh` (Advanced page only) | – | – | – |

Notes:
- Only the `Name=` line of `.desktop` files is read. `Exec=` is never parsed or run.
- Subprocesses are limited to the allowlist built in `adapters/registry.py:build_allowlist()`: `<cli> --version`, `code --list-extensions --show-versions` and `dpkg -S <resolved path>`. There is no shell, stdin is closed, each call has a 5 s timeout and output is capped at 64 KB. MCP `command` entries are never run.
- MCP rows show name, transport, enabled, scope, source file, and the *names* of env/header keys. URLs, args, commands and all values are never shown. State is always "Configured (not checked)".
- Editor AI extensions (Cline, Kilo Code, …) keep MCP settings in extension storage. These are not read.
- Paths were taken from each tool's public documentation at design time. If a tool changes its layout, update `registry.py`.
