# Auto-trigger at 15 KB via a SessionStart hook

A skill only fires when the model judges it relevant — it can't watch a file size on its
own. To make compaction fire automatically once MEMORY.md crosses 15 KB, install a
`SessionStart` hook. The hook runs a tiny check at the start of every session and, when the
index is over budget, prints a line of `additionalContext` that nudges the model to invoke
the `memory-compaction` skill. (A hook can inject context; it can't run the skill itself —
the model still does the work, which is what we want, since compaction needs judgment.)

## The checker script

Bundled at `<skill-dir>/scripts/session_start_check.py`. It resolves the project's
MEMORY.md, and if it's over the threshold, prints a short nudge to stdout (which
SessionStart forwards to the model as context). It stays silent and exits 0 otherwise, so
it's invisible on healthy projects.

## Install (user settings)

Add a `hooks.SessionStart` entry to `~/.claude/settings.json`. If the file already has
other top-level keys (model, tui, …), merge — don't overwrite. Use the **update-config**
skill to edit settings.json safely; here is the shape to add:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/memory-compaction/scripts/session_start_check.py"
          }
        ]
      }
    ]
  }
}
```

Notes:
- Put it in **user** settings (`~/.claude/settings.json`) so it applies to every project,
  matching the portable design — the script resolves each project's own memory dir at run
  time.
- The threshold lives in the script (`THRESHOLD_KB = 15`). Change it there, in one place.
- SessionStart hooks run on session start/resume. The nudge is advisory: the model sees it
  as context and decides to run the skill. It won't interrupt work mid-session.

## Verify the hook fires

After installing, start a fresh session in a project whose MEMORY.md is over 15 KB and
confirm the nudge appears in the session's startup context. Or test the checker directly:

```bash
python3 ~/.claude/skills/memory-compaction/scripts/session_start_check.py /path/to/project/memory
```

It should print the nudge for an over-budget dir and nothing for an under-budget one.
