import time

from conftest import exe
from ide_toolbox.core.models import ProbeState
from ide_toolbox.core.probe import OUTPUT_CAP, ProbeRunner, ProbeSpec, install_source, probe_cli, which_all


def test_rejects_unlisted(tmp_path):
    exe(tmp_path, "tool", "touch RAN")
    r = ProbeRunner(str(tmp_path), set())
    assert r.run(ProbeSpec(("tool", "--version"))).state == "rejected"
    assert not (tmp_path / "RAN").exists()


def test_path_placeholder_only_dpkg(tmp_path):
    spec = ProbeSpec(("tool", "{path}"))
    r = ProbeRunner(str(tmp_path), {spec.argv})
    assert r.run(spec, "/etc/passwd").state == "rejected"


def test_timeout_and_cap(tmp_path):
    exe(tmp_path, "hang", "sleep 30")
    exe(tmp_path, "loud", "yes aaaaaaaaaaaaaaaa")
    hang = ProbeSpec(("hang", "--version"), timeout=0.5)
    loud = ProbeSpec(("loud", "--version"))
    r = ProbeRunner(str(tmp_path), {hang.argv, loud.argv})
    t = time.monotonic()
    assert r.run(hang).state == "timeout"
    assert time.monotonic() - t < 3
    out = r.run(loud)
    assert out.state == "ok" and len(out.output) <= OUTPUT_CAP


def test_probe_states(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    exe(a, "t", "echo 1.2.3"); exe(b, "t", "echo 9"); exe(a, "quiet", "true")
    r = ProbeRunner(f"{a}:{b}", {("t", "--version"), ("quiet", "--version")})
    res = probe_cli(r, "t", ProbeSpec(("t", "--version")), tmp_path)
    assert res.state == ProbeState.FOUND and res.version == "1.2.3" and res.duplicates == (str(b / "t"),)
    assert probe_cli(r, "quiet", ProbeSpec(("quiet", "--version")), tmp_path).state == ProbeState.FOUND_NO_VERSION
    assert probe_cli(r, "none", ProbeSpec(("none", "--version")), tmp_path).state == ProbeState.NOT_ON_PATH
    assert which_all("../t", str(a)) == []


def test_install_source(tmp_path):
    h = tmp_path
    assert install_source("/snap/bin/code", h) == "snap"
    assert install_source(f"{h}/.local/share/mise/installs/gh/x/gh", h) == "mise"
    assert install_source(f"{h}/.local/bin/claude", h) == "~/.local/bin"
    assert install_source("/usr/share/code/bin/code", h, "code") == "apt/dpkg (code)"
    assert install_source("/opt/x", h) == "Unknown"
