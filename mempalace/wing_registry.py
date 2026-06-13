"""Wing registry + canonicalization. Pure logic; no MCP/Chroma imports."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml
from rapidfuzz import fuzz, process

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


FUZZY_THRESHOLD = 90      # token_set_ratio score required to accept
FUZZY_MARGIN = 8          # winner must beat runner-up by this much


@dataclass
class CanonResult:
    slug: str
    status: str           # canonical | provisional | unverified
    matched: bool = False


def canonicalize_agent(name: str) -> str:
    """Return a bare writer slug. Strips any number of leading 'wing-'/'wing_'
    segments (including a trailing bare 'wing') so the storage layer can add the
    'wing_' prefix exactly once."""
    slug = normalize(name)
    while slug == "wing" or slug.startswith("wing-"):
        slug = "" if slug == "wing" else slug[len("wing-"):]
    return slug or "unknown"


def canonicalize_wing(name: str, account: str | None, kind: str, registry: Registry) -> CanonResult:
    """Resolve `name` to a canonical wing slug, scoped to account+kind.

    - empty registry              -> unverified (fail open, store as requested)
    - exact slug/alias match      -> canonical
    - high-confidence fuzzy match -> canonical (no alias learning here)
    - otherwise (incl. account mismatch) -> provisional
    """
    norm = normalize(name)
    if not registry.entries:
        return CanonResult(slug=norm, status="unverified")

    scoped = [e for e in registry.entries
              if e.kind == kind and (e.account or None) == (account or None)]

    # exact slug/alias
    for e in scoped:
        if norm == e.slug or norm in {normalize(a) for a in e.aliases}:
            return CanonResult(slug=e.slug, status="canonical", matched=True)

    # high-confidence fuzzy, with runner-up margin
    if scoped:
        choices = {e.slug: e.slug for e in scoped}
        ranked = process.extract(norm, choices, scorer=fuzz.token_set_ratio, limit=2)
        if ranked:
            best_slug, best_score = ranked[0][0], ranked[0][1]
            runner = ranked[1][1] if len(ranked) > 1 else 0
            if best_score >= FUZZY_THRESHOLD and (best_score - runner) >= FUZZY_MARGIN:
                return CanonResult(slug=best_slug, status="canonical", matched=True)

    return CanonResult(slug=norm, status="provisional")
