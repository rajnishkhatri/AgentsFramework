# Skills bundle log

Chronological history of the skills bundle, newest first (ISO-8601).

- 2026-06-25 — Added `memory-compaction` skill to the bundle: re-hook-first lossless compaction of Claude Code's always-loaded `MEMORY.md` index when it exceeds ~15 KB (target ≤12 KB), with bundled `analyze_memory.py` / `verify_memory.py` scripts, deeper-levers + auto-trigger references, and a SessionStart hook. Mirrors the live skill at `~/.claude/skills/memory-compaction`. Includes the packaged `memory-compaction.skill`.
- 2026-06-20 — Declared `docs/skills/` an OKF bundle: added `index.md` + this `log.md`, added `type: skill` frontmatter to all 7 `SKILL.md` Concepts. Convention pinned in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md); linted by `scripts/okf_lint.py`.
