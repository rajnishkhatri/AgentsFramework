# SDD workspace-binding schema

> The **contract** that makes the six SDD lifecycle skills portable. Each skill's
> body uses `{{placeholder}}` tokens instead of this-repo-specific strings; a
> per-workspace binding resolves them at runtime. This file is the single source
> of the vocabulary — the placeholder set, what each abstracts, this repo's
> reference value, and the prompt a foreign workspace answers on first run.
>
> Governed by [ADR-0032](../../adr/0032-workspace-binding-contract.md). Realized by
> [sdd-skills-portability-export.spec.md](../../plan/sdd-skills-portability-export.spec.md) (FR-5).

## Resolution order (how a skill fills these at runtime)

1. `.sdd/binding.toml` at the workspace root (a foreign repo, once confirmed).
2. `docs/skills/_sdd/binding.reference.toml` (THIS repo's committed reference).
3. Neither present → **first-run auto-adapt** (see [FIRST_RUN.md](FIRST_RUN.md)):
   inspect the ecosystem, propose values, **require human confirmation**, persist
   to `.sdd/binding.toml`. Never run a guessed gate command silently (AP-6).

## The vocabulary (13 keys)

| Key (`{{placeholder}}`) | Abstracts | This-repo reference value | First-run fill-prompt |
|---|---|---|---|
| `constitution` | The rules-of-record doc every stage checks against. | `AGENTS.md` | "Which file holds this repo's binding engineering rules/invariants? (e.g. `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`)" |
| `check_gate` | The one pre-commit gate command. | `make check` | "What single command runs the full lint+format+typecheck+test gate? (e.g. `make check`, `npm run verify`, `just ci`)" |
| `test_gate` | The invariant/architecture test command. | `pytest tests/architecture/ -q` | "What command runs the architecture/invariant tests that MUST pass? (e.g. `pytest tests/architecture/ -q`, `npm test`)" |
| `spec_home` | Where specs (+ the spec template) live. | `docs/plan/` (template `docs/plan/_spec_template.md`) | "What directory holds specs, and is there a spec template file?" |
| `plan_home` | Where plans and task lists live. | `docs/plan/` | "What directory holds plan / task-list docs?" |
| `adr_home` | The decision-record bundle directory. | `docs/adr/` | "What directory holds Architecture Decision Records (or equivalent)? `<none>` if the workspace has none." |
| `adr_template` | The ADR template to copy. | `docs/adr/0000-template.md` | "Is there an ADR template file to copy for a new record?" |
| `decision_log` | The append-only small-decision log. | `docs/adr/decisions.md` | "Where are small non-obvious decisions logged? `<none>` if unused." |
| `adr_waiver_token` | Commit-message token that waives the ADR ratchet. | `ADR-OK:` | "What commit-message token (if any) waives the missing-ADR merge gate?" |
| `test_waiver_token` | Commit-message token that waives the test-weakening gate. | `G8-OK:` | "What commit-message token (if any) justifies a deleted/skipped test?" |
| `breadth_read_tool` | The read-only broad-fan-out mechanism for grounding. | the `explore` subagent | "What tool/agent does broad read-only codebase exploration here? (e.g. a subagent, `grep`/`rg`, an IDE search)" |
| `methodology_source` | The full SDD methodology runbook. | `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md` | "Where does the full SDD methodology text live? `<none>` to rely on the skill bodies alone." |
| `gate_catalog` | The comprehension-gate catalog (G-series wordings). | `docs/adr/GATES.md` | "Is there a catalog of comprehension gates / review checklists? `<none>` if not." |

## Optional `examples` section

The binding MAY carry an `[examples]` table whose values are workspace-specific
illustrations the portable skill bodies reference generically (e.g. a
"deterministic-cascade precedent", a "live prod surface vs dev surface" pair).
Absent in a foreign workspace → the skill uses the generic phrasing with no
concrete instance. In THIS repo the reference binding supplies the original
`components/router.py` / `services/guardrails.py` / `middleware/app_prod.py`
instances so this-repo readers see them unchanged (spec FR-3).

Keys used by the portable bodies:

| `[examples]` key | Reference value (this repo) |
|---|---|
| `deterministic_cascade` | `components/router.py` (router deterministic tree) + `services/guardrails.py` (regex→classifier→LLM cascade, `decision_stage` audit field) |
| `live_prod_surface` | `middleware/app_prod.py` hand-builds prod routes; `agent_ui_adapter/server.py` is dev/standalone |
| `eval_capture_rule` | record every LLM call via `eval_capture.record()` with `user_id`+`task_id` |
| `hook_instrumentation` | `scripts/hooks/*.py` (PreToolUse/PostToolUse/Stop/SubagentStop/SessionStart) |
