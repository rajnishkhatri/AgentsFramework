---
name: memory-compaction
type: skill
description: >-
  Compact and maintain Claude Code's persistent memory index (MEMORY.md) when it grows
  too large. MEMORY.md is loaded into context at the start of EVERY session for a project
  and only ever grows as sessions append memories — past a hard limit (~24.4 KB) the
  harness silently truncates it, hiding every memory below the cut line so recall never
  reaches them. Use this skill whenever MEMORY.md exceeds ~15 KB, whenever a SessionStart
  hook or the harness warns that the memory index is large/over budget/truncated, or
  whenever the user asks to compact, trim, shrink, clean up, optimize, or reorganize their
  memory file, memory index, or MEMORY.md. Also trigger on phrases like "my memory file is
  too big", "memories aren't loading", or "reduce memory size". The fix is lossless: index
  lines are re-hooked to short pointers while the full detail stays in the topic files.
---

# Memory compaction

## Why this matters

Claude Code keeps per-project memory in `~/.claude/projects/<encoded-cwd>/memory/`:

- **`MEMORY.md`** is the **index** — one list line per memory. It is **re-injected into
  context at the start of every session** (it appears in the `claudeMd` system-reminder).
  It is *always-loaded* and therefore costs tokens on every future conversation.
- **The topic `*.md` files** beside it are the **detail store** — loaded only on demand,
  effectively free until used.

The failure mode this skill prevents: MEMORY.md **only grows** — every session can append
an entry, none shrink it — so it drifts over budget unnoticed. Past the harness hard limit
(~24.4 KB) **the index load is truncated**, and every memory below the cut line keeps
existing as a file but loses its visible hook. Recall silently never reaches it. That is
real memory loss, not cosmetics.

The root cause is almost always the same: index lines that should be short *hooks* have
been bloated into full paragraphs — root cause, `file:line`, fix, status — duplicating
detail that already lives in the topic file. **The whole detail already exists one level
down.** Compaction just deletes the duplicate from the always-loaded tier.

## When to run

Trigger compaction when **MEMORY.md exceeds ~15 KB**. Compact down to **≤12 KB** so there
is runway before it re-triggers. The harness hard limit is ~24.4 KB; 15 KB is the
intervene-early line and 12 KB the target, leaving comfortable headroom.

## The procedure

### 1. Locate and measure

