import os
from pathlib import Path

from ide_toolbox.core.models import PathState
from ide_toolbox.core.parsers import load_structured, read_front_matter, strip_jsonc, MAX_BYTES
from ide_toolbox.core.paths import path_state
from ide_toolbox.core.redact import looks_secret, safe_text, summarize_mapping
from ide_toolbox.core.settings import Settings


def test_path_states(tmp_path):
    f = tmp_path / "f"; f.write_text("x")
    assert path_state(f) == PathState.EXISTS
    assert path_state(tmp_path / "nope") == PathState.MISSING
    os.symlink(tmp_path / "gone", tmp_path / "link")
    assert path_state(tmp_path / "link") == PathState.BROKEN_SYMLINK
    d = tmp_path / "locked"; d.mkdir(); d.chmod(0)
    try:
        if os.geteuid() != 0:
            assert path_state(d) == PathState.UNREADABLE
    finally:
        d.chmod(0o755)


def test_secret_detection():
    for s in ["sk-abcdefgh12345678", "ghp_ABCDEFGH12345678", "Bearer xyz",
              "https://u:p@host/x", "eyJabcdefgh.eyJabcdefgh.sig", "Zx8Kq2Lm9Pw4Rt7Yv1Bn6Cd3Fg5Hj0Sa"]:
        assert looks_secret(s), s
        assert safe_text(s) == "•••"
    for s in ["github", "brainstorm", "1.145.2", "2.1.319 (Claude Code)"]:
        assert not looks_secret(s)


def test_summary_types_only():
    rows = dict(summarize_mapping({"model": "secretvalue", "apiKey": "x", "nested": {"token": 1, "n": 2}}))
    assert rows["model"] == "string (value hidden)"
    assert rows["apiKey"] == "hidden"
    assert rows["nested.token"] == "hidden"
    assert "secretvalue" not in repr(rows)


def test_jsonc():
    assert load_structured  # noqa
    txt = '{"a": "http://x//y", /* c */ "b": [1,2,],}'
    import json
    assert json.loads(strip_jsonc(txt)) == {"a": "http://x//y", "b": [1, 2]}


def test_parse_errors_no_content(tmp_path):
    f = tmp_path / "bad.json"; f.write_text('{\n"secretvalue": \n')
    r = load_structured(f)
    assert r.error == "PARSE_ERROR" and r.line and "secretvalue" not in repr(r)
    big = tmp_path / "big.json"; big.write_bytes(b" " * (MAX_BYTES + 1))
    assert load_structured(big).error == "TOO_LARGE"
    assert load_structured(tmp_path / "x.json").error == "MISSING"
    assert load_structured(tmp_path / "x.txt").error == "UNSUPPORTED_FORMAT"
    t = tmp_path / "c.toml"; t.write_text("a = [")
    assert load_structured(t).error == "PARSE_ERROR"
    y = tmp_path / "c.yaml"; y.write_text("a: [")
    assert load_structured(y).error == "PARSE_ERROR"
    m = tmp_path / "S.md"; m.write_text("---\nname: n\n---\n")
    assert read_front_matter(m).data == {"name": "n"}


def test_settings_roundtrip(tmp_path):
    s = Settings(tmp_path / "cfg/settings.json")
    assert s.add_root(tmp_path)
    assert not s.add_root(tmp_path / "missing")
    assert not s.add_root(Path("relative"))
    s.save()
    s2 = Settings(s.path).load()
    assert s2.project_roots == [tmp_path]
    assert [p.name for p in s.path.parent.iterdir()] == ["settings.json"]
