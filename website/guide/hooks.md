# Auto-Save Hooks

Two hooks for Claude Code and Codex that automatically save memories during work. No manual "save" commands needed.

## What They Do

| Hook | When It Fires | What Happens |
|------|--------------|-------------|
| **Save Hook** | Every 15 human messages | Blocks the AI, tells it to save key topics/decisions/quotes to the palace |
| **PreCompact Hook** | Right before context compaction | Emergency save — forces the AI to save everything before losing context |
| **Session-End Hook** | When the session ends | Housekeeping — deletes the session's save-point marker so `hook_state/` never accumulates stale files. Never blocks. |

The AI does the actual filing — it knows the conversation context, so it classifies memories into the right wings/halls/closets. The hooks just tell it **when** to save.

## Install — Claude Code

The hooks are plain CLI invocations of the installed Python package — no
shell scripts, nothing to `chmod`. Use the interpreter of the environment
where mempalace is installed (a venv is typical). On Windows, prefer the
venv's `pythonw.exe` — it is windowless, so the hook doesn't flash a console
window every time it fires.

Add to `~/.claude/settings.json` (all projects) or
`.claude/settings.local.json` (one project):

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "\"/path/to/venv/bin/python\" -m mempalace hook run --hook stop --harness claude-code"
      }]
    }],
    "PreCompact": [{
      "hooks": [{
        "type": "command",
        "command": "\"/path/to/venv/bin/python\" -m mempalace hook run --hook precompact --harness claude-code"
      }]
    }],
    "SessionEnd": [{
      "hooks": [{
        "type": "command",
        "command": "\"/path/to/venv/bin/python\" -m mempalace hook run --hook session-end --harness claude-code"
      }]
    }]
  }
}
```

Quote the interpreter path so paths with spaces survive shell tokenization.
Restart Claude Code afterwards — hooks load at session start.

**Automated install:** `python scripts/install_host.py` bootstraps the venv
and rewrites any existing `mempalace hook run` commands in your settings to
that venv's windowless interpreter — idempotent, with backups.

## Install — Codex CLI

Add to `.codex/hooks.json`, same CLI form with the `codex` harness:

```json
{
  "Stop": [{
    "type": "command",
    "command": "python3 -m mempalace hook run --hook stop --harness codex"
  }],
  "PreCompact": [{
    "type": "command",
    "command": "python3 -m mempalace hook run --hook precompact --harness codex"
  }]
}
```

## Configuration

Constants in `mempalace/hooks_cli.py`:

- **`SAVE_INTERVAL = 15`** — How many human messages between saves. Lower = more frequent, higher = less interruption. (Tool results in the transcript are not counted — only real human messages.)
- **`STATE_DIR`** — Where hook state is stored (`~/.mempalace/hook_state/`).

Environment variables:

- **`MEMPAL_DIR`** — Optional. Set to a conversations directory to auto-run `mempalace mine` on each save trigger.
- **`MEMPAL_HOOK_DEBUG`** — Optional. Set to enable diagnostic logging to `~/.mempalace/hook_state/hook.log`; unset, the hooks write no log.

## Session-End Hook

Claude Code only: the `SessionEnd` entry above is housekeeping — each session
deletes its own `{session_id}_last_save` marker on exit. It never blocks and
produces no output. Without it, markers (2-byte files) accumulate harmlessly
in `~/.mempalace/hook_state/`.

## How It Works

### Save Hook (Stop event)

```
User sends message → AI responds → Stop hook fires
                                          ↓
                                  Count human messages in transcript
                                          ↓
                            ┌── < 15 since last save → let AI stop
                            │
                            └── ≥ 15 since last save → block + save
                                                            ↓
                                                    AI saves to palace
                                                            ↓
                                                    AI stops (flag set)
```

The `stop_hook_active` flag prevents infinite loops.

### PreCompact Hook

```
Context window full → PreCompact fires → ALWAYS blocks → AI saves → Compaction proceeds
```

No counting needed — compaction always warrants a save.

## Debugging

Logging is off by default — set `MEMPAL_HOOK_DEBUG=1` in the environment
Claude Code runs under, then:

```bash
cat ~/.mempalace/hook_state/hook.log
```

Example output:
```
[14:30:15] Session abc123: 12 exchanges, 12 since last save
[14:35:22] Session abc123: 15 exchanges, 15 since last save
[14:35:22] TRIGGERING SAVE at exchange 15
[14:40:01] Session abc123: 18 exchanges, 3 since last save
```

## Cost

**Zero extra tokens.** The hooks are bash scripts that run locally. They don't call any API. The only "cost" is a few seconds of the AI organizing memories at each checkpoint.
