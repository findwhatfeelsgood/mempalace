# MemPalace Hooks — Auto-Save for Terminal AI Tools

These hook scripts make MemPalace save automatically. No manual "save" commands needed.

## What They Do

| Hook | When It Fires | What Happens |
|------|--------------|-------------|
| **Save Hook** | Every 15 human messages | Blocks the AI, tells it to save key topics/decisions/quotes to the palace |
| **PreCompact Hook** | Right before context compaction | Emergency save — forces the AI to save EVERYTHING before losing context |
| **Session-End Hook** | When the session ends | Housekeeping — deletes the session's save-point marker from `hook_state/` so stale per-session files never accumulate. Never blocks. |

The AI does the actual filing — it knows the conversation context, so it classifies memories into the right wings/halls/closets. The hooks just tell it WHEN to save.

## Install — Claude Code

The hooks are plain CLI invocations of the installed Python package — there
are no shell scripts to copy or `chmod`. Use the interpreter of the
environment where mempalace is installed (a venv is typical). On Windows,
prefer the venv's `pythonw.exe` — it is windowless, so the hook doesn't flash
a console and steal keyboard focus every time it fires.

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

Quote the interpreter path (as above) so paths containing spaces survive
shell tokenization. Restart Claude Code afterwards — hooks load at session
start.

**Automated install:** `python scripts/install_host.py` bootstraps the venv
and rewrites any existing `mempalace hook run` commands in your settings to
that venv's windowless interpreter — idempotent, with backups.

## Install — Codex CLI (OpenAI)

Add to `.codex/hooks.json`, using the same CLI form with the `codex` harness:

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

(The `.codex-plugin/hooks/` wrapper scripts do exactly this and can be used
instead if your Codex setup passes hook input via a file.)

## Configuration

Constants in `mempalace/hooks_cli.py`:

- **`SAVE_INTERVAL = 15`** — How many human messages between saves. Lower = more frequent saves, higher = less interruption. (Tool results in the transcript are not counted — only real human messages.)
- **`STATE_DIR`** — Where hook state is stored (`~/.mempalace/hook_state/`).

Environment variables:

- **`MEMPAL_DIR`** — Optional. Set to a conversations directory to auto-run `mempalace mine <dir>` on each save trigger. Leave unset (default) to let the AI handle saving via the block reason message.
- **`MEMPAL_HOOK_DEBUG`** — Optional. Set (e.g. `=1`) to enable diagnostic logging to `~/.mempalace/hook_state/hook.log`. Unset (default), the hooks write no log at all.

### Session-End Hook (Claude Code)

The `SessionEnd` entry above is housekeeping: each session removes its own
`{session_id}_last_save` marker on exit. Without it, markers are 2-byte files
that accumulate harmlessly in `~/.mempalace/hook_state/` — cleanup is
cosmetic, not required.

### mempalace CLI

The relevant commands are:

```bash
mempalace mine <dir>               # Mine all files in a directory
mempalace mine <dir> --mode convos # Mine conversation transcripts only
```

The hook commands run the installed `mempalace` package via `-m`, so they work
from any working directory — no repo paths involved.

## How It Works (Technical)

### Save Hook (Stop event)

```
User sends message → AI responds → Claude Code fires Stop hook
                                            ↓
                                    Hook counts human messages in JSONL transcript
                                            ↓
                              ┌─── < 15 since last save ──→ echo "{}" (let AI stop)
                              │
                              └─── ≥ 15 since last save ──→ {"decision": "block", "reason": "save..."}
                                                                    ↓
                                                            AI saves to palace
                                                                    ↓
                                                            AI tries to stop again
                                                                    ↓
                                                            stop_hook_active = true
                                                                    ↓
                                                            Hook sees flag → echo "{}" (let it through)
```

The `stop_hook_active` flag prevents infinite loops: block once → AI saves → tries to stop → flag is true → we let it through.

### PreCompact Hook

```
Context window getting full → Claude Code fires PreCompact
                                        ↓
                                Hook ALWAYS blocks
                                        ↓
                                AI saves everything
                                        ↓
                                Compaction proceeds
```

No counting needed — compaction always warrants a save.

## Debugging

Logging is off by default. Enable it by setting `MEMPAL_HOOK_DEBUG=1` in the
environment Claude Code runs under, then check the hook log:
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

## Known Limitations

**Hooks require session restart after install.** Claude Code loads hooks from `settings.json` at session start only. If you run `mempalace init` or manually edit hook config mid-session, the hooks won't fire until you restart Claude Code. This is a Claude Code limitation.

## Cost

**Zero extra tokens.** The hooks notify the AI that saves happened in the background — the AI doesn't need to write anything in the chat. All filing is handled automatically. Previous versions asked the AI to write diary entries and drawer content in the chat window, which cost ~$1/session in retransmitted tokens.
