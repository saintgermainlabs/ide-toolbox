"""Whitelist-first sanitizing. Heuristics are only a second line of defence."""
from __future__ import annotations

import math
import re
from collections import Counter

MASK = "•••"
_SENSITIVE_KEY = re.compile(r"(?i)(key|token|secret|pass|auth|cookie|bearer|credential|env|header)")
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"xox[abposr]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]*"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"[a-z][a-z0-9+.\-]*://[^\s/@]+@\S*"),  # URL userinfo
]
_SAFE_NAME = re.compile(r"[^A-Za-z0-9 ._:@/+\-()\[\]#,]")


def _entropy(s: str) -> float:
    c = Counter(s)
    n = len(s)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def looks_secret(s: str) -> bool:
    if any(p.search(s) for p in _SECRET_PATTERNS):
        return True
    for tok in re.split(r"[\s,;]+", s):
        if len(tok) >= 24 and re.fullmatch(r"[A-Za-z0-9_\-+/=.]+", tok) and _entropy(tok) > 3.7:
            return True
    return False


def key_is_sensitive(key: str) -> bool:
    return bool(_SENSITIVE_KEY.search(key))


def safe_text(value: object, limit: int = 120) -> str:
    """Return a short, printable, secret-masked string for display."""
    if value is None:
        return ""
    s = str(value).replace("\n", " ").replace("\r", " ").strip()
    s = _SAFE_NAME.sub("", s)[:limit]
    if looks_secret(s):
        return MASK
    return s


def safe_key(key: object) -> str:
    k = safe_text(key, 80)
    return k or MASK


def summarize_mapping(data: object, max_rows: int = 200) -> tuple[tuple[str, str], ...]:
    """Top-level (and one nested level) key names with value *types* only."""
    rows: list[tuple[str, str]] = []

    def kind(v: object) -> str:
        if isinstance(v, dict):
            return f"object ({len(v)} keys)"
        if isinstance(v, list):
            return f"list ({len(v)} items)"
        if isinstance(v, bool):
            return "boolean"
        if isinstance(v, (int, float)):
            return "number"
        if v is None:
            return "null"
        return "string (value hidden)"

    if not isinstance(data, dict):
        return (("(root)", kind(data)),)
    for k, v in data.items():
        if len(rows) >= max_rows:
            rows.append(("…", "truncated"))
            break
        name = safe_key(k)
        sens = key_is_sensitive(str(k))
        rows.append((name, "hidden" if sens else kind(v)))
        if isinstance(v, dict) and not sens:
            for k2, v2 in list(v.items())[:50]:
                sens2 = key_is_sensitive(str(k2))
                rows.append((f"{name}.{safe_key(k2)}", "hidden" if sens2 else kind(v2)))
    return tuple(rows)
