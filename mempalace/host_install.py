"""Portable host installer for the FWFG MemPalace fork.

Pure, testable config-edit helpers + orchestration. Runs under the fork venv
(has pyyaml + mempalace). The stdlib bootstrap scripts/install_host.py creates
the venv and delegates here via `python -m mempalace.host_install`.

Every edit helper: backs up first, is idempotent (returns False when already
correct), honors dry_run (compute + report, write nothing).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import yaml


def backup_file(path: Path) -> Path | None:
    """Copy `path` to `<path>.bak.<ts>` before it is edited. None if absent."""
    path = Path(path)
    if not path.is_file():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_name(f"{path.name}.bak.{ts}")
    shutil.copy2(path, bak)
    return bak


def within_tree(target: Path, tree_root: Path, allowed_globals: list[Path]) -> bool:
    """True iff `target` is under `tree_root` or under one of `allowed_globals`.
    The identity-boundary guard: a C:\\dev run must never write a C:\\pdev path."""
    target = Path(target).resolve()
    roots = [Path(tree_root).resolve(), *[Path(g).resolve() for g in allowed_globals]]
    for r in roots:
        try:
            target.relative_to(r)
            return True
        except ValueError:
            continue
    return False


def _load_yaml_list(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    return [e for e in data if isinstance(e, dict)]


def write_trees_yaml(path: Path, entries: list[dict], dry_run: bool) -> bool:
    """Merge `entries` (keyed by path; account overrides) into the tree-map and
    write it with yaml.safe_dump. Idempotent; backs up before overwrite; returns
    True iff content changed (or would change, when dry_run)."""
    path = Path(path)
    merged: dict[str, str] = {e["path"]: e["account"] for e in _load_yaml_list(path)
                             if e.get("path") and e.get("account")}
    before = dict(merged)
    for e in entries:
        if e.get("path") and e.get("account"):
            merged[e["path"]] = e["account"]
    if merged == before and path.is_file():
        return False
    if dry_run:
        return True
    payload = [{"path": p, "account": a} for p, a in merged.items()]
    backup_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")
    return True


def repoint_json_mcp(path: Path, server: str, venv_python: str, harness: str,
                     dry_run: bool) -> bool:
    """Point a JSON mcpServers[server] at the venv python + set HARNESS env.
    PRESERVES any existing MEMPALACE_ACCOUNT and never adds one — account is
    tree-derived; removal is strip_account's job (verify-before-strip). No-op if
    file/server absent or already correct. Backs up before writing. Returns changed."""
    path = Path(path)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    srv = (data.get("mcpServers") or {}).get(server)
    if not isinstance(srv, dict):
        return False
    desired_cmd = venv_python
    desired_args = ["-m", "mempalace.mcp_server"]
    env = dict(srv.get("env") or {})
    changed = (srv.get("command") != desired_cmd or srv.get("args") != desired_args
               or env.get("MEMPALACE_HARNESS") != harness)
    if not changed:
        return False
    if dry_run:
        return True
    backup_file(path)
    srv["command"] = desired_cmd
    srv["args"] = desired_args
    env["MEMPALACE_HARNESS"] = harness
    srv["env"] = env
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


_HOOK_RE = re.compile(
    r"^(?P<py>.+?)\s+-m\s+mempalace\s+hook\s+run\s+--hook\s+(?P<hook>\S+)\s+"
    r"--harness\s+(?P<harness>\S+)\s*$"
)


def repoint_hook_commands(path: Path, venv_python: str, harness: str, dry_run: bool) -> bool:
    """Rewrite any 'mempalace hook run' command in a hooks JSON to use the explicit
    venv python (QUOTED, so paths with spaces like C:\\Program Files\\... work as a
    single shell token) and the given harness. Leaves non-mempalace commands alone.
    Idempotent; backs up; returns changed."""
    path = Path(path)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    changed = False

    def fix(node):
        nonlocal changed
        if isinstance(node, dict):
            cmd = node.get("command")
            if isinstance(cmd, str):
                m = _HOOK_RE.match(cmd.strip())
                if m:
                    new = f'"{venv_python}" -m mempalace hook run --hook {m["hook"]} --harness {harness}'
                    if new != cmd:
                        node["command"] = new
                        changed = True
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(data)
    if not changed:
        return False
    if dry_run:
        return True
    backup_file(path)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def repoint_codex_toml(path: Path, venv_python: str, harness: str, dry_run: bool) -> bool:
    """Targeted edit of the [mcp_servers.mempalace] block in a Codex config.toml:
    set command to the venv python and ensure an env table with MEMPALACE_HARNESS.
    PRESERVES any existing MEMPALACE_ACCOUNT and never adds one (removal is
    strip_account's job — verify-before-strip). Preserves comments/other tables.
    Idempotent; backs up; returns changed. Verifies the result parses (tomllib)
    before writing."""
    import tomllib
    path = Path(path)
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    try:
        cur = tomllib.loads(text)
    except Exception:
        return False
    mp = (cur.get("mcp_servers") or {}).get("mempalace")
    if not isinstance(mp, dict):
        return False
    cmd_ok = mp.get("command") == venv_python
    env_ok = (mp.get("env") or {}).get("MEMPALACE_HARNESS") == harness
    if cmd_ok and env_ok:
        return False
    lines = text.splitlines()
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        if line.strip() == "[mcp_servers.mempalace]":
            out.append(line)
            i += 1
            # rewrite keys until the next table header or EOF
            while i < n and not lines[i].lstrip().startswith("["):
                stripped = lines[i].lstrip()
                if stripped.startswith("command"):
                    out.append(f"command = '{venv_python}'")   # single-quoted TOML literal (no escaping)
                else:
                    out.append(lines[i])
                i += 1
            # ensure an env table follows with the harness
            out.append("")
            out.append("[mcp_servers.mempalace.env]")
            out.append(f'MEMPALACE_HARNESS = "{harness}"')
            # skip an existing env table (we just rewrote it) to avoid duplication
            if i < n and lines[i].strip() == "[mcp_servers.mempalace.env]":
                i += 1
                while i < n and not lines[i].lstrip().startswith("["):
                    s = lines[i].lstrip()
                    if s and not s.startswith("MEMPALACE_HARNESS") and not s.startswith("#"):
                        out.append(lines[i])   # preserve other env keys
                    i += 1
            continue
        out.append(line)
        i += 1
    new_text = "\n".join(out) + "\n"
    try:
        tomllib.loads(new_text)              # never write unparseable TOML
    except Exception:
        return False
    if dry_run:
        return True
    backup_file(path)
    path.write_text(new_text, encoding="utf-8")
    return True


def _strip_account_json(path: Path, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    found = False
    for srv in (data.get("mcpServers") or {}).values():
        env = srv.get("env") if isinstance(srv, dict) else None
        if isinstance(env, dict) and "MEMPALACE_ACCOUNT" in env:
            found = True
            if not dry_run:
                del env["MEMPALACE_ACCOUNT"]
    if found and not dry_run:
        backup_file(path)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return found


def _strip_account_toml(path: Path, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    kept = [ln for ln in lines if ln.strip().split("=")[0].strip() != "MEMPALACE_ACCOUNT"]
    if len(kept) == len(lines):
        return False
    if not dry_run:
        backup_file(path)
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return True


def strip_account(host_paths: list[Path], project_paths: list[Path], scope: str,
                  dry_run: bool) -> list[str]:
    """Remove MEMPALACE_ACCOUNT from host-level configs (always) and, when
    scope=='all', from project-scoped configs too. JSON + TOML. Returns the list
    of files changed (or that would change, when dry_run). DEC-G: default keeps
    project/user overrides — the escape hatch for unreliable-CWD harnesses."""
    targets = list(host_paths)
    if scope == "all":
        targets += list(project_paths)
    removed: list[str] = []
    for p in targets:
        p = Path(p)
        hit = _strip_account_toml(p, dry_run) if p.suffix == ".toml" else _strip_account_json(p, dry_run)
        if hit:
            removed.append(str(p))
    return removed


AGENTS_SECTION = """
## MemPalace memory (required)

You have persistent memory via the **MemPalace MCP tools**. Provenance (harness,
account, machine) is set by the environment / tree-map — never fabricate it.

1. **On startup:** call `mempalace_bootstrap` once and follow its protocol + filing
   rules. File into an existing wing from the list it returns; don't spawn
   near-duplicates (use `mempalace_register_wing` for a genuinely new one).
2. **Before answering** about any past person, project, decision, or event: call
   `mempalace_search` or `mempalace_kg_query` first. Never guess — verify.
3. **At session end** (or after a meaningful chunk of work): call
   `mempalace_diary_write` (AAAK summary) + `mempalace_add_drawer` (verbatim
   decisions/quotes/code).
"""


def ensure_agents_section(path: Path, dry_run: bool) -> bool:
    """Append the MemPalace memory protocol to an existing AGENTS.md if absent.
    Idempotent (keyed on the section header); backs up; returns changed. No-op if
    the file does not exist (the installer never creates a tree's AGENTS.md)."""
    path = Path(path)
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if "## MemPalace memory (required)" in text:
        return False
    if dry_run:
        return True
    backup_file(path)
    sep = "" if text.endswith("\n") else "\n"
    path.write_text(text + sep + AGENTS_SECTION, encoding="utf-8")
    return True
