"""Portable host installer for the FWFG MemPalace fork.

Pure, testable config-edit helpers + orchestration. Runs under the fork venv
(has pyyaml + mempalace). The stdlib bootstrap scripts/install_host.py creates
the venv and delegates here via `python -m mempalace.host_install`.

Every edit helper: backs up first, is idempotent (returns False when already
correct), honors dry_run (compute + report, write nothing).
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


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
