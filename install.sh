#!/usr/bin/env bash
# IDE Toolbox – one-command, user-level installer for Ubuntu/Linux (no sudo).
#
#   curl -fsSL https://raw.githubusercontent.com/saintgermainlabs/ide-toolbox/main/install.sh | bash
#
# What it does:
#   1. Downloads the source archive of this repo over HTTPS (or uses --source DIR).
#   2. Installs it into  ${XDG_DATA_HOME:-~/.local/share}/ide-toolbox/app
#   3. Creates the app's own virtualenv with uv (Python 3.13 + locked PySide6).
#      If uv is missing it is installed from the official https://astral.sh/uv/install.sh.
#   4. Adds the command  ~/.local/bin/ide-toolbox  and an app-menu launcher.
# It never launches the app, never uses sudo, and keeps ~/.config/ide-toolbox and ~/.cache/ide-toolbox.
set -euo pipefail

REPO="saintgermainlabs/ide-toolbox"
REF="${IDE_TOOLBOX_REF:-main}"
ARCHIVE_URL="${IDE_TOOLBOX_ARCHIVE_URL:-https://codeload.github.com/${REPO}/tar.gz/refs/heads/${REF}}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_ROOT="$DATA_HOME/ide-toolbox"
APP_DIR="$APP_ROOT/app"
BIN_DIR="${IDE_TOOLBOX_BIN_DIR:-$HOME/.local/bin}"
BIN_LINK="$BIN_DIR/ide-toolbox"
DESKTOP_FILE="$DATA_HOME/applications/ide-toolbox.desktop"
MARKER=".ide-toolbox-install"
DESKTOP_TAG="X-IDE-Toolbox-Installer=true"

MODE="remote" SOURCE="" DESKTOP=1 ACTION="install"

usage() {
  cat <<USAGE
IDE Toolbox installer (user-level, no sudo)

Usage: install.sh [--source DIR] [--no-desktop] [--uninstall] [--help]

  (default)       download ${REPO}@${REF} over HTTPS and install/update it
  --source DIR    install from a local checkout instead of downloading
  --no-desktop    do not create the app-menu launcher
  --uninstall     remove the installed app, command link and launcher
                  (settings in ~/.config/ide-toolbox and ~/.cache/ide-toolbox are kept)
  --help          show this help

Installs into: $APP_DIR
Command:       $BIN_LINK
Environment:   IDE_TOOLBOX_REF (branch, default main), IDE_TOOLBOX_NO_UV_BOOTSTRAP=1 (fail instead of installing uv)
USAGE
}

say() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --uninstall) ACTION="uninstall" ;;
    --no-desktop) DESKTOP=0 ;;
    --source) [[ $# -ge 2 ]] || die "--source needs a directory"; MODE="local"; SOURCE="$2"; shift ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
  shift
done

[[ "$(id -u)" -ne 0 ]] || die "run as your normal user, not root"
[[ -n "${HOME:-}" ]] || die "HOME is not set"

owned_app()     { [[ -f "$APP_DIR/$MARKER" ]]; }
owned_link()    { [[ -L "$BIN_LINK" && "$(readlink "$BIN_LINK")" == "$APP_DIR/scripts/run.sh" ]]; }
owned_desktop() { [[ -f "$DESKTOP_FILE" ]] && grep -qx "$DESKTOP_TAG" "$DESKTOP_FILE"; }

uninstall() {
  owned_link && rm -f -- "$BIN_LINK" && say "removed $BIN_LINK"
  owned_desktop && rm -f -- "$DESKTOP_FILE" && say "removed $DESKTOP_FILE"
  if owned_app; then
    rm -rf -- "$APP_DIR" && say "removed $APP_DIR"
    rmdir -- "$APP_ROOT" 2>/dev/null || true
  elif [[ -e "$APP_DIR" ]]; then
    say "left $APP_DIR alone (not created by this installer)"
  fi
  say "settings and logs (~/.config/ide-toolbox, ~/.cache/ide-toolbox) were kept"
}

if [[ "$ACTION" == "uninstall" ]]; then uninstall; exit 0; fi

# ---- preflight --------------------------------------------------------------
[[ "$(uname -s)" == "Linux" ]] || die "this installer supports Linux only"
for c in tar mktemp readlink grep; do command -v "$c" >/dev/null || die "missing required command: $c"; done
if [[ "$MODE" == "remote" ]]; then command -v curl >/dev/null || die "curl is required (sudo apt install curl)"; fi
if [[ -e "$APP_DIR" ]] && ! owned_app; then
  die "$APP_DIR exists but was not created by this installer; refusing to touch it"
fi
if [[ -e "$BIN_LINK" || -L "$BIN_LINK" ]] && ! owned_link; then
  die "$BIN_LINK already exists and is not ours; refusing to overwrite it"
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ide-toolbox.XXXXXXXX")"
cleanup() { rm -rf -- "$TMP"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

# ---- uv ---------------------------------------------------------------------
UV="$(command -v uv || true)"
[[ -n "$UV" || ! -x "$HOME/.local/bin/uv" ]] || UV="$HOME/.local/bin/uv"
if [[ -z "$UV" ]]; then
  [[ "${IDE_TOOLBOX_NO_UV_BOOTSTRAP:-0}" != "1" ]] || die "uv not found (https://docs.astral.sh/uv/)"
  command -v curl >/dev/null || die "uv not found and curl missing to install it"
  say "uv not found – installing it from the official installer https://astral.sh/uv/install.sh (user-level)"
  curl -fsSL --proto '=https' --tlsv1.2 https://astral.sh/uv/install.sh -o "$TMP/uv-install.sh"
  UV_NO_MODIFY_PATH=1 sh "$TMP/uv-install.sh"
  UV="$HOME/.local/bin/uv"
  [[ -x "$UV" ]] || die "uv installation failed"
fi

# ---- fetch source -----------------------------------------------------------
NEW="$TMP/new"
mkdir -p "$NEW"
if [[ "$MODE" == "local" ]]; then
  SOURCE="$(cd "$SOURCE" && pwd)" || die "source directory not found"
  [[ -f "$SOURCE/pyproject.toml" && -f "$SOURCE/scripts/install.sh" ]] || die "$SOURCE is not an ide-toolbox checkout"
  say "installing from local source: $SOURCE"
  tar -C "$SOURCE" --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=dist -cf - . | tar -C "$NEW" -xf -
else
  say "downloading $ARCHIVE_URL"
  case "$ARCHIVE_URL" in https://*|file://*) ;; *) die "archive URL must be https" ;; esac
  curl -fsSL --proto '=https,file' --tlsv1.2 "$ARCHIVE_URL" -o "$TMP/src.tar.gz"
  tar -xzf "$TMP/src.tar.gz" -C "$NEW" --strip-components=1 --no-same-owner
  [[ -f "$NEW/pyproject.toml" && -f "$NEW/scripts/install.sh" ]] || die "downloaded archive does not look like ide-toolbox"
fi
touch "$NEW/$MARKER"

# ---- swap into place, then build the venv (restore previous copy on failure) ----
mkdir -p "$APP_ROOT"
HAD_OLD=0
if owned_app; then mv -- "$APP_DIR" "$TMP/old"; HAD_OLD=1; fi
mv -- "$NEW" "$APP_DIR"
say "creating the app environment with uv (downloads Python 3.13 and PySide6 if needed)"
if ! (cd "$APP_DIR" && PATH="$(dirname "$UV"):$PATH" bash scripts/install.sh >/dev/null) \
   || [[ ! -x "$APP_DIR/.venv/bin/ide-toolbox" ]]; then
  rm -rf -- "$APP_DIR"
  if [[ "$HAD_OLD" -eq 1 ]]; then mv -- "$TMP/old" "$APP_DIR"; say "restored previous install"; fi
  die "environment setup failed"
fi

mkdir -p "$BIN_DIR"
ln -sfn -- "$APP_DIR/scripts/run.sh" "$BIN_LINK"

if [[ "$DESKTOP" -eq 1 ]]; then
  if [[ -e "$DESKTOP_FILE" ]] && ! owned_desktop; then
    say "skipping launcher: $DESKTOP_FILE exists and is not ours"
  else
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    cat > "$DESKTOP_FILE" <<DESK
[Desktop Entry]
Type=Application
Name=IDE Toolbox
Comment=Read-only inventory of vibe-coding and IDE tools
Exec="$APP_DIR/scripts/run.sh"
Icon=utilities-terminal
Terminal=false
Categories=Development;
$DESKTOP_TAG
DESK
    say "app-menu launcher: $DESKTOP_FILE"
  fi
fi

say "installed to $APP_DIR"
case ":$PATH:" in *":$BIN_DIR:"*) say "start it with:  ide-toolbox" ;;
  *) say "start it with:  $BIN_LINK   (add $BIN_DIR to PATH to use just 'ide-toolbox')" ;; esac
