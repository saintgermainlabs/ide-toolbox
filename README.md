# IDE Toolbox (read-only)

A PySide6 desktop app for Ubuntu. It shows which vibe-coding / IDE tools are present and what skills, plugins/extensions and MCP servers each one has configured. It also shows where their config files live, with Open File / Open Folder / Copy Path buttons, and has an **Advanced** page for CLI diagnostics: state, version, path, install source and duplicate copies.

The app is **read-only**. It never edits configs, installs or removes anything, or connects to MCP servers, and it never reads credential stores or app databases. Values from config files are never shown. To see or edit a file, use **Open File**, which opens it in your own editor.

## Install (one command, user-level, no sudo)

```bash
curl -fsSL https://raw.githubusercontent.com/saintgermainlabs/ide-toolbox/main/install.sh | bash
```

Prefer to read the script first:

```bash
curl -fsSLO https://raw.githubusercontent.com/saintgermainlabs/ide-toolbox/main/install.sh
less install.sh
bash install.sh
```

The installer:
- Downloads this repo's source archive over HTTPS into `~/.local/share/ide-toolbox/app`.
- Creates the app's own environment with [uv](https://docs.astral.sh/uv/). That step downloads Python 3.13 and the locked PySide6 wheels. If uv is missing, the installer first fetches it from the official `https://astral.sh/uv/install.sh`, or you can set `IDE_TOOLBOX_NO_UV_BOOTSTRAP=1` to stop instead.
- Adds the command `~/.local/bin/ide-toolbox` and an "IDE Toolbox" app-menu launcher.

It never uses sudo and doesn't start the app. Running it again updates the app. Options:

```bash
bash install.sh --help
bash install.sh --source /path/to/checkout   # install from a local clone
bash install.sh --no-desktop                 # skip the app-menu launcher
bash install.sh --uninstall                  # remove app, command and launcher (keeps settings)
```

The installer refuses to overwrite an existing `~/.local/share/ide-toolbox/app` or `~/.local/bin/ide-toolbox` that it didn't create.

## Use
- One tab per detected tool, each with **Overview / Skills / Plugins / MCPs / Configuration** sub-tabs.
- Tick **Show undetected tools** to also show tools with no signal at all (marked "missing").
- **Add project folder…** adds a project's `.cursor/`, `.claude/`, `.mcp.json`, `.vscode/mcp.json`, `opencode.json`, `.gemini/settings.json` and `.aider.conf.yml` to the scan. Only those fixed paths are checked.
- Section states are OK, Empty, Missing, Unreadable, ParseError, Unsupported, Unknown and TimedOut.

## Files the app writes
Only `~/.config/ide-toolbox/settings.json` (your project list and the toggle) and `~/.cache/ide-toolbox/log.txt` (rotated; error categories and tool IDs only).

## Develop
```bash
uv sync
QT_QPA_PLATFORM=offscreen uv run pytest -q
uv build   # wheel + sdist in dist/
```
Installer tests: `bash tests/test_installer.sh` (mocked uv, no network). Adapter paths: `docs/ADAPTERS.md`.

## Known limits (v1)
- Scans are offline: no network calls, and MCP servers are never started, so MCP status is always "Configured (not checked)".
- Some tools or sections are reported as Unsupported or Unknown rather than guessed.
- License: none has been chosen yet, so default copyright applies.
- No live MCP status, no export, no editing.
- Kiro, Crush, Copilot CLI, Antigravity and Kimi Code only get detection and folder checks.
- Tested offscreen with synthetic fixtures only. Check on your real Wayland session that Open File / Open Folder open your default apps.
