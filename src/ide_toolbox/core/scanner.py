"""Run adapter sections with per-section deadlines; never raises."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Callable, TypeVar

from ..adapters.base import SpecAdapter
from .context import ScanContext
from .models import Detection, Section, SectionStatus, ToolReport

log = logging.getLogger("ide_toolbox")
T = TypeVar("T")
DEADLINE = 5.0


class _Timeout(Exception):
    pass


def run_with_deadline(fn: Callable[[], T], deadline: float) -> T:
    box: dict = {}

    def target():
        try:
            box["v"] = fn()
        except BaseException as e:  # noqa: BLE001
            box["e"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(deadline)
    if t.is_alive():
        raise _Timeout()
    if "e" in box:
        raise box["e"]
    return box["v"]


def _section(adapter_id: str, name: str, fn, deadline: float, counter: list[int]) -> Section:
    try:
        return run_with_deadline(fn, deadline)
    except _Timeout:
        counter[0] += 1
        log.warning("section_timeout tool=%s section=%s", adapter_id, name)
        return Section(SectionStatus.TIMED_OUT, [], [f"Stopped after {deadline:g} s"])
    except Exception as e:  # noqa: BLE001
        counter[0] += 1
        log.warning("section_error tool=%s section=%s category=%s", adapter_id, name, type(e).__name__)
        return Section(SectionStatus.UNKNOWN, [], ["Internal error while reading this section"])


def scan_tool(adapter: SpecAdapter, ctx: ScanContext, deadline: float = DEADLINE) -> ToolReport:
    errors = [0]
    # Probes have their own per-process timeouts; give them a combined budget.
    probe_budget = deadline * (2 * max(1, len(adapter.spec.clis)) + 1)
    try:
        probes = run_with_deadline(lambda: adapter.probe(ctx), probe_budget)
    except Exception as e:  # noqa: BLE001
        errors[0] += 1
        log.warning("probe_error tool=%s category=%s", adapter.id, type(e).__name__)
        probes = []
    try:
        detection = run_with_deadline(lambda: adapter.detect(ctx, probes), deadline)
    except Exception:  # noqa: BLE001
        errors[0] += 1
        detection = Detection()
    try:
        config = run_with_deadline(lambda: adapter.config_locations(ctx), deadline)
        summaries = run_with_deadline(lambda: adapter.summaries(ctx, config), deadline)
    except Exception:  # noqa: BLE001
        errors[0] += 1
        config, summaries = [], []
    skills = _section(adapter.id, "skills", lambda: adapter.skills(ctx), deadline, errors)
    plugins = _section(adapter.id, "plugins", lambda: adapter.plugins(ctx), deadline, errors)
    mcps = _section(adapter.id, "mcps", lambda: adapter.mcps(ctx), deadline, errors)
    version = next((p.version for p in probes if p.version), "")
    return ToolReport(adapter.id, adapter.display_name, detection, version, probes, config,
                      summaries, skills, plugins, mcps,
                      scanned_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), errors=errors[0])
