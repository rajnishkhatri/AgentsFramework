# First run in a new workspace — bind the SDD skills to your ecosystem

The six SDD lifecycle skills (`sdd-lifecycle`, `sdd-brainstorm`, `sdd-spec`,
`sdd-replan`, `sdd-implement`, `sdd-converge`) are **workspace-neutral**: their
bodies use `{{placeholder}}` tokens instead of any one repo's file paths or
commands. Before they can run here, those placeholders need your workspace's real
values — the **binding**.

## Resolution order (what a skill checks, in order)

1. **`.sdd/binding.toml`** at your repo root — the resolved binding for this
   workspace. If it exists and is filled, the skill uses it and does nothing else.
2. A committed **reference** binding shipped with the skill's home repo
   (`docs/skills/_sdd/binding.reference.toml`) — only relevant inside that repo.
3. **Neither present → first-run auto-adapt** (below).

## First-run auto-adapt — inspect → propose → confirm → persist

When no binding is found, the skill does **not** guess and run. It:

1. **Inspects your ecosystem** for markers of each binding key:
   - `constitution` → `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`,
     `.github/copilot-instructions.md`, a `docs/` conventions file.
   - `check_gate` → a `Makefile` target (`check`/`ci`/`verify`), `package.json`
     scripts, a `justfile`, `tox.ini`, `noxfile.py`, `pre-commit` config.
   - `test_gate` → the detected test runner (`pytest`, `npm test`, `go test`,
     `cargo test`, `gradle test`, …), narrowed to an architecture/invariant suite
     if one exists.
   - `spec_home` / `plan_home` → `docs/plan/`, `docs/specs/`, `specs/`, `.sdd/`.
   - `adr_home` / `adr_template` / `decision_log` → `docs/adr/`, `docs/decisions/`,
     `adr/`, or **absent** (`<none>`).
   - `adr_waiver_token` / `test_waiver_token` → any commit-message waiver
     convention the repo documents, else `<none>`.
   - `breadth_read_tool` → an available subagent / `rg` / IDE search.
   - `methodology_source` / `gate_catalog` → a runbook or review-checklist doc,
     else `<none>`.
2. **Proposes** a filled `binding.toml` — every key with its detected value (or
   `<none>`), shown to you.
3. **Requires your confirmation.** You edit or approve. Nothing runs against a
   guessed `check_gate`/`test_gate` until you confirm it — a wrong gate command is
   worse than asking (undecidable → ask, never fabricate).
4. **Persists** the confirmed binding to `.sdd/binding.toml`. Subsequent runs skip
   straight to step 1 of the resolution order.

## Graceful degradation

A key set to `<none>` means that step has no workspace analog — the skill **skips**
that step (e.g. no `adr_home` → the decision-record stage is a no-op) rather than
emitting a broken command or a fabricated path. When your ecosystem is ambiguous
(e.g. both a `Makefile` and `package.json` scripts), the skill proposes the
candidates and asks — it does not pick silently.

## Files in this bundle

- `binding.schema.md` — the 13-key vocabulary + fill-prompts (the contract).
- `binding.template.toml` — copy to `.sdd/binding.toml` and fill (or let first-run
  fill it).
- `binding.reference.toml` — the home repo's own values (a worked example).
