"""OpenAI Agents SDK adapter for MemPalace.

Pure helpers (no SDK import) so they're testable without the OpenAI API:
  mcp_server_params()   - build the MCPServerStdio params (provenance env)
  BOOTSTRAP_INSTRUCTIONS / with_memory_instructions()
  SaveCadence           - deterministic turn-count auto-save trigger
  saved_in_result()     - verify a run actually wrote to the palace

SDK-coupled helpers import `agents` lazily (optional dependency):
  build_mcp_server(), MemPalaceRunHooks
"""
from __future__ import annotations

import os
import platform
import socket
import sys

HARNESS = "openai-agents-sdk"


def _hostname() -> str:
    return (os.environ.get("MEMPALACE_MACHINE") or platform.node()
            or socket.gethostname() or "unknown").lower()


def mcp_server_params(*, account: str | None, model: str | None = None,
                      palace_path: str | None = None, registry_path: str | None = None,
                      session: str | None = None) -> dict:
    """Build the params dict for agents.mcp.MCPServerStdio.

    The MCP stdio transport REPLACES the subprocess environment with `env`, so we
    merge os.environ first (preserving PATH etc.) and then layer provenance on top.
    harness is fixed to this adapter; account/model/session/paths are optional.
    """
    env = dict(os.environ)
    env["MEMPALACE_HARNESS"] = HARNESS
    env["MEMPALACE_MACHINE"] = _hostname()
    if account:
        env["MEMPALACE_ACCOUNT"] = account
    if model:
        env["MEMPALACE_MODEL"] = model
    if session:
        env["MEMPALACE_SESSION"] = session
    if palace_path:
        env["MEMPALACE_PALACE_PATH"] = palace_path
    if registry_path:
        env["MEMPALACE_REGISTRY_PATH"] = registry_path
    return {"command": sys.executable, "args": ["-m", "mempalace.mcp_server"], "env": env}


BOOTSTRAP_INSTRUCTIONS = (
    "You have persistent memory via the MemPalace MCP tools. "
    "On startup, call mempalace_bootstrap once and follow its protocol and filing "
    "rules exactly. Before answering about any past work, person, or decision, "
    "search the palace (mempalace_search / mempalace_kg_query) — never guess. "
    "File new memories into an existing wing from the bootstrap list; do not invent "
    "near-duplicate wings. Provenance is set by the environment — never fabricate it."
)


def with_memory_instructions(base: str | None) -> str:
    """Prepend the MemPalace bootstrap stub to an agent's instructions."""
    if not base:
        return BOOTSTRAP_INSTRUCTIONS
    return f"{BOOTSTRAP_INSTRUCTIONS}\n\n{base}"


class SaveCadence:
    """Counts agent turns; signals a save every `interval` turns.

    Deterministic and SDK-free so the auto-save policy is unit-testable.
    """

    def __init__(self, interval: int = 15):
        if interval < 1:
            raise ValueError("interval must be >= 1")
        self.interval = interval
        self.count = 0

    def tick(self) -> bool:
        """Record one completed turn; return True when a save is due."""
        self.count += 1
        return self.count % self.interval == 0

    def pending(self) -> bool:
        """True if a save is currently due (interval boundary reached)."""
        return self.count % self.interval == 0

    def reset(self) -> None:
        self.count = 0


WRITE_TOOLS = ("mempalace_diary_write", "mempalace_add_drawer")


def saved_in_result(run_result) -> bool:
    """True if the run made at least one MemPalace write-tool call.

    Duck-typed against the Agents SDK RunResult (`.new_items`, each item a
    tool_call_item whose `.raw_item.name` is the tool name) so it is testable
    without the SDK.
    """
    items = getattr(run_result, "new_items", None) or []
    for item in items:
        if getattr(item, "type", None) != "tool_call_item":
            continue
        name = getattr(getattr(item, "raw_item", None), "name", None)
        if name in WRITE_TOOLS:
            return True
    return False


SAVE_PROMPT = (
    "MemPalace checkpoint: save this session's key content now. Call "
    "mempalace_diary_write with an AAAK-compressed summary, and mempalace_add_drawer "
    "for any verbatim decisions/quotes/code. File into an existing wing. Then continue."
)


class FlushError(RuntimeError):
    """Raised when a save flush ran but no MemPalace write tool was called."""


def flush_due(run, *, max_attempts: int = 2) -> None:
    """Drive a verified save. `run` is a callable taking a prompt string and
    returning a run result (duck-typed for saved_in_result). Retries up to
    max_attempts; raises FlushError if no write tool was called (fails visibly)."""
    for _ in range(max_attempts):
        result = run(SAVE_PROMPT)
        if saved_in_result(result):
            return
    raise FlushError("save flush did not produce a MemPalace write tool call")
