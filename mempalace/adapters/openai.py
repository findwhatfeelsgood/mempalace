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
