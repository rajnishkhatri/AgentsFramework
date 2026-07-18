# Spec — Workspace-neutral, multi-agent-portable SDD lifecycle skills + `.skill` export

**Status:** Draft (clarify pass complete) — 2026-07-15
**Owner:** Rajnish Khatri
**Related:** [sdd-skills-portability-export.brainstorm.md](sdd-skills-portability-export.brainstorm.md) (Stage 1, gate resolved) · ADR-0032 (workspace-binding contract — to be written) · prior art: `scripts/sync_skills.py`, `tests/architecture/test_skills_mirror_parity.py`, `tests/code_reviewer/test_cursor_mdc_parity.py`, `docs/skills/README.md` (portable↔binding split)

**Clarify-pass resolutions (2026-07-15):**
- **Q1 — Portable purity:** zero repo tokens in the portable body; all concrete
  values come from the binding (FR-1/FR-2).
- **Q2 — Resolution model:** placeholders ship literally in canonical + mirrors;
  the reading agent resolves the binding AT RUNTIME and **auto-adapts to a foreign
  workspace's ecosystem** (FR-6a/6b/8a). This is the load-bearing change vs the
  original static-substitution draft — the skills are language/ecosystem agnostic.
- **Q2b — Binding home:** resolved binding lives at `.sdd/binding.toml` in the
  consumer workspace root; THIS repo's reference at `docs/skills/_sdd/`.
- **Q2c — Adapt strictness:** propose → human-confirm → persist (AP-6: never run a
  guessed check/test command without confirmation).
- **Q3 — Pointer thinness:** Copilot `.instructions.md` = frontmatter + 1-line
  pointer only (FR-15).
- **Q4 — Emitter scope:** the six SDD archives only; the 4 legacy hand-zipped
  archives left as-is (§6).

---

## 1. Goal

Make the six SDD lifecycle skills (`sdd-lifecycle`, `sdd-brainstorm`, `sdd-spec`,
`sdd-replan`, `sdd-implement`, `sdd-converge`) usable in **any workspace** and by
**any coding agent** — today Cursor + Claude Code, adding GitHub Copilot with an
extensible registry — then **export** them as drop-in `.skill` archives. A team on
a different repo/agent installs the archive, fills in a small binding template, and
runs the same 10-stage SDD methodology.

## 2. Context

The six skills are canonical in `docs/skills/<name>/SKILL.md`, byte-mirrored to
`.claude/skills/` + `.cursor/skills/` by `scripts/sync_skills.py`. Stage-1 grounding
proved every skill is densely welded to THIS repo: **9× `AGENTS.md`, 6× the runbook,
6× `make check`, 4× `pytest tests/architecture/ -q`, 3× `docs/adr/0000-template.md`,
2× `ADR-OK:` / `docs/adr/GATES.md` / `docs/plan/`, plus `eval_capture.record()`,
`scripts/hooks/*.py`, `G8-OK:`**. Only the 10-stage skeleton + human↔agent micro-loop
+ EARS + red/green TDD are portable. The portable↔binding split is a proven repo
pattern (`llm-eval-grounded-theory` portable ↔ `agentsframework-eval-probe` binding,
`docs/skills/README.md`). `.skill` archives already exist as **tracked zips**
(`<name>/SKILL.md` + `references/`/`scripts/`/`assets/`) but there is **no emitter
script** and none carries a binding config. GitHub Copilot custom-instructions format
verified against current GitHub docs (2026): repo-wide `.github/copilot-instructions.md`;
path-specific `.github/instructions/NAME.instructions.md` with `applyTo:` glob
frontmatter, auto-discovered on save.

## 3. Functional requirements (EARS)

### D1 — Portable skill core reads a binding (rewrite the six in place)

- **FR-1 (failure-first).** IF a portable SDD `SKILL.md` body contains a
  hard-coded THIS-repo binding token (`AGENTS.md`, `make check`,
  `pytest tests/architecture/`, `docs/adr/`, `docs/plan/`, `eval_capture`,
  `scripts/hooks/`, `ADR-OK:`, `G8-OK:`, `sdd_lifecycle_runbook.md`,
  `ai-slop-backpressure`, `explore` subagent-by-name) THEN the portable-core
  guard test SHALL fail, naming the file, line, and token.
