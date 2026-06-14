# FWFG fork — operating notes

This is the FWFG-owned fork of the public `mempalace/mempalace`, carrying the
multi-model provenance / wing-registry / bootstrap / adapter work. Upstream
tracking is kept clean (see `docs`/the design spec); this file is FWFG-only and
is **not** meant to go upstream.

## Which MemPalace Is Which

There are two related repos and (historically) more than one Python install. Keep
them straight:

| Thing | What it is |
|---|---|
| **`mempalace`** (this repo) | The **runtime package fork** — MCP server, provenance stamping, wing registry/canonicalization, `mempalace_bootstrap`, the OpenAI adapter, local migration/backfill. |
| **`mempalace-bq`** | The **BigQuery sync/mirror** companion — DDL, the push/pull sync, forced-resync. It is *not* a MemPalace package; it never becomes the fork. |

### Rules that prevent old/new confusion

- **Never use bare `python -m mempalace`.** With multiple interpreters on a machine
  (3.12, 3.14, uv, Store stub…), bare `python` is ambiguous and may hit a stale
  global install or one with no `mempalace` at all.
- **Every configured host points at the explicit fork interpreter:**
  `C:\dev\mempalace\.venv\Scripts\python.exe`
  This applies to every MCP server entry and every hook command (Claude Code's
  `.mcp.json` / `~/.claude.json` / `~/.claude/settings.json`, and Codex's
  `~/.codex/config.toml` / `~/.codex/hooks.json`).
- **Stale global installs should fail loudly.** Do not leave an old `mempalace`
  installed in a global/user-site interpreter. `pip uninstall` it (by exact
  interpreter) so a stray bare `python -m mempalace` errors instead of silently
  running old code.

### How to tell which one you're running

```
C:\dev\mempalace\.venv\Scripts\python.exe -m mempalace doctor
```

`mempalace doctor` prints the executable path, package import path, package
version, palace path, registry path, env-derived provenance
(`harness`/`account`/`model`/`machine`/`session`), and whether the
`mempalace_bootstrap` tool exists. The fork reports a `+fwfg` version and
`bootstrap_tool_available: true`; a stale global install will not.