Resolve the memory directory from the current project (don't hardcode a path). Run the
analyzer — it does all the deterministic measurement so you don't eyeball it:

```bash
python <skill-dir>/scripts/analyze_memory.py [MEMORY_DIR]
```

It prints JSON: `size_kb`, `entry_count`, per-hook char stats (`hook_avg_chars`,
`hook_max_chars`, `hooks_over_hard`, and the offending `long_hooks`), `dangling_links`,
`orphan_topic_files`, `duplicate_links`, and `resolved_candidates` (entries that
self-mark RESOLVED/SUPERSEDED — prune candidates). If `MEMORY_DIR` is omitted the script
derives it from `CLAUDE_PROJECT_DIR` / cwd.

If `size_kb` is already ≤12, there's nothing to do — say so and stop.

**Measure hooks by character, never by byte.** The index is full of multi-byte UTF-8
(`—`, `→`, `≤`, `§`, `×`) — the em dash alone is 3 bytes — so byte-length overstates a
hook by ~1.5×. The scripts already count characters; if you spot-check by hand, use
`len()` in Python, not `wc -c` / `awk length`. This is the single most common trap.

### 2. Re-hook (the primary, lossless lever)

This is the main fix and it loses **zero** information. For each bloated index line,
replace the fat paragraph with a short hook of **≤~120 characters** (hard ceiling 150).
The **canonical, authoritative source for the hook is each topic file's `description:`
frontmatter** — pull it in verbatim. This matters because the description was curated by
whoever saved the memory; writing your own paraphrase risks subtle drift from what the
memory actually says. Only hand-write a hook when a file has no usable `description:` (or
it's itself over the limit), and then keep it strictly faithful to the topic file's
content. Read every description in one pass with:

```bash
# harvest every topic file's description in one pass
for f in <MEMORY_DIR>/*.md; do
  [ "$(basename "$f")" = MEMORY.md ] && continue
  printf '%s ::: ' "$(basename "$f")"
  awk -F'description: ' '/^description:/{print $2; exit}' "$f" | sed 's/^"//; s/"$//'
done
```

When you rewrite each line, preserve:
- the exact `[Title](topic-file.md)` link target — **never rename a file**;
- a leading date stamp where it disambiguates (`2026-06-25 …`);
- any load-bearing `[[wikilink]]` cross-references between memories.

Keep the `# Memory index` header. Drop transient harness footers (e.g. a
`> WARNING: MEMORY.md is …KB` line) — that's a runtime message, not content.

**Watch the separator.** A title may itself contain an em dash
(`[Cloudflare removed — BFF on Cloud Run](…)`). The hook is the text after the *link*,
not after the first ` — `. The scripts handle this; mind it when editing by hand.

### 3. Re-verify, then decide if deeper levers are needed

Run the gate:

```bash
python <skill-dir>/scripts/verify_memory.py [MEMORY_DIR] --target-kb 12
```

It checks size ≤ target, no hook over 150 chars, no duplicate/dangling links, and that
every topic file is still represented in the index (link **or** deliberate plain-text
entry). Exit 0 = all pass.

**If re-hook alone gets under 12 KB → done.** Re-hooking typically cuts the index by
~50–60%, so this is the common case.

**If it does NOT get under budget**, deeper levers are available — but they delete or
merge memories, so **confirm with the user before applying either** (use AskUserQuestion).
See `references/deeper_levers.md` for how to prune resolved memories and consolidate
topic clusters safely. Default posture: re-hook first; only go deeper on the user's say-so.

### 4. Repair what the analyzer flags

While you're in the file, fix anything the report surfaced:
- **Dangling links** (a `](file.md)` with no file on disk). There is always a
  **non-destructive repair — never treat this as delete-or-fail**:
  - If the link should point at an existing file (typo, renamed file, or a *repo doc*
    rather than a memory file), repoint it.
  - Otherwise **convert the entry to plain text**: drop the `[Title](file.md)` markdown
    link but **keep the title and note as plain text**. This preserves the memory/history
    AND clears the `no_dangling_links` check, so the verifier reaches a clean exit 0
    *without deleting anything*. This is the correct move even when the user has forbidden
    deletion — converting a broken link to plain text removes no memory.
- **Orphan topic files** (on disk but unreferenced): add a one-line hook for each so the
  detail is reachable again.

### 5. Report — with evidence, not just claims

A bare "compacted to 6.9 KB, all checks pass" is unverifiable. Make your report
**auditable** so the user can independently confirm it:

- **Paste the verifier's actual output**, including the command and its exit status — e.g.
  the `verify_memory.py --target-kb 12` lines and `ALL CHECKS PASS`. The bundled gate is the
  source of truth; don't substitute ad-hoc `wc -c` / `grep` one-liners for it.
- **Show before/after from the analyzer**: the key `analyze_memory.py` fields (`size_kb`,
  `entry_count`, `hook_avg_chars`, `hook_max_chars`, `dangling_links`) for both states, so
  the size and hook-length claims are checkable — not just a summary sentence.
- **Spot-check the re-hook source**: show 2–3 explicit pairs of *topic file `description:`
  line → new index hook*, proving the hooks came from the authoritative frontmatter and
  didn't drift into your own paraphrase.
- **State the lossless invariant concretely**: topic-file count before vs after (must be
  equal for a pure re-hook) and entry count before vs after. If you pruned or merged
  anything, name exactly what — those are the only steps that remove information.
- **Recommend prevention.** If MEMORY.md grew over budget once, it will again — it only
  grows. Recommend the **SessionStart auto-trigger** (see step "wire automatic triggering"
  below) and offer to install it, unless it's already wired.

## Guardrails

- **Re-hook is lossless; pruning and consolidating are not.** Never delete or merge a
  memory without explicit user confirmation. Re-hooking needs none — it only re-compresses
  the index.
- **Never touch the topic `*.md` files during re-hook.** The detail must stay intact; you
  are only editing `MEMORY.md`.
- **Treat ~18 KB as a soft ceiling and ~24.4 KB as the hard harness limit.** If you can't
  reach 12 KB losslessly and the user declines deeper levers, getting under 18 KB still
  protects against truncation — report the residual honestly rather than silently
  over-trimming hooks into uselessness.

## Optional: wire automatic triggering

A skill only fires when the model judges it relevant; it cannot watch a file size by
itself. To auto-fire at 15 KB, install a `SessionStart` hook that checks the size and
injects a nudge. The snippet and install steps are in `references/auto_trigger_hook.md`.
