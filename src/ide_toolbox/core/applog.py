"""Category-only rotating log under the app cache dir."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .settings import cache_dir


def setup_logging() -> None:
    d = cache_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(d / "log.txt", maxBytes=256_000, backupCount=2, encoding="utf-8")
    except OSError:
        return
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    lg = logging.getLogger("ide_toolbox")
    lg.setLevel(logging.INFO)
    lg.addHandler(h)
    lg.propagate = False
