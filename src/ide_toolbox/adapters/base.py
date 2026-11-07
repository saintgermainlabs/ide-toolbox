"""Declarative, read-only tool adapters.

Each ToolSpec lists *fixed* locations relative to $HOME or to a user-chosen
project root. Nothing is discovered recursively; globs have fixed depth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..core.context import ScanContext
from ..core.desktop import find_desktop_entries
from ..core.models import (MAX_ITEMS, ConfigSummary, Confidence, Detection, McpItem,
                           PathEntry, PathState, PluginItem, ProbeResult, ProbeState,
                           Section, SectionStatus, Signal, SignalKind, SkillItem)
from ..core.parsers import load_structured, read_front_matter
from ..core.paths import make_entry, path_state
from ..core.probe import ProbeSpec, probe_cli
from ..core.redact import key_is_sensitive, safe_key, safe_text, summarize_mapping

DPKG_SPEC = ProbeSpec(("dpkg", "-S", "{path}"))
ERROR_STATUS = {"MISSING": SectionStatus.MISSING, "UNREADABLE": SectionStatus.UNREADABLE,
                "TOO_LARGE": SectionStatus.UNREADABLE, "PARSE_ERROR": SectionStatus.PARSE_ERROR,
                "UNSUPPORTED_FORMAT": SectionStatus.UNSUPPORTED}
ERROR_NOTE = {"MISSING": "file not found", "UNREADABLE": "not readable",
              "TOO_LARGE": "too large (over 2 MB), not parsed", "PARSE_ERROR": "could not be parsed",
              "UNSUPPORTED_FORMAT": "format not supported"}


@dataclass(frozen=True)
class Loc:
    label: str
    rel: str            # relative to home (user) or project root
    kind: str = "file"  # file | dir
    project: bool = False


@dataclass(frozen=True)
class McpSource:
    rel: str
    keys: tuple[str, ...]  # key path to the servers mapping
    project: bool = False
    fmt: str | None = None


@dataclass(frozen=True)
class PluginSource:
    kind: str  # ext_dir | json_list | manifest_glob | cli_list
    rel: str = ""
    keys: tuple[str, ...] = ()
    pattern: str = ""
    project: bool = False


@dataclass
class ToolSpec:
    id: str
    name: str
    clis: tuple[str, ...] = ()
    desktop_files: tuple[str, ...] = ()
    config: tuple[Loc, ...] = ()
    skill_dirs: tuple[Loc, ...] | None = None        # None = Unsupported
    plugins: tuple[PluginSource, ...] | None = None  # None = Unsupported
    mcps: tuple[McpSource, ...] | None = None        # None = Unsupported
    unknown: tuple[str, ...] = ()                    # sections reported as Unknown
    notes: dict[str, str] = field(default_factory=dict)
    access: str = ""
    advanced_only: bool = False

    @property
    def version_specs(self) -> list[ProbeSpec]:
        return [ProbeSpec((c, "--version")) for c in self.clis]


def _scope(project: Path | None) -> str:
    return "User" if project is None else f"Project: {project}"


def _dig(data: object, keys: tuple[str, ...]) -> object:
    for k in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(k)
    return data


def _enabled(cfg: dict) -> str:
    if isinstance(cfg.get("disabled"), bool):
        return "No" if cfg["disabled"] else "Yes"
    if isinstance(cfg.get("enabled"), bool):
        return "Yes" if cfg["enabled"] else "No"
    return ""


def _transport(cfg: dict) -> str:
    t = cfg.get("type") or cfg.get("transport")
    if isinstance(t, str):
        t = t.lower()
        mapping = {"stdio": "stdio", "local": "stdio", "http": "http", "streamable-http": "http",
                   "streamablehttp": "http", "remote": "http", "sse": "sse"}
        if t in mapping:
            return mapping[t]
    if "command" in cfg:
        return "stdio"
    if "httpUrl" in cfg:
        return "http"
    if "url" in cfg or "serverUrl" in cfg:
        return "http"
    return "unknown"


def _key_names(v: object) -> tuple[str, ...]:
    if isinstance(v, dict):
        return tuple(safe_key(k) for k in list(v)[:50])
    return ()


class SpecAdapter:
    def __init__(self, spec: ToolSpec):
        self.spec = spec
        self.id = spec.id
        self.display_name = spec.name

    # ---- helpers -------------------------------------------------------
    def _roots(self, ctx: ScanContext, project: bool) -> list[Path | None]:
        return list(ctx.project_roots) if project else [None]

    def _base(self, ctx: ScanContext, root: Path | None) -> Path:
        return ctx.home if root is None else root

    # ---- detection -----------------------------------------------------
    def version_probes(self) -> list[ProbeSpec]:
        return self.spec.version_specs

    def probe(self, ctx: ScanContext) -> list[ProbeResult]:
        out: list[ProbeResult] = []
        for cli, spec in zip(self.spec.clis, self.spec.version_specs):
            if ctx.runner is None or not ctx.probes_enabled:
                from ..core.probe import which_all
                paths = which_all(cli, ctx.path_env)
                out.append(ProbeResult(name=cli, state=ProbeState.FOUND_NO_VERSION if paths
                                       else ProbeState.NOT_ON_PATH, path=paths[0] if paths else ""))
                continue
            out.append(probe_cli(ctx.runner, cli, spec, ctx.home, DPKG_SPEC))
        return out

    def detect(self, ctx: ScanContext, probes: list[ProbeResult]) -> Detection:
        sig: list[Signal] = []
        for p in probes:
            if p.state != ProbeState.NOT_ON_PATH:
                sig.append(Signal(SignalKind.CLI, f"{p.name}: {p.state.value}", p.path))
            if p.source.startswith(("apt", "snap", "flatpak")):
                sig.append(Signal(SignalKind.PACKAGE, p.source, p.resolved))
        for name, path in find_desktop_entries(ctx.desktop_dirs, self.spec.desktop_files):
            sig.append(Signal(SignalKind.DESKTOP, name, path))
        for loc in self.spec.config:
            if loc.project:
                continue
            p = ctx.home / loc.rel
            if path_state(p) in (PathState.EXISTS, PathState.UNREADABLE):
                sig.append(Signal(SignalKind.CONFIG, loc.label, str(p)))
        cli_ok = any(p.state == ProbeState.FOUND for p in probes)
        cli_any = any(s.kind == SignalKind.CLI for s in sig)
        desk = any(s.kind == SignalKind.DESKTOP for s in sig)
        cfg = any(s.kind == SignalKind.CONFIG for s in sig)
        if cli_ok or (desk and cfg):
            conf = Confidence.HIGH
        elif cli_any or desk:
            conf = Confidence.MEDIUM
        elif cfg:
            conf = Confidence.LOW
        else:
            conf = Confidence.NONE
        return Detection(sig, conf)

    # ---- configuration -------------------------------------------------
    def config_locations(self, ctx: ScanContext) -> list[PathEntry]:
        out = []
        for loc in self.spec.config:
            for root in self._roots(ctx, loc.project):
                out.append(make_entry(loc.label, self._base(ctx, root) / loc.rel, loc.kind, _scope(root)))
        return out

    def summaries(self, ctx: ScanContext, entries: list[PathEntry]) -> list[ConfigSummary]:
        res = []
        for e in entries:
            if e.kind != "file" or e.state != PathState.EXISTS:
                continue
            pr = load_structured(Path(e.path))
            if pr.error == "UNSUPPORTED_FORMAT":
                continue
            if not pr.ok:
                note = ERROR_NOTE[pr.error] + (f" (line {pr.line})" if pr.line else "")
                res.append(ConfigSummary(e.path, ERROR_STATUS[pr.error], (), note))
            else:
                res.append(ConfigSummary(e.path, SectionStatus.OK, summarize_mapping(pr.data),
                                         "Key names and value types only; values are hidden."))
        return res

    # ---- skills --------------------------------------------------------
    def skills(self, ctx: ScanContext) -> Section[SkillItem]:
        if self.spec.skill_dirs is None:
            return self._unsupported("skills")
        items: list[SkillItem] = []
        notes: list[str] = []
        seen_dir = False
        for loc in self.spec.skill_dirs:
            for root in self._roots(ctx, loc.project):
                d = self._base(ctx, root) / loc.rel
                st = path_state(d)
                if st == PathState.MISSING:
                    continue
                seen_dir = True
                if st != PathState.EXISTS or not d.is_dir():
                    notes.append(f"{d}: {st.value}")
                    continue
                try:
                    children = sorted(d.iterdir())
                except OSError:
                    notes.append(f"{d}: not readable")
                    continue
                for child in children:
                    if len(items) >= MAX_ITEMS:
                        notes.append(f"Truncated at {MAX_ITEMS} items")
                        break
                    md = child / "SKILL.md"
                    if not child.is_dir() or not md.is_file():
                        continue
                    fm = read_front_matter(md)
                    data = fm.data if fm.ok and isinstance(fm.data, dict) else {}
                    if not fm.ok:
                        notes.append(f"{md}: {ERROR_NOTE.get(fm.error, 'error')}")
                    items.append(SkillItem(
                        name=safe_text(data.get("name") or child.name, 80),
                        description=safe_text(data.get("description", ""), 200),
                        scope=_scope(root), source=str(md)))
        if items:
            return Section(SectionStatus.OK, items, notes)
        if not seen_dir:
            return Section(SectionStatus.MISSING, [], ["No skills folder found"])
        return Section(SectionStatus.EMPTY, [], notes)

    # ---- plugins -------------------------------------------------------
    def plugins(self, ctx: ScanContext) -> Section[PluginItem]:
        if "plugins" in self.spec.unknown:
            return self._unknown("plugins")
        if self.spec.plugins is None:
            return self._unsupported("plugins")
        items: list[PluginItem] = []
        notes: list[str] = []
        any_source = False
        for src in self.spec.plugins:
            for root in self._roots(ctx, src.project):
                got, found = self._plugin_source(ctx, src, root, notes)
                any_source |= found
                items.extend(got)
                if items and src.kind == "cli_list":
                    break
            if items and src.kind == "cli_list":
                break  # CLI list is authoritative; skip folder fallback
        if len(items) > MAX_ITEMS:
            items = items[:MAX_ITEMS]
            notes.append(f"Truncated at {MAX_ITEMS} items")
        if items:
            return Section(SectionStatus.OK, items, notes)
        if not any_source:
            return Section(SectionStatus.MISSING, [], notes or ["No plugin/extension source found"])
        return Section(SectionStatus.EMPTY, [], notes)

    def _plugin_source(self, ctx, src: PluginSource, root, notes) -> tuple[list[PluginItem], bool]:
        scope = _scope(root)
        base = self._base(ctx, root)
        if src.kind == "cli_list":
            if ctx.runner is None or not ctx.probes_enabled:
                return [], False
            spec = ProbeSpec(src.keys)
            out = ctx.runner.run(spec)
            if out.state != "ok" or out.returncode != 0:
                if out.state == "timeout":
                    notes.append(f"{' '.join(src.keys)}: timed out, using folder listing")
                return [], False
            items = []
            for line in out.output.splitlines()[:MAX_ITEMS]:
                line = line.strip()
                if not line:
                    continue
                name, _, ver = line.partition("@")
                items.append(PluginItem(safe_text(name, 100), safe_text(ver, 40), "", scope,
                                        f"{src.keys[0]} {' '.join(src.keys[1:])}"))
            return items, True
        if src.kind == "ext_dir":
            d = base / src.rel
            if not d.is_dir():
                return [], False
            items = []
            try:
                children = sorted(d.iterdir())
            except OSError:
                notes.append(f"{d}: not readable")
                return [], True
            for child in children[: MAX_ITEMS + 1]:
                if not child.is_dir() or child.name.startswith("."):
                    continue
                ver = ""
                name = child.name
                pj = load_structured(child / "package.json", "json")
                if pj.ok and isinstance(pj.data, dict):
                    pub, nm = pj.data.get("publisher"), pj.data.get("name")
                    if isinstance(nm, str):
                        name = f"{pub}.{nm}" if isinstance(pub, str) else nm
                    if isinstance(pj.data.get("version"), str):
                        ver = pj.data["version"]
                items.append(PluginItem(safe_text(name, 100), safe_text(ver, 40), "", scope, str(child)))
            return items, True
        if src.kind == "manifest_glob":
            d = base / src.rel
            if not d.is_dir():
                return [], False
            items = []
            for mf in sorted(d.glob(src.pattern))[: MAX_ITEMS + 1]:
                pr = load_structured(mf, "json")
                if not pr.ok or not isinstance(pr.data, dict):
                    notes.append(f"{mf}: {ERROR_NOTE.get(pr.error, 'unexpected format')}")
                    continue
                nm = pr.data.get("name")
                ver = pr.data.get("version")
                items.append(PluginItem(safe_text(nm if isinstance(nm, str) else mf.parent.name, 100),
                                        safe_text(ver if isinstance(ver, str) else "", 40),
                                        _enabled(pr.data), scope, str(mf)))
            return items, True
        if src.kind == "json_list":
            f = base / src.rel
            if not f.exists():
                return [], False
            pr = load_structured(f)
            if not pr.ok:
                notes.append(f"{f}: {ERROR_NOTE[pr.error]}")
                return [], True
            val = _dig(pr.data, src.keys)
            items = []
            if isinstance(val, list):
                for v in val[:MAX_ITEMS]:
                    if isinstance(v, str):
                        items.append(PluginItem(safe_text(v, 100), "", "", scope, str(f)))
            return items, True
        return [], False

    # ---- MCPs ----------------------------------------------------------
    def mcps(self, ctx: ScanContext) -> Section[McpItem]:
        if "mcps" in self.spec.unknown:
            return self._unknown("mcps")
        if self.spec.mcps is None:
            return self._unsupported("mcps")
        items: list[McpItem] = []
        notes: list[str] = []
        found_file = False
        worst: SectionStatus | None = None
        for src in self.spec.mcps:
            for root in self._roots(ctx, src.project):
                f = self._base(ctx, root) / src.rel
                if not f.exists() and not f.is_symlink():
                    continue
                found_file = True
                pr = load_structured(f, src.fmt)
                if not pr.ok:
                    worst = ERROR_STATUS[pr.error]
                    notes.append(f"{f}: {ERROR_NOTE[pr.error]}" + (f" (line {pr.line})" if pr.line else ""))
                    continue
                servers = _dig(pr.data, src.keys)
                if not isinstance(servers, dict):
                    continue
                for name, cfg in list(servers.items())[:MAX_ITEMS]:
                    if not isinstance(cfg, dict):
                        cfg = {}
                    items.append(McpItem(
                        name=safe_key(name), transport=_transport(cfg), enabled=_enabled(cfg),
                        scope=_scope(root), source=str(f),
                        env_keys=_key_names(cfg.get("env") or cfg.get("environment")),
                        header_keys=_key_names(cfg.get("headers") or cfg.get("http_headers"))))
        if len(items) > MAX_ITEMS:
            items = items[:MAX_ITEMS]
            notes.append(f"Truncated at {MAX_ITEMS} items")
        if "mcps_extra" in self.spec.notes:
            notes.append(self.spec.notes["mcps_extra"])
        if items:
            return Section(SectionStatus.OK, items, notes)
        if worst is not None:
            return Section(worst, [], notes)
        if not found_file:
            return Section(SectionStatus.MISSING, [], ["No MCP config file found"])
        return Section(SectionStatus.EMPTY, [], notes)

    def _unsupported(self, section: str) -> Section:
        note = self.spec.notes.get(section, "No documented, readable source for this data in v1.")
        return Section(SectionStatus.UNSUPPORTED, [], [note])

    def _unknown(self, section: str) -> Section:
        note = self.spec.notes.get(section, "Not yet mapped to a documented source in v1.")
        return Section(SectionStatus.UNKNOWN, [], [note])


__all__ = ["SpecAdapter", "ToolSpec", "Loc", "McpSource", "PluginSource", "key_is_sensitive"]
