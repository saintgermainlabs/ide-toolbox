"""Plain data models. Everything here is already sanitized when built."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

MCP_STATE = "Configured (not checked)"
MAX_ITEMS = 500


class PathState(str, Enum):
    EXISTS = "Exists"
    MISSING = "Missing"
    UNREADABLE = "Unreadable"
    BROKEN_SYMLINK = "BrokenSymlink"


class SectionStatus(str, Enum):
    OK = "OK"
    EMPTY = "Empty"
    MISSING = "Missing"
    UNREADABLE = "Unreadable"
    PARSE_ERROR = "ParseError"
    UNSUPPORTED = "Unsupported"
    UNKNOWN = "Unknown"
    TIMED_OUT = "TimedOut"


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low (config only)"
    NONE = "None"


class SignalKind(str, Enum):
    CLI = "CLI"
    DESKTOP = "Desktop"
    PACKAGE = "Package"
    CONFIG = "Config"


class ProbeState(str, Enum):
    FOUND = "Found"
    FOUND_NO_VERSION = "Found – no version output"
    NOT_ON_PATH = "Not on PATH"
    TIMED_OUT = "Probe timed out"
    ERROR = "Probe error"
    REJECTED = "Rejected (not allowlisted)"


@dataclass(frozen=True)
class Signal:
    kind: SignalKind
    detail: str
    path: str = ""


@dataclass
class Detection:
    signals: list[Signal] = field(default_factory=list)
    confidence: Confidence = Confidence.NONE

    @property
    def label(self) -> str:
        return {
            Confidence.HIGH: "Detected",
            Confidence.MEDIUM: "Detected (limited signal)",
            Confidence.LOW: "Config found, application not detected",
            Confidence.NONE: "Missing",
        }[self.confidence]


@dataclass(frozen=True)
class PathEntry:
    label: str
    path: str
    kind: str  # "file" | "dir"
    scope: str  # "User" | "Project: <root>"
    state: PathState
    link_target: str = ""


@dataclass(frozen=True)
class SkillItem:
    name: str
    description: str
    scope: str
    source: str


@dataclass(frozen=True)
class PluginItem:
    name: str
    version: str
    enabled: str  # "Yes" | "No" | "" (not declared)
    scope: str
    source: str


@dataclass(frozen=True)
class McpItem:
    name: str
    transport: str
    enabled: str
    scope: str
    source: str
    env_keys: tuple[str, ...] = ()
    header_keys: tuple[str, ...] = ()
    state: str = MCP_STATE


T = TypeVar("T")


@dataclass
class Section(Generic[T]):
    status: SectionStatus
    items: list[T] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ConfigSummary:
    """Adapter-approved, non-secret summary of a config file."""
    path: str
    status: SectionStatus
    rows: tuple[tuple[str, str], ...] = ()  # (key path, type/count) only
    note: str = ""


@dataclass
class ProbeResult:
    name: str
    state: ProbeState
    version: str = ""
    path: str = ""
    resolved: str = ""
    source: str = "Unknown"
    duplicates: tuple[str, ...] = ()


@dataclass
class ToolReport:
    tool_id: str
    name: str
    detection: Detection
    version: str
    probes: list[ProbeResult]
    config: list[PathEntry]
    summaries: list[ConfigSummary]
    skills: Section[SkillItem]
    plugins: Section[PluginItem]
    mcps: Section[McpItem]
    scanned_at: str = ""
    errors: int = 0