- **FR-2.** THE SYSTEM SHALL express every abstracted binding as a placeholder
  drawn from a fixed vocabulary (`{{constitution}}`, `{{check_gate}}`,
  `{{test_gate}}`, `{{spec_home}}`, `{{plan_home}}`, `{{adr_home}}`,
  `{{adr_template}}`, `{{decision_log}}`, `{{adr_waiver_token}}`,
  `{{test_waiver_token}}`, `{{breadth_read_tool}}`, `{{methodology_source}}`,
  `{{gate_catalog}}`) — the same vocabulary the binding schema (§4) defines.
- **FR-3.** WHEN this repo's reference binding is substituted into the six
  portable cores THE SYSTEM SHALL reproduce the current (pre-rewrite) skill
  guidance semantically — i.e. every binding token that appears today has a
  placeholder that resolves back to the identical string under the reference
  binding (round-trip completeness).
- **FR-4.** THE SYSTEM SHALL keep the 10-stage skeleton, stage-ownership table,
  human↔agent micro-loop, EARS notation, and red/green TDD discipline unchanged
  and repo-agnostic (these are the portable core — no placeholder needed).

### D5 — Binding is placeholders + runtime resolution + first-run auto-adapt

**Resolution model (clarify Q2): placeholders ship literally; the reading agent
resolves the binding AT RUNTIME — this repo from `binding.reference.toml`, a
foreign repo by auto-detecting its ecosystem and proposing values for human
confirmation. The skills are coding-language/ecosystem agnostic and adapt to the
workspace they land in.**

- **FR-5.** THE SYSTEM SHALL define a single binding schema file
  (`docs/skills/_sdd/binding.schema.md` — human+machine readable) enumerating the
  §4 placeholder vocabulary, each with: purpose, this-repo reference value, and a
  "fill this" prompt.
- **FR-6.** THE SYSTEM SHALL provide a committed reference instance
  (`docs/skills/_sdd/binding.reference.toml`) whose values are THIS repo's real
  bindings (`constitution = "AGENTS.md"`, `check_gate = "make check"`, …).
- **FR-6a (runtime resolution).** WHEN a portable SDD skill is invoked THE SYSTEM
  SHALL resolve each `{{placeholder}}` from the workspace binding: use
  `binding.reference.toml` if present at the workspace root's `.sdd/` (or
  `docs/skills/_sdd/` in THIS repo), else fall to first-run auto-adapt (FR-6b).
