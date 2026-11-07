#!/usr/bin/env bash
# Installer checks with an isolated HOME and a mocked uv (no network).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INST="$ROOT/install.sh"
T="$(mktemp -d)"; trap 'rm -rf -- "$T"' EXIT
pass=0; fail() { echo "FAIL: $*" >&2; exit 1; }; ok() { pass=$((pass+1)); }

bash -n "$INST" && ok

# --help: no writes, no network
H="$T/h0"; mkdir -p "$H"
env -i HOME="$H" PATH=/usr/bin:/bin bash "$INST" --help | grep -q "Usage:" && ok
[[ -z "$(ls -A "$H")" ]] || fail "--help wrote files"; ok

# mock uv: creates .venv/bin/ide-toolbox
MB="$T/mockbin"; mkdir -p "$MB"
cat > "$MB/uv" <<'UV'
#!/usr/bin/env bash
mkdir -p .venv/bin; printf '#!/bin/sh\necho ran\n' > .venv/bin/ide-toolbox; chmod +x .venv/bin/ide-toolbox
UV
chmod +x "$MB/uv"
run() { env -i HOME="$H" PATH="$MB:/usr/bin:/bin" "$@"; }

H="$T/h1"; mkdir -p "$H/.config/ide-toolbox"; echo keep > "$H/.config/ide-toolbox/settings.json"
run bash "$INST" --source "$ROOT" >/dev/null
APP="$H/.local/share/ide-toolbox/app"
[[ -f "$APP/.ide-toolbox-install" && -x "$APP/.venv/bin/ide-toolbox" ]] || fail "local install"; ok
[[ "$(run "$H/.local/bin/ide-toolbox")" == "ran" ]] || fail "command link"; ok
grep -qx "X-IDE-Toolbox-Installer=true" "$H/.local/share/applications/ide-toolbox.desktop" || fail desktop; ok
[[ ! -e "$APP/.git" && ! -e "$APP/.pytest_cache" ]] || fail "copied junk"; ok
# idempotent re-run
run bash "$INST" --source "$ROOT" >/dev/null && ok
# remote mode via file:// archive
tar -C "$(dirname "$ROOT")" -czf "$T/src.tar.gz" --exclude=.venv --exclude=.git "$(basename "$ROOT")"
run env IDE_TOOLBOX_ARCHIVE_URL="file://$T/src.tar.gz" bash "$INST" --no-desktop >/dev/null && ok
# http URL rejected
run env IDE_TOOLBOX_ARCHIVE_URL="http://example.invalid/x.tgz" bash "$INST" >/dev/null 2>&1 && fail "http accepted"; ok
# uninstall keeps settings
run bash "$INST" --uninstall >/dev/null
[[ ! -e "$APP" && ! -e "$H/.local/bin/ide-toolbox" && ! -e "$H/.local/share/applications/ide-toolbox.desktop" ]] || fail uninstall; ok
[[ "$(cat "$H/.config/ide-toolbox/settings.json")" == keep ]] || fail "settings lost"; ok

# refuses foreign dir / foreign command
H="$T/h2"; mkdir -p "$H/.local/share/ide-toolbox/app" "$H/.local/bin"; echo mine > "$H/.local/share/ide-toolbox/app/f"
run bash "$INST" --source "$ROOT" >/dev/null 2>&1 && fail "foreign dir overwritten"; ok
[[ -f "$H/.local/share/ide-toolbox/app/f" ]] || fail "foreign file removed"; ok
run bash "$INST" --uninstall >/dev/null; [[ -f "$H/.local/share/ide-toolbox/app/f" ]] || fail "uninstall removed foreign"; ok
H="$T/h3"; mkdir -p "$H/.local/bin"; echo other > "$H/.local/bin/ide-toolbox"
run bash "$INST" --source "$ROOT" >/dev/null 2>&1 && fail "foreign command overwritten"; ok
# no uv + bootstrap disabled -> clean failure
H="$T/h4"; mkdir -p "$H"
env -i HOME="$H" PATH=/usr/bin:/bin IDE_TOOLBOX_NO_UV_BOOTSTRAP=1 bash "$INST" --source "$ROOT" >/dev/null 2>&1 && fail "no-uv"; ok
echo "installer tests passed: $pass"
