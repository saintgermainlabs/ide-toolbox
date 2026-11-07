"""Bounded parsers for the supported formats. Errors never carry file contents."""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml

MAX_BYTES = 2 * 1024 * 1024


@dataclass
class ParseResult:
    data: object = None
    error: str = ""  # "" | MISSING | UNREADABLE | TOO_LARGE | PARSE_ERROR | UNSUPPORTED_FORMAT
    line: int | None = None

    @property
    def ok(self) -> bool:
        return not self.error


def _read(path: Path) -> tuple[str | None, str]:
    try:
        if not path.exists():
            return None, "MISSING"
        if not path.is_file():
            return None, "UNREADABLE"
        if path.stat().st_size > MAX_BYTES:
            return None, "TOO_LARGE"
        with path.open("rb") as fh:
            raw = fh.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None, "TOO_LARGE"
        return raw.decode("utf-8", errors="replace"), ""
    except (PermissionError, OSError):
        return None, "UNREADABLE"


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas, respecting strings."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            seg = text[i: n if j < 0 else j + 2]
            out.append("\n" * seg.count("\n"))  # keep line numbers
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_structured(path: Path, fmt: str | None = None) -> ParseResult:
    fmt = fmt or {".json": "jsonc", ".jsonc": "jsonc", ".toml": "toml",
                  ".yml": "yaml", ".yaml": "yaml"}.get(path.suffix.lower(), "")
    if not fmt:
        return ParseResult(error="UNSUPPORTED_FORMAT")
    text, err = _read(path)
    if err:
        return ParseResult(error=err)
    assert text is not None
    try:
        if fmt in ("json", "jsonc"):
            return ParseResult(data=json.loads(strip_jsonc(text)))
        if fmt == "toml":
            return ParseResult(data=tomllib.loads(text))
        if fmt == "yaml":
            return ParseResult(data=yaml.safe_load(text))
    except json.JSONDecodeError as e:
        return ParseResult(error="PARSE_ERROR", line=e.lineno)
    except tomllib.TOMLDecodeError as e:
        return ParseResult(error="PARSE_ERROR", line=getattr(e, "lineno", None))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        return ParseResult(error="PARSE_ERROR", line=(mark.line + 1) if mark else None)
    except (ValueError, RecursionError):
        return ParseResult(error="PARSE_ERROR")
    return ParseResult(error="UNSUPPORTED_FORMAT")


def read_front_matter(path: Path) -> ParseResult:
    text, err = _read(path)
    if err:
        return ParseResult(error=err)
    assert text is not None
    if not text.startswith("---"):
        return ParseResult(data={})
    end = text.find("\n---", 3)
    if end < 0:
        return ParseResult(error="PARSE_ERROR", line=1)
    try:
        data = yaml.safe_load(text[3:end])
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        return ParseResult(error="PARSE_ERROR", line=(mark.line + 2) if mark else None)
    return ParseResult(data=data if isinstance(data, dict) else {})
