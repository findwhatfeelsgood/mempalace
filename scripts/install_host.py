#!/usr/bin/env python3
"""Bootstrap the FWFG MemPalace fork on a host, then delegate to the venv module.

Stdlib only (runs before the package/venv exist). Steps: ensure repo (you ran
this from a clone), create the venv, editable-install, then hand off to
`<venv>/python -m mempalace.host_install` for all config work. Forwards flags.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent          # the fork clone
VENV = REPO / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def main():
    base = sys.executable
    run(["git", "-C", str(REPO), "pull", "--ff-only"])
    if not VENV_PY.exists():
        run([base, "-m", "venv", str(VENV)])
    run([str(VENV_PY), "-m", "pip", "install", "-e", str(REPO)])
    if "--with-openai" in sys.argv:
        run([str(VENV_PY), "-m", "pip", "install", "openai-agents"])
    forwarded = [a for a in sys.argv[1:] if a != "--with-openai"]
    run([str(VENV_PY), "-m", "mempalace.host_install", "--venv-python", str(VENV_PY), *forwarded])


if __name__ == "__main__":
    main()
