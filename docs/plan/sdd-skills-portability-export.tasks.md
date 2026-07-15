# Tasks — Workspace-neutral, multi-agent-portable SDD skills + `.skill` export

**Realizes:** [sdd-skills-portability-export.spec.md](sdd-skills-portability-export.spec.md) · [plan](sdd-skills-portability-export.plan.md) · [ADR-0032](../adr/0032-workspace-binding-contract.md)

Atomic tasks, red/green TDD. `[dep: Tn]` = must follow. `[∥]` = parallel-safe
with siblings. Each task's **Verify** maps 1:1 to an EARS criterion.

## Phase 1 — Binding contract

- **T1.** Write `docs/skills/_sdd/binding.schema.md` — the 13-key vocabulary
  (§4 table), each key with purpose + reference value + fill-prompt.
  **Verify (FR-5):** file lists all 13 keys, each with purpose + reference value +
  fill-prompt; keys == the placeholder set used in T5. `[∥]`
- **T2.** Write `docs/skills/_sdd/binding.reference.toml` — THIS repo's real values
  for all 13 keys. **Verify (FR-6):** every schema key present with this-repo value. `[dep: T1]`
- **T3.** Author `test_sdd_binding_schema.py::test_schema_reference_complete` **RED
  first**, then make green. **Verify (FR-8):** fails if reference⊄schema or
  schema⊄reference; green with T1+T2. `[dep: T2]`

## Phase 2 — Portable-core guard + rewrite (the spine)

- **T4.** Author `test_sdd_portable_core.py::test_no_repo_binding_token_leaks`
  **RED against the CURRENT six skills** — must fail now (they contain `AGENTS.md`
  etc.). Token list = the §4 binding tokens. **Verify (FR-1):** red before T5,
  names file+line+token. `[dep: T3]`
- **T5.** Rewrite the six `docs/skills/sdd-*/SKILL.md`: replace every binding token
  with its `{{placeholder}}`; genericize repo-specific worked examples (router/
  guardrail/prod-surface) and move concrete instances to `binding.reference.toml`
  `examples`. **Verify (FR-1/FR-2):** T4 goes green; only vocabulary placeholders
  remain. `[dep: T4]`
- **T6.** Add `test_sdd_portable_core.py::test_reference_binding_round_trips` —
  substituting the reference binding into each portable core reproduces every
  binding string present today. **Verify (FR-3):** green. `[dep: T5]`
- **T7.** Add `test_sdd_portable_core.py::test_portable_skeleton_preserved` — the
  10-stage table, stage-ownership, micro-loop, EARS, red/green lines are intact +
  repo-agnostic. **Verify (FR-4):** green. `[dep: T5]`
- **T8.** Write `docs/skills/_sdd/binding.template.toml` (keys, `<fill>` values) +
  `docs/skills/_sdd/FIRST_RUN.md` (the FR-6b inspect→propose→confirm→persist flow,
  `.sdd/binding.toml` target). **Verify (FR-6b/7):** template keys == schema;
  FIRST_RUN names the auto-adapt steps + AP-6 confirm gate. `[dep: T1]` `[∥ T4]`
- **T9.** Add the runtime-resolution + auto-adapt guidance to each portable
  SKILL.md preamble (resolve from `.sdd/binding.toml` / `docs/skills/_sdd/` else
  first-run). **Verify (FR-6a/8a):** each skill states the resolution order;
  this-repo path auto-resolves. `[dep: T5]`

## Phase 3 — Sync propagation + adapter registry

- **T10.** `make skills-sync` to propagate the rewritten (placeholder) canonical to
  `.claude/skills/` + `.cursor/skills/`. **Verify (FR-10):** `sync_skills.py
  --check` green; mirrors byte-identical to canonical. `[dep: T5]`
- **T11.** Refactor `scripts/sync_skills.py`: `TARGETS` 2-tuple → `ADAPTERS`
  registry (`{name, discovery_path, project}`); Claude+Cursor adapters = identity
  byte-copy. Generalize `check()`/`sync()` to iterate adapters. **Verify (FR-9):**
  Claude/Cursor output byte-identical to pre-refactor (diff = ∅). `[dep: T10]`
- **T12.** Generalize `test_skills_mirror_parity.py` to iterate the registry (not 2
  fixed paths). **Verify (FR-12):** drift in ANY adapter → non-zero + named. `[dep: T11]`
- **T13.** Add `test_sync_adapter_registry.py::test_new_adapter_is_one_entry` — a
  fixture adapter added to the registry is picked up with no core-logic change.
  **Verify (FR-11):** green. `[dep: T11]`

## Phase 4 — Copilot adapter

- **T14.** Add `CopilotAdapter` to the registry: `project` emits
  `.github/copilot-instructions.md` (repo-wide pointer) + `.github/instructions/
  sdd-<name>.instructions.md` (frontmatter `applyTo:` + 1-line pointer). Run
  `make skills-sync` to generate them. **Verify (FR-13):** files exist; each is
  pointer-only. `[dep: T11]`
- **T15.** Author `test_copilot_instructions_parity.py` — (a) every pointer path
  resolves to an existing `docs/skills/sdd-*/SKILL.md`; (b) no body prose beyond
  frontmatter + 1 line; (c) `applyTo:` frontmatter parses + is a valid glob string.
  **Verify (FR-13/14/15):** green; fails on a broken path or prose bloat. `[dep: T14]`

## Phase 5 — Emitter + export

- **T16.** Write `scripts/pack_skills.py`: zip `docs/skills/<name>/` →
  `docs/skills/<name>.skill` (`<name>/` top dir; include SKILL.md + present
  references/scripts/assets; SDD skills also bundle `binding.template.toml` +
  `FIRST_RUN.md`). Deterministic member order + normalized mtime.
  **Verify (FR-16/17):** archive layout matches; SDD archives carry the template. `[dep: T8]`
- **T17.** Add `--check` to `pack_skills.py` + `make skills-pack` target.
  **Verify (FR-18):** `--check` non-zero + named when an archive drifts from source. `[dep: T16]`
- **T18.** Author `test_skills_pack.py` — `test_emits_six_sdd_archives` +
  `test_pack_check_detects_drift`. **Verify (FR-16/18/19):** exactly six SDD
  `.skill` emitted; drift detected. `[dep: T17]`
- **T19.** Run `make skills-pack`; commit the six `docs/skills/sdd-*.skill`.
  **Verify (FR-19):** six archives tracked. `[dep: T18]`

## Phase 6 — Docs + green gate

- **T20.** Update `docs/skills/README.md` — add the portable-SDD row + the binding
  contract + first-run flow; note Copilot support surface. **Verify:** README
  describes the contract + how to install into a foreign repo. `[dep: T5]` `[∥]`
- **T21.** Full gate: `make check` + `pytest tests/architecture/ -q` green; both
  `--check`s green; `skills-sync`/`skills-pack` idempotent. **Verify (DoD):** paste
  actual output. `[dep: T12,T13,T15,T18,T19,T20]`

## Parallelization map

- **Wave A (parallel):** T1, T8-prep, T20-draft.
- **Spine (sequential):** T1→T2→T3→T4→T5→{T6,T7,T9}.
- **Wave B (after T5):** T10→T11→{T12,T13}; T11→T14→T15.
- **Wave C (after T8):** T16→T17→T18→T19.
- **Converge:** T21.

Load-bearing critical path: T1→T2→T3→T4→T5→T10→T11→T14→T15 (+ T16→T18 branch).
