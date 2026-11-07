"""Allowlisted, bounded subprocess probes. No shell, stdin closed, deadline, output cap."""
from __future__ import annotations

import os
import selectors
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .models import ProbeResult, ProbeState
from .redact import safe_text

OUTPUT_CAP = 64 * 1024
DEFAULT_TIMEOUT = 5.0


@dataclass(frozen=True)
class ProbeSpec:
    """argv[0] is a bare program name resolved on PATH; the rest are fixed literals.
    A trailing "{path}" placeholder is only allowed for dpkg -S."""
    argv: tuple[str, ...]
    timeout: float = DEFAULT_TIMEOUT


@dataclass
class RunOutcome:
    state: str  # ok | timeout | error | missing | rejected
    returncode: int | None = None
    output: str = ""


def which_all(name: str, path_env: str) -> list[str]:
    if "/" in name or not name:
        return []
    found: list[str] = []
    for d in path_env.split(os.pathsep):
        if not d:
            continue
        p = Path(d) / name
        try:
            if p.is_file() and os.access(p, os.X_OK) and str(p) not in found:
                found.append(str(p))
        except OSError:
            continue
    return found


def install_source(resolved: str, home: Path, dpkg_owner: str = "") -> str:
    r = resolved
    h = str(home)
    if r.startswith("/snap/"):
        return "snap"
    if "/flatpak/" in r:
        return "flatpak"
    if r.startswith(f"{h}/.local/share/mise/") or "/mise/installs/" in r:
        return "mise"
    if "/node_modules/" in r or "/.npm-global/" in r or "/.nvm/" in r:
        return "npm global"
    if r.startswith(f"{h}/.local/bin/"):
        return "~/.local/bin"
    if r.startswith(f"{h}/.local/share/uv/") or "/uv/tools/" in r:
        return "uv tool"
    if r.startswith(f"{h}/.local/pipx/") or "/pipx/venvs/" in r:
        return "pipx"
    if dpkg_owner:
        return f"apt/dpkg ({dpkg_owner})"
    if r.startswith(h):
        return "user install"
    return "Unknown"


class ProbeRunner:
    """Runs only ProbeSpecs that were registered in the allowlist."""

    def __init__(self, path_env: str, allowlist: set[tuple[str, ...]] | None = None,
                 env: dict[str, str] | None = None):
        self.path_env = path_env
        self.allowlist = set(allowlist or ())
        self.env = env

    def allow(self, spec: ProbeSpec) -> None:
        self.allowlist.add(spec.argv)

    def run(self, spec: ProbeSpec, path_arg: str | None = None) -> RunOutcome:
        if spec.argv not in self.allowlist:
            return RunOutcome("rejected")
        argv = list(spec.argv)
        if "{path}" in argv:
            if argv[0] != "dpkg" or not path_arg or not os.path.isabs(path_arg):
                return RunOutcome("rejected")
            argv = [path_arg if a == "{path}" else a for a in argv]
        exe = which_all(argv[0], self.path_env)
        if not exe:
            return RunOutcome("missing")
        argv[0] = exe[0]
        return _bounded_run(argv, spec.timeout, self.env)


def _bounded_run(argv: list[str], timeout: float, env: dict[str, str] | None) -> RunOutcome:
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, shell=False, env=env,
                                start_new_session=True, close_fds=True)
    except OSError:
        return RunOutcome("error")
    buf = bytearray()
    deadline = time.monotonic() + timeout
    sel = selectors.DefaultSelector()
    assert proc.stdout is not None
    sel.register(proc.stdout, selectors.EVENT_READ)
    timed_out = False
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                timed_out = True
                break
            events = sel.select(min(left, 0.2))
            if events:
                chunk = os.read(proc.stdout.fileno(), 8192)
                if not chunk:
                    break
                if len(buf) < OUTPUT_CAP:
                    buf += chunk[: OUTPUT_CAP - len(buf)]
                else:
                    break  # cap reached; stop reading
            elif proc.poll() is not None:
                break
    finally:
        sel.close()
    if timed_out or proc.poll() is None:
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            proc.kill()
    try:
        rc = proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        rc = None
    proc.stdout.close()
    if timed_out:
        return RunOutcome("timeout")
    return RunOutcome("ok", rc, buf.decode("utf-8", errors="replace"))


def first_version_line(output: str) -> str:
    for line in output.splitlines():
        line = line.strip()
        if line:
            return safe_text(line, 120)
    return ""


def probe_cli(runner: ProbeRunner, name: str, spec: ProbeSpec, home: Path,
              dpkg_spec: ProbeSpec | None = None) -> ProbeResult:
    paths = which_all(name, runner.path_env)
    if not paths:
        return ProbeResult(name=name, state=ProbeState.NOT_ON_PATH)
    path = paths[0]
    resolved = os.path.realpath(path)
    owner = ""
    if dpkg_spec is not None and resolved.startswith(("/usr/", "/opt/", "/bin/")):
        out = runner.run(dpkg_spec, path_arg=resolved)
        if out.state == "ok" and out.returncode == 0 and ":" in out.output:
            owner = safe_text(out.output.split(":", 1)[0], 60)
    res = ProbeResult(name=name, state=ProbeState.FOUND, path=path, resolved=resolved,
                      source=install_source(resolved, home, owner), duplicates=tuple(paths[1:]))
    out = runner.run(spec)
    if out.state == "timeout":
        res.state = ProbeState.TIMED_OUT
    elif out.state == "rejected":
        res.state = ProbeState.REJECTED
    elif out.state != "ok":
        res.state = ProbeState.ERROR
    else:
        v = first_version_line(out.output)
        if not v:
            res.state = ProbeState.FOUND_NO_VERSION
        elif out.returncode not in (0, None):
            res.state = ProbeState.ERROR
        else:
            res.version = v
    return res
