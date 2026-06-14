"""Historical normalization: backfill provenance + seed the wing registry.

Pure classifiers (classify_agent, account_for_wing) + palace operations
(seed_registry_from_palace, backfill_provenance). Additive and crash-safe:
documents are never modified; writes back up first and merge metadata.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import wing_registry as wr


# Legacy `agent` string -> (harness, model). Order matters: most specific first.
# Unknown -> (None, None); we never guess.
_OPUS_47 = re.compile(r"opus[-.]?4[-.]?7|opus47")
_OPUS_48 = re.compile(r"opus[-.]?4[-.]?8|opus48")
_CLAUDE_HARNESS = re.compile(r"^(claude|opus-fwfg|wing[-_]?claude)")


def classify_agent(agent: str | None) -> tuple[str | None, str | None]:
    """Map a legacy `agent` metadata string to (harness, model). Never guesses."""
    if not agent:
        return (None, None)
    a = agent.strip().lower()
    if _OPUS_48.search(a):
        return ("claude-code", "claude-opus-4.8")
    if _OPUS_47.search(a):
        return ("claude-code", "claude-opus-4.7")
    if "fable-5" in a or "fable5" in a:
        return ("claude-code", "claude-fable-5")
    if a == "codex" or a.startswith("codex"):
        return ("codex", None)
    if a == "claude-code" or _CLAUDE_HARNESS.match(a):
        return ("claude-code", None)
    return (None, None)


# Explicit account classification for historical wings. Unknowns are flagged
# for review, never defaulted to work (spec §7).
_PERSONAL_PATTERNS = (re.compile(r"^pdev($|[-_])"),)
_WORK_PATTERNS = (
    re.compile(r"^wing[-_]"),       # agent diaries (claude-*, opus-*) are work on this machine
    re.compile(r"^fwfg([-_]|$)"),
    re.compile(r"^dev$"),
    re.compile(r"^apple([-_]|$)"),
    re.compile(r"^gizmo"),
    re.compile(r"^klaviyo"),
    re.compile(r"^uscreen"),
    re.compile(r"^inbox([-_]|$)"),
    re.compile(r"^support([-_]|$)"),
    re.compile(r"^mempalace([-_]|$)"),
    re.compile(r"^md-file"),
    re.compile(r"^filenamer"),
    re.compile(r"^claude-skills"),
    re.compile(r"^user-preferences$"),
)


def account_for_wing(wing: str) -> tuple[str | None, bool]:
    """Return (account, needs_review). Personal -> ja.powell@gmail.com;
    recognized work -> alan@fwfg.com; unrecognized -> (None, True) for review."""
    w = (wing or "").strip().lower()
    if any(p.search(w) for p in _PERSONAL_PATTERNS):
        return ("ja.powell@gmail.com", False)
    if any(p.search(w) for p in _WORK_PATTERNS):
        return ("alan@fwfg.com", False)
    return (None, True)


def _read_wing_counts(palace_path: str) -> dict[str, int]:
    """Distinct wings -> drawer count, read via the ChromaDB API (read-only)."""
    import chromadb
    client = chromadb.PersistentClient(path=str(Path(palace_path).expanduser()))
    col = client.get_collection("mempalace_drawers")
    counts: dict[str, int] = {}
    total = col.count()
    offset = 0
    while offset < total:
        batch = col.get(include=["metadatas"], limit=1000, offset=offset)
        metas = batch["metadatas"] or []
        if not metas:
            break
        for m in metas:
            w = (m or {}).get("wing", "__unknown__")
            counts[w] = counts.get(w, 0) + 1
        offset += len(metas)
    del col, client
    return counts


def seed_registry_from_palace(palace_path: str, *, registry_path=None, dry_run: bool = True) -> list:
    """Build wing_registry entries from the palace's wings, collapsing dupes by
    normalized slug and assigning accounts (unknowns flagged status='review').
    Returns the entries; writes the YAML unless dry_run."""
    counts = _read_wing_counts(palace_path)
    by_slug: dict[str, wr.WingEntry] = {}
    for raw_wing, n in sorted(counts.items()):
        slug = wr.normalize(raw_wing)
        kind = "diary" if raw_wing.startswith("wing_") and slug.startswith("wing-") else "project"
        account, needs_review = account_for_wing(raw_wing)
        if slug in by_slug:
            entry = by_slug[slug]
            if raw_wing != entry.slug and wr.normalize(raw_wing) != entry.slug:
                pass
            if raw_wing not in entry.aliases and raw_wing != slug:
                entry.aliases.append(raw_wing)
            continue
        entry = wr.WingEntry(
            slug=slug, display=raw_wing, kind=kind, account=account,
            aliases=[raw_wing] if raw_wing != slug else [],
            status="review" if needs_review else "active",
            description=f"{n} drawers (seeded)",
        )
        by_slug[slug] = entry
    entries = list(by_slug.values())
    if not dry_run:
        wr.save_registry(wr.Registry(entries=entries), registry_path)
    return entries
