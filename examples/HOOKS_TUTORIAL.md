# How to Use MemPalace Hooks (Auto-Save)

MemPalace hooks act as an "Auto-Save" feature. They help your AI keep a permanent memory without you needing to run manual commands.

### 1. What are these hooks?
* **Save Hook** (`--hook stop`): Saves new facts and decisions every 15 human messages.
* **PreCompact Hook** (`--hook precompact`): Saves your context right before the AI's memory window fills up.
* **Session-End Hook** (`--hook session-end`): Cleans up the session's save-point marker on exit. Never blocks.

### 2. Setup for Claude Code
The hooks run the installed `mempalace` package directly — use the interpreter of the environment where it is installed (on Windows, prefer `pythonw.exe` so no console window flashes). Add this to your configuration file (`~/.claude/settings.json` for all projects):

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [{"type": "command", "command": "\"/path/to/venv/bin/python\" -m mempalace hook run --hook stop --harness claude-code"}]
      }
    ],
    "PreCompact": [
      {
        "hooks": [{"type": "command", "command": "\"/path/to/venv/bin/python\" -m mempalace hook run --hook precompact --harness claude-code"}]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [{"type": "command", "command": "\"/path/to/venv/bin/python\" -m mempalace hook run --hook session-end --harness claude-code"}]
      }
    ]
  }
}
```

Restart Claude Code afterwards — hooks load at session start. Or let `python scripts/install_host.py` set everything up for you.

See [hooks/README.md](../hooks/README.md) for configuration details (`SAVE_INTERVAL`, `MEMPAL_DIR`, `MEMPAL_HOOK_DEBUG`).
