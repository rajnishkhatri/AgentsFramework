# Skills bundle log

Chronological history of the skills bundle, newest first (ISO-8601).

- 2026-07-02 — Added the six `sdd-*` skills (`sdd-lifecycle`, `sdd-brainstorm`, `sdd-spec`, `sdd-replan`, `sdd-implement`, `sdd-converge`) operationalizing the 10-stage SDD lifecycle runbook (`docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md`); stages 7–8 reuse `code-review` + `make check`/arch-tests rather than new skills. Same change made the mirrors mechanical: `scripts/sync_skills.py` + `make skills-sync` project this bundle to `.claude/skills/` + `.cursor/skills/` (now tracked), enforced by `tests/architecture/test_skills_mirror_parity.py`.
- 2026-06-25 — Added `memory-compaction` skill to the bundle: re-hook-first lossless compaction of Claude Code's always-loaded `MEMORY.md` index when it exceeds ~15 KB (target ≤12 KB), with bundled `analyze_memory.py` / `verify_memory.py` scripts, deeper-levers + auto-trigger references, and a SessionStart hook. Mirrors the live skill at `~/.claude/skills/memory-compaction`. Includes the packaged `memory-compaction.skill`.
- 2026-06-20 — Declared `docs/skills/` an OKF bundle: added `index.md` + this `log.md`, added `type: skill` frontmatter to all 7 `SKILL.md` Concepts. Convention pinned in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md); linted by `scripts/okf_lint.py`.
