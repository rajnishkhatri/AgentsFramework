# scripts/hooks/ — Claude Code / Cursor Hook Scripts

> Nested guide. Loads when Claude reads a file under `scripts/hooks/`. Root
> `AGENTS.md` owns the inter-layer invariants; this file is local guidance for
> the harness hook scripts (Track A of the agentic-engineering harness adoption,
> `docs/plan/agentic_engineering_harness_adoption.plan.md`).

## What these are

Deterministic Python scripts the coding-agent harness invokes around tool calls.
They read a JSON payload on **stdin** and signal via **exit code** — they are the
lowest rung of the verification ladder (post-edit hooks below tests below LLM
review). Wired in `.claude/settings.local.json` (Claude Code) and
`.cursor/hooks.json` (Cursor).

## HOOK-1 — PostToolUse never blocks the edit

A `PostToolUse` hook fires **after** the write already happened — the file is on
disk. It therefore **MUST NOT** try to block: `exit 2` here is *feedback fed back
to the agent* so it self-corrects, never a gate. The "never block Edit/Write
mid-reasoning" rule. A `PostToolUse` script that treats `exit 2` as a hard block,
or that deletes / reverts the edited file, is a defect. (Reference:
`post_edit_ruff.py`.)

## HOOK-2 — PreToolUse is safety-only and thin

A `PreToolUse` hook MAY block (`exit 2` = block, stderr = reason). Keep it a
**last-resort deterministic backstop** for irreversible / high-blast-radius
actions the root `AGENTS.md` already forbids (push to `main`, broad `rm -rf`,
reading/writing `.env`). It is **not** a general command-policy engine — the
rich approve/ask/deny classifier owns that. If the deny-list grows, fold it into
the classifier instead. (Reference: `pre_bash_guard.py`.)

## HOOK-3 — Fail safe on malformed input

A hook that cannot parse its stdin payload must **do nothing and not interrupt
the agent** (return the allow/no-op exit code) — never crash, never block on a
parse error. An environment gap (a missing tool binary) is likewise a no-op with
a one-line stderr note, not a punishment for the agent. (Reference: both scripts'
`_read_*` helpers and the `RUFF.exists()` guard.)

## HOOK-4 — Advisory context hooks never block and stay bounded

A hook that *injects context* (stdout JSON with
`hookSpecificOutput.additionalContext` — e.g. on `SessionStart`) is advisory
plumbing, not a gate: it always exits 0, never emits `decision: block`, and
caps its payload (≤ ~10 KB) — an unbounded re-inject would defeat the
compaction it runs after. When over budget, degrade to a "re-read these paths"
list, never truncate mid-content. Silence (no stdout) is the correct output
when there is nothing to add. (Reference: `sessionstart_reinject.py`.)

**Event choice matters — `PostCompact` cannot inject context.** The CC hook
schema gives `PostCompact` *no decision control* (side-effects/logging only), so
a `{"hookSpecificOutput":{"hookEventName":"PostCompact","additionalContext":…}}`
payload is rejected with `Hook JSON output validation failed — (root): Invalid
input` and silently dropped. For "re-prime context after compaction" wire under
**`SessionStart`** (which *does* accept `additionalContext`) and gate on
`source == "compact"` — that reproduces the post-compaction timing without
firing on every startup/resume/clear. `additionalContext` is accepted on
`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolBatch`,
`Stop`, and `SubagentStop` — never `PostCompact`.
