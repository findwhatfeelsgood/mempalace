"""Wing registry + canonicalization. Pure logic; no MCP/Chroma imports."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

DEFAULT_REGISTRY_PATH = Path(os.path.expanduser("~/.mempalace/wing_registry.yaml"))
_SEP_RE = re.compile(r"[\s_]+")
_DEDUP_DASH_RE = re.compile(r"-{2,}")


def normalize(name: str) -> str:
    """Lowercase, trim, unify separators to single '-'."""
    s = (name or "").strip().lower()
    s = _SEP_RE.sub("-", s)
    s = _DEDUP_DASH_RE.sub("-", s)
    return s.strip("-")


@dataclass
class WingEntry:
    slug: str
    display: str = ""
    kind: str = "project"          # project | diary
    account: str | None = None
    aliases: list[str] = field(default_factory=list)
    status: str = "active"         # active | archived
    description: str = ""


@dataclass
class Registry:
    entries: list[WingEntry] = field(default_factory=list)


def load_registry(path: Path | None = None) -> Registry:
    """Read the registry YAML. Fail open: missing/corrupt -> empty Registry."""
    path = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not path.is_file():
        return Registry()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        return Registry(entries=[WingEntry(**e) for e in raw])
    except Exception:
        return Registry()


def save_registry(reg: Registry, path: Path | None = None) -> None:
    path = Path(path) if path else DEFAULT_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump([asdict(e) for e in reg.entries], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
