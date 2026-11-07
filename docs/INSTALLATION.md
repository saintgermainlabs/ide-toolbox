# Installation

Repository: https://github.com/saintgermainlabs/ide-toolbox

## One command (Ubuntu/Linux, your user only, no sudo)

```bash
curl -fsSL https://raw.githubusercontent.com/saintgermainlabs/ide-toolbox/main/install.sh | bash
```

## Inspect first

```bash
curl -fsSLO https://raw.githubusercontent.com/saintgermainlabs/ide-toolbox/main/install.sh
less install.sh
bash install.sh
```

## What it does
- Downloads this repo's `main` source archive over HTTPS into `~/.local/share/ide-toolbox/app`.
- Needs [uv](https://docs.astral.sh/uv/). If uv is missing, the installer says so and installs it for your user from the official `https://astral.sh/uv/install.sh`. To stop instead, set `IDE_TOOLBOX_NO_UV_BOOTSTRAP=1`.
- Creates the app's own environment from `uv.lock`, which downloads Python 3.13 and PySide6 6.9.2 if they aren't cached.
- Adds the command `~/.local/bin/ide-toolbox` and an **IDE Toolbox** app-menu launcher. Use `--no-desktop` to skip the launcher.
- Does not start the app. Start it with `ide-toolbox`, or with `~/.local/bin/ide-toolbox` if `~/.local/bin` is not on your PATH, or from the app menu.

## Update, reinstall, uninstall
- Run the same command again to update. If the update fails, the previous install is restored.
- The installer refuses to overwrite an `~/.local/share/ide-toolbox/app` folder, an `~/.local/bin/ide-toolbox` command or a launcher that it didn't create.
- `bash install.sh --uninstall` removes only the app folder, command and launcher it created. Your settings (`~/.config/ide-toolbox`) and logs (`~/.cache/ide-toolbox`) are kept.
- From a local clone: `bash install.sh --source /path/to/ide-toolbox`. All options: `bash install.sh --help`.

## Testing status
The installer was tested on a separate Ubuntu-based build machine. Tests used a temporary home folder, both a local source copy and the live GitHub command, and the app was started offscreen. It has **not** yet been verified on a real Wayland desktop session. After installing, please check that the window, Open File / Open Folder and the app-menu launcher work there.
