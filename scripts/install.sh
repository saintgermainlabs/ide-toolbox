#!/usr/bin/env bash
# Creates the app's own venv with uv (Python 3.13, pinned PySide6 from uv.lock).
# Optional:  --desktop  also writes a user-level launcher (~/.local/share/applications/ide-toolbox.desktop)
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
uv sync --frozen --no-dev
echo "Installed. Run with: $(pwd)/scripts/run.sh"
if [[ "${1:-}" == "--desktop" ]]; then
  dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  mkdir -p "$dir"
  cat > "$dir/ide-toolbox.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=IDE Toolbox
Comment=Read-only inventory of vibe-coding and IDE tools
Exec=$(pwd)/scripts/run.sh
Icon=utilities-terminal
Terminal=false
Categories=Development;
DESK
  echo "Launcher written: $dir/ide-toolbox.desktop"
fi
