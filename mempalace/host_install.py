"""Portable host installer for the FWFG MemPalace fork.

Pure, testable config-edit helpers + orchestration. Runs under the fork venv
(has pyyaml + mempalace). The stdlib bootstrap scripts/install_host.py creates
the venv and delegates here via `python -m mempalace.host_install`.

Every edit helper: backs up first, is idempotent (returns False when already
correct), honors dry_run (compute + report, write nothing).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
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


def parse_py_launcher(text: str) -> list[str]:
    """Extract interpreter paths from `py -0p` output."""
    paths = []
    for line in text.splitlines():
        idx = line.find(":\\")
        if idx >= 1:
            paths.append(line[idx - 1:].strip())
    return paths


def _default_runner(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return ""


def uninstall_stale(interpreters: list[str], venv_python: str, yes: bool, dry_run: bool,
                    _runner=None) -> list[str]:
    """For each interpreter (exact path) that is NOT the venv and HAS mempalace,
    uninstall via that exact interpreter (`<py> -m pip uninstall -y mempalace`).
    Never uses bare python/pip. Returns interpreters uninstalled (or would be)."""
    if _runner is None:
        _runner = _default_runner
    removed = []
    venv_n = os.path.normcase(os.path.normpath(venv_python))
    for py in interpreters:
        if os.path.normcase(os.path.normpath(py)) == venv_n:
            continue
        if "Name: mempalace" not in _runner([py, "-m", "pip", "show", "mempalace"]):
            continue
        removed.append(py)
        if not dry_run and yes:
            _runner([py, "-m", "pip", "uninstall", "-y", "mempalace"])
    return removed


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


GLOBAL_DIRS = [Path.home() / ".mempalace", Path.home() / ".codex", Path.home() / ".claude"]
HOME_CLAUDE_JSON = Path.home() / ".claude.json"
CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
CODEX_HOOKS = Path.home() / ".codex" / "hooks.json"
DEFAULT_TREES = [
    {"path": r"C:\dev", "account": "alan@fwfg.com"},
    {"path": r"C:\pdev", "account": "ja.powell@gmail.com"},
]


def agents_targets_for_tree(tree_root: Path, known_trees: list[Path]) -> list[Path]:
    """AGENTS.md paths the installer may write for THIS run = only the current
    tree's. Other trees are out of bounds (printed as a follow-up by run_install)."""
    return [Path(tree_root) / "AGENTS.md"]


def parse_args(argv):
    p = argparse.ArgumentParser(prog="mempalace.host_install")
    p.add_argument("--tree-root", default=os.getcwd())
    p.add_argument("--venv-python", default="")
    p.add_argument("--tree", action="append", default=[], help="PATH=ACCOUNT (repeatable)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--strip-account", action="store_true")
    p.add_argument("--strip-all-account-overrides", action="store_true")
    return p.parse_args(argv)


def _tree_entries(extra: list[str]) -> list[dict]:
    entries = list(DEFAULT_TREES)
    for spec in extra:
        if "=" in spec:
            path, acct = spec.split("=", 1)
            entries.append({"path": path.strip(), "account": acct.strip()})
    return entries


def run_install(args) -> int:
    if not args.venv_python or not Path(args.venv_python).is_file():
        print(f"ERROR: --venv-python must be an existing interpreter; got {args.venv_python!r}")
        return 1
    tree_root = Path(args.tree_root)
    trees_path = Path.home() / ".mempalace" / "trees.yaml"
    print(f"== MemPalace host install (tree-root={tree_root}, dry_run={args.dry_run}) ==")
    write_trees_yaml(trees_path, _tree_entries(args.tree), args.dry_run)         # global
    repoint_json_mcp(tree_root / ".mcp.json", "mempalace", args.venv_python, "claude-code", args.dry_run)
    repoint_json_mcp(HOME_CLAUDE_JSON, "mempalace", args.venv_python, "claude-code", args.dry_run)
    repoint_hook_commands(CLAUDE_SETTINGS, args.venv_python, "claude-code", args.dry_run)
    repoint_codex_toml(CODEX_CONFIG, args.venv_python, "codex", args.dry_run)
    repoint_hook_commands(CODEX_HOOKS, args.venv_python, "codex", args.dry_run)
    for agents in agents_targets_for_tree(tree_root, [Path(e["path"]) for e in DEFAULT_TREES]):
        if within_tree(agents, tree_root, GLOBAL_DIRS):
            ensure_agents_section(agents, args.dry_run)
    # boundary follow-up: other known trees are NOT written here
    for e in DEFAULT_TREES:
        other = Path(e["path"])
        if not within_tree(other, tree_root, GLOBAL_DIRS) and other.exists():
            print(f"  NOTE: run `python -m mempalace.host_install` from {other} to configure its AGENTS.md")
    stale = uninstall_stale(_discover_interpreters(args.venv_python), args.venv_python, args.yes, args.dry_run)
    if stale:
        print(f"  stale mempalace interpreters: {stale}")
    print("  VERIFY-THEN-STRIP: open a session in this tree, run `mempalace doctor`,")
    print("  confirm tree_account is correct, THEN run with --strip-account.")
    return 0


def run_strip(args) -> int:
    scope = "all" if args.strip_all_account_overrides else "host"
    host = [HOME_CLAUDE_JSON, CLAUDE_SETTINGS, CODEX_CONFIG, CODEX_HOOKS]
    project = [Path(args.tree_root) / ".mcp.json"]
    print(f"== strip account (scope={scope}, dry_run={args.dry_run}) ==")
    removed = strip_account(host, project, scope, args.dry_run)
    print(f"  {'would remove' if args.dry_run else 'removed'} MEMPALACE_ACCOUNT from: {removed or 'nothing'}")
    return 0


def _discover_interpreters(venv_python: str) -> list[str]:
    found = []
    found += _default_runner(["where", "python"]).splitlines()
    found += parse_py_launcher(_default_runner(["py", "-0p"]))
    seen, out = set(), []
    for p in (x.strip() for x in found if x.strip()):
        k = os.path.normcase(os.path.normpath(p))
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def main(argv=None):
    args = parse_args(argv if argv is not None else __import__("sys").argv[1:])
    if args.strip_account or args.strip_all_account_overrides:
        return run_strip(args)
    return run_install(args)


if __name__ == "__main__":
    raise SystemExit(main())
