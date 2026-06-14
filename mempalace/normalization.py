"""Historical normalization: backfill provenance + seed the wing registry.

Pure classifiers (classify_agent, account_for_wing) + palace operations
(seed_registry_from_palace, backfill_provenance). Additive and crash-safe:
documents are never modified; writes back up first and merge metadata.
"""
from __future__ import annotations

import re

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