- **FR-6b (first-run auto-adapt — foreign workspace).** IF no resolved binding is
  found THEN the first-run preamble SHALL instruct the agent to inspect the
  workspace for ecosystem markers (constitution doc: `AGENTS.md`/`CLAUDE.md`/
  `CONTRIBUTING.md`/`.cursorrules`; gate command: `Makefile` target/`package.json`
  scripts/`justfile`/`tox.ini`; test command: detected test runner; ADR/decision
  homes: `docs/adr/`/`docs/decisions/` or absent), PROPOSE a filled binding, and
  require human confirmation before writing `.sdd/binding.toml` — never silently
  assume (AP-6: undecidable → ask, don't fabricate).
- **FR-7.** WHERE a `.skill` archive is produced (see D3) THE SYSTEM SHALL bundle
  the `binding.template.toml` (schema keys, `<fill>` values) + a `FIRST_RUN.md`
  preamble describing the FR-6b auto-adapt flow.
- **FR-8 (failure-first).** IF `binding.reference.toml` is missing a key that the
  schema declares, or declares a key the schema does not, THEN a guard test SHALL
  fail (schema↔reference completeness).
- **FR-8a (live-UX preservation).** WHILE running inside THIS repo THE SYSTEM
  SHALL resolve the binding automatically from the committed reference (no manual
  fill), so today's live SDD guidance is semantically unchanged despite the
  mirrors now carrying placeholders.

### D2 — Adapter registry (generalize the 2-target sync)

- **FR-9.** THE SYSTEM SHALL replace `scripts/sync_skills.py`'s hard-coded
  `TARGETS` 2-tuple with an adapter registry where each adapter declares its
  discovery path and projection function.
- **FR-10.** WHEN `make skills-sync` runs THE SYSTEM SHALL produce the Claude
  (`.claude/skills/`) and Cursor (`.cursor/skills/`) mirrors **byte-identically to
  today** (regression-safe: existing `test_skills_mirror_parity.py` stays green
  unchanged before Copilot is added).
- **FR-11.** THE SYSTEM SHALL make adding a new coding agent a single new registry
  entry — no change to skill bodies or the core sync/check logic.
- **FR-12 (failure-first).** IF any registered adapter's projection has drifted
  from canonical THEN `python scripts/sync_skills.py --check` SHALL exit non-zero
  and name the drifted target/path (generalized per-adapter, not the fixed 2).

### D4 — Copilot adapter (thin pointer, never prose copy)

- **FR-13.** THE SYSTEM SHALL project a repo-wide `.github/copilot-instructions.md`
  and per-skill `.github/instructions/sdd-<name>.instructions.md` files, each a
  **thin pointer** to the canonical `docs/skills/sdd-<name>/SKILL.md` — never
  restating skill prose (mirrors `.cursor/rules/*.mdc`).
- **FR-14.** THE SYSTEM SHALL write valid Copilot `applyTo:` glob frontmatter in
  each `.instructions.md` file (verified format: `applyTo: "<glob>"`,
  comma-separated for multiple).
- **FR-15 (failure-first).** IF a `sdd-<name>.instructions.md` pointer references a
  `docs/skills/` path that does not exist, or contains any body prose beyond
  frontmatter + a single one-line `see docs/skills/sdd-<name>/SKILL.md` pointer
  (clarify Q3: pointer + `applyTo` + 1-line description only), THEN
  `test_copilot_instructions_parity.py` SHALL fail.

### D3 — `.skill` emitter + export

- **FR-16.** THE SYSTEM SHALL provide `scripts/pack_skills.py` + a `make
  skills-pack` target that zips `docs/skills/<name>/` → `docs/skills/<name>.skill`
  matching the existing tracked layout (`<name>/SKILL.md` + `references/`/`scripts/`
  as present).
- **FR-17.** WHERE a skill is an SDD skill THE SYSTEM SHALL include the D5
  `binding.template.toml` + first-run preamble inside its `.skill` archive.
- **FR-18 (failure-first).** IF a tracked `*.skill` archive's contents differ from
  its source `docs/skills/<name>/` (+ the D5 template for SDD skills) THEN
  `python scripts/pack_skills.py --check` SHALL exit non-zero and name the drift
  (mirrors `sync_skills.py --check`; makes the archives a mechanical projection,
  not hand-zipped).
- **FR-19.** THE SYSTEM SHALL emit exactly the six SDD `.skill` archives on
  `make skills-pack`.

## 4. Data model / contracts

**Binding vocabulary** (the placeholder set; TOML keys in
`binding.reference.toml` / `binding.template.toml`):

| Key | This-repo reference value | Abstracts |
|---|---|---|
| `constitution` | `AGENTS.md` | the rules-of-record doc |
| `check_gate` | `make check` | the pre-commit gate command |
| `test_gate` | `pytest tests/architecture/ -q` | the arch/invariant test command |
| `spec_home` | `docs/plan/` (+ `_spec_template.md`) | where specs live |
| `plan_home` | `docs/plan/` | where plans live |
| `adr_home` | `docs/adr/` | ADR bundle dir |
| `adr_template` | `docs/adr/0000-template.md` | ADR template |
| `decision_log` | `docs/adr/decisions.md` | small-decision log |
| `adr_waiver_token` | `ADR-OK:` | ratchet waiver token |
| `test_waiver_token` | `G8-OK:` | test-weakening waiver token |
| `breadth_read_tool` | `explore` subagent | broad read-only fan-out mechanism |
| `methodology_source` | `docs/research/.../sdd_lifecycle_runbook.md` | full runbook |
| `gate_catalog` | `docs/adr/GATES.md` (G1–G9) | comprehension-gate catalog |

**Adapter contract** (D2): `Adapter = {name, discovery_path: Path,
project(skill_dir) -> files}`. Claude/Cursor `project` = identity byte-copy;
Copilot `project` = emit pointer `.instructions.md` + repo-wide file.

**`.skill` archive** (D3/D5): zip; top dir = `<name>/`; contains `SKILL.md` +
present `references/`/`scripts/`/`assets/`; SDD skills additionally carry
`<name>/binding.template.toml` + `<name>/FIRST_RUN.md`.

## 5. Invariants & security boundaries

- **None of the 8 Architecture Invariants are touched** — skills, sync scripts,
  and archives are tooling/docs, not a package layer (`trust/`→`services/`→
  `components/`→`orchestration/`). No layer imports change.
- **New abstraction (⚠️ Ask-first → ADR-0032):** the workspace-binding contract
  (placeholder vocabulary + adapter registry). Stated per G1: it buys one source
  of truth reusable across repos/agents; the rejected simpler thing was D6
  (duplicate portable skill). Recorded in the brainstorm gate.
- **No new pyproject dependency** — `zipfile`/`tomllib` are stdlib (Python 3.13).
- **No secrets, no live LLM in CI** — all guards are deterministic file checks.

## 6. Edge cases

- **Axial archive top-dir wrinkle:** the existing `agentsframework-axial-coding.skill`
  uses top dir `axial-skill-pkg/`, not `<name>/`. The emitter SHALL use a
  deterministic `<name>/` top dir; the four pre-existing hand-zipped archives are
  out of scope for `--check` unless adopted (document, don't silently reformat).
- **Placeholder appearing in prose legitimately** (e.g. a skill *discussing* the
  word "constitution" generically) — the guard keys on the exact binding *tokens*
  (`AGENTS.md`, `make check`), not English words, to avoid false positives.
- **Foreign workspace with NO detectable markers** (no Makefile, no constitution
  doc, no ADR dir) — first-run auto-adapt (FR-6b) proposes `<none>` for the absent
  binding and the skill degrades gracefully (skips that gate's step), asking the
  human rather than fabricating a command that would fail.
- **Ambiguous ecosystem** (both a `Makefile` and `package.json` scripts) —
  auto-adapt proposes the candidates and asks; never picks silently.
- **Placeholders shipped in mirrors, read live in THIS repo** — FR-8a: the
  reference binding auto-resolves, so live SDD work is unchanged; this is the one
  behavior-adjacent risk and is covered by a round-trip test (FR-3) + FR-8a.
- **Copilot path-specific support gap:** github.com honors path-specific
  `.instructions.md` only for cloud agent + code review today (IDE separate) —
  documented as a known limitation, not a blocker (the repo-wide file has broad
  coverage).
- **Empty `references/`/`scripts/`** in a skill dir → emitter includes only what
  exists (governance-trace-audit has no `scripts/`).

## 7. Non-functional requirements

- **Determinism:** all four guard tests (FR-1, FR-8, FR-12, FR-15, FR-18) are L1
  deterministic file/AST checks — in `make check`, zero network, zero LLM.
- **Reversibility:** the rewrite is git-reversible; the reference binding
  round-trips (FR-3) so behavior is provably preserved.
- **Zip determinism:** `pack_skills.py` SHALL write archives with fixed member
  order + normalized mtime so `--check` is stable across machines.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `tests/architecture/test_sdd_portable_core.py::test_no_repo_binding_token_leaks` | L1 | yes |
| FR-3 | `tests/architecture/test_sdd_portable_core.py::test_reference_binding_round_trips` | L1 | yes |
| FR-4 | `tests/architecture/test_sdd_portable_core.py::test_portable_skeleton_preserved` | L1 | yes |
| FR-8 | `tests/architecture/test_sdd_binding_schema.py::test_schema_reference_complete` | L1 | yes |
| FR-10/12 | `tests/architecture/test_skills_mirror_parity.py` (generalized per-adapter) | L1 | yes |
| FR-11 | `tests/architecture/test_sync_adapter_registry.py::test_new_adapter_is_one_entry` | L1 | yes |
| FR-13/15 | `tests/architecture/test_copilot_instructions_parity.py` | L1 | yes |
| FR-14 | `…::test_applyto_frontmatter_valid` | L1 | yes |
| FR-16/19 | `tests/architecture/test_skills_pack.py::test_emits_six_sdd_archives` | L1 | yes |
| FR-18 | `tests/architecture/test_skills_pack.py::test_pack_check_detects_drift` | L1 | yes |

Failure-path tests (FR-1, FR-8, FR-12, FR-15, FR-18) authored + seen-to-fail
before the implementation that makes them pass.

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test seen to fail first.
- [ ] `make check` green (lint + format-check + pyright + test).
- [ ] `tests/architecture/` green; the generalized mirror-parity test passes with
      Claude/Cursor byte-identical to pre-change (FR-10).
- [ ] `make skills-sync` + `make skills-pack` both idempotent; both `--check`
      variants green.
- [ ] ADR-0032 appended (workspace-binding contract) + `index.md`/`log.md` lines.
- [ ] Six `docs/skills/sdd-*.skill` archives emitted and tracked.
- [ ] Actual command output pasted (not summarized) for verification claims.
