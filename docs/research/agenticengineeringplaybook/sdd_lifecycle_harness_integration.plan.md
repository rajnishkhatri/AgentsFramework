# SDD Lifecycle → Sensors/Hooks + Skills — Integration Plan

> **Status:** Plan (not started). Authored 2026-06-28.
> **Operationalizes:** [`sdd_lifecycle_runbook.md`](./sdd_lifecycle_runbook.md) (the 10-stage
> prose loop) and the deferred sensor/skill items in
> [`harness_adoption_critical_review_and_v2_plan.md`](./harness_adoption_critical_review_and_v2_plan.md)
> (2.1 Stop ADR trigger, 3.1 test-weakening, 5.1 explore subagent, 5.2 PostCompact).
> **Companion:** the practical-adoption assessment
> ([`../../plan/harness_adoption_v2_practical_adoption.plan.md`](../../plan/harness_adoption_v2_practical_adoption.plan.md)).

## Context

The SDD lifecycle runbook is currently **prose** — a 10-stage human↔agent loop whose
enforcement is mostly convention. This plan makes it **operational**: the stages with a
clean deterministic signal become **sensors/hooks** (fire automatically), and every
non-trivial stage becomes a **skill** (auto-detected by `description`-match in Claude Code
*and* Cursor, or human-invoked). It is the follow-through on the runbook's own
"[v2-Pn] fires once the v2 plan lands" column.

**Decisions locked (this session):**
1. Hooks = ADR-trigger **advise** + test-weakening detector + PostCompact re-inject.
2. **Per-stage** skills (up to 8), auto-detect + human-invocable.
3. Skills authored in `docs/skills/` (OKF bundle), mirrored to `.cursor/skills/` + `.claude/skills/`.
4. The ADR hook **advises via `additionalContext`, never blocks** (honest limit: hooks
   can't capture the typed answer).

## Verified facts (Claude Code 2.1.185, confirmed this session)

- **Stop / PostCompact / SessionStart / SubagentStop all exist** and support
  `hookSpecificOutput.additionalContext` for non-blocking context injection.
- **Stop output is `additionalContext` XOR `decision:block` — no hybrid.** "Advise, don't
  block" = the `additionalContext` form: `{"continue":true,"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":"…"}}`.
- **The Stop payload carries NO edited-files list** — only `transcript_path`, `cwd`,
  `session_id`. → derive the turn's changes with **`git diff --name-only` / `git status`**
  against `cwd` (deterministic; preferred over brittle transcript parsing).
- **PostCompact** takes a `manual|auto` matcher, **cannot block**, *can* return
  `additionalContext`. Fits re-injecting the subtree `AGENTS.md`.
- Skills are **purely model-dispatched** (no `Skill()` calls in scripts); the
  `description` field is the trigger. `disable-model-invocation: true` = human-only.
  House pattern: `docs/skills/<name>/SKILL.md` (+ `reference.md`/`commands.md`), mirrored to
  `.cursor/skills/` + `.claude/skills/`; bundle has `index.md` + `log.md`, linted by
  `scripts/okf_lint.py` (`docs/skills` is a registered bundle).

## Part A — Sensors / hooks (deterministic, mechanical)

All three obey the existing **HOOK-1/2/3** contracts in `scripts/hooks/AGENTS.md` and
reuse the `pre_bash_guard.py` shared-detection pattern (one pure detection module, imported
by both the Claude entrypoint and any future Cursor entrypoint).

**S1 — ADR-trigger Stop sensor (advise).** `scripts/hooks/stop_adr_check.py`.
On `Stop`: `git diff --name-only` (+ staged) against `cwd`; if any path matches an ADR
seam — `trust/models.py`, a new node in `orchestration/react_loop.py`, a new top-level dir
under `services/`, a `pyproject.toml` dependency change, a new Protocol/abstraction — **and**
no new `docs/adr/NNNN-*.md` appeared this turn, return `additionalContext`:
*"ADR trigger touched (<seam>); per AGENTS.md ADR.1 append docs/adr/NNNN-*.md (+ index/log)
and answer the G-gate in your own words."* Never blocks. Detection logic in a shared,
pure, unit-tested `scripts/hooks/adr_seams.py` (L1) so a pre-commit/Cursor variant reuses
it. Wire under `hooks.Stop` in `.claude/settings.local.json`. **Its own ADR** (new gate) +
a `decisions.md` line.

**S2 — test-weakening sensor (the mechanical G8).** Implement as
`tests/architecture/test_no_test_weakening.py` (preferred over a hook — runs in CI, is a
trusted gate, already covered by `make check`). It shells `git diff` on `tests/**` and fails
on: a removed `def test_*`, a newly-added `@pytest.mark.skip`/`xfail`/`pytest.skip(` without
a tracking-ref justification token, or a net test-count drop. The ratchet move v2-3.1/H4
names. (`AGENTS.md` G8 already references this sensor by name — landing it closes that
forward-reference.) A pre-commit mirror is optional; the arch-test is the source of truth.

**S3 — PostCompact AGENTS.md re-inject.** `scripts/hooks/postcompact_reinject.py`.
On `PostCompact` (matcher `auto` + `manual`): detect the active subtree from recent
transcript/`cwd`, return `additionalContext` with that folder's nested `AGENTS.md` (root as
fallback). Cannot block (HOOK-3 fail-safe: parse error → empty `{}`). Wire under
`hooks.PostCompact`. Mitigates the "nested AGENTS.md don't survive /compact" gotcha.

**Cursor parity:** S1/S3 are Claude-event-specific (Cursor has no Stop/PostCompact today);
keep the *detection modules* tool-agnostic so a Cursor entrypoint is a later add, not a
rebuild. S2 is CI-level → already tool-agnostic.

## Part B — Per-stage skills (auto-detected + human-invocable)

Authored in `docs/skills/<name>/` (canonical OKF), mirrored to `.cursor/skills/` +
`.claude/skills/`. Each `SKILL.md`: a trigger-optimized `description` (the house
"Use this whenever … even when the user only says X" style), a body that names **when to
defer** to a sibling skill (anti-overlap), the stage's initiate→do→gate→advance loop, and a
**harness-instrumentation (today vs [v2-Pn])** section. Reuse existing skills where they
already own a stage — do **not** duplicate.

| Skill | Stage(s) | Notes / reuse |
|---|---|---|
| **sdd-lifecycle** | 0 / index | Thin orchestrator: the 10-stage map + "which skill for which stage" router + the constitution-is-`AGENTS.md` rule. Points at the others. |
| **sdd-brainstorm** | 1 | 6-direction generation (3 conventional + 3 exploratory); hypotheses validated against repo evidence (grep/glob, not memory). Defers exploration to the `explore` subagent (v2-5.1). |
| **sdd-spec** | 2–4 | EARS spec from `_spec_template.md` + clarify pass + cross-artifact analyze + constitution check (`tests/architecture/` + `make check` baseline). The keystone skill. |
| **sdd-replan** | 5 | The deliberate-gap stage: externalize state to the plan doc; route scope-change→spec / reorder→tasks / reprioritize→impl. |
| **sdd-implement** | 6 | Red/green TDD + per-task EARS verification + `eval_capture.record()`; surfaces the S1/S2 sensors. Mostly references existing hooks. |
| **sdd-converge** | 9–10 | `missing/partial/contradicts/unrequested` classification; append-only Phase-N tasks; bounded `max_iterations`; the sign-off checklist (ADR/gates/green). |

**Stages 7 (review) and 8 (test) reuse what exists** — `code-review` + `security-review`
skills + `meta/code_reviewer.py` + the unified-reviewer v3; `make check` +
`tests/architecture/` + `judge_validation`. `sdd-lifecycle` points at them rather than
re-authoring. **Net new skills: ~6**, not 8.

## Critical files

- **Hooks:** `scripts/hooks/adr_seams.py` (new, pure detection), `stop_adr_check.py` (new),
  `postcompact_reinject.py` (new), `tests/architecture/test_no_test_weakening.py` (new),
  `.claude/settings.local.json` (wire Stop + PostCompact), `scripts/hooks/AGENTS.md`
  (add HOOK-4 Stop/advise + HOOK-5 PostCompact contracts).
- **Skills:** `docs/skills/sdd-*/SKILL.md` (+ `reference.md` where deep), mirrors under
  `.cursor/skills/` + `.claude/skills/`, `docs/skills/index.md` + `log.md` updated.
- **Reuse, don't rebuild:** `pre_bash_guard.py` shared-detection pattern, `_spec_template.md`,
  `decisions.md`, `code-review`/`security-review` skills, `meta/judge_validation.py`,
  `components/answer_verifiers.py` (cited by sdd-spec's verifier-checkable criteria).
- **ADRs:** one for the Stop sensor (new gate); `decisions.md` lines for the small calls.

## Build order (reversible, sensors before skills)

1. **S2 test-weakening arch-test** — lowest risk, pure CI, no new event. Land + verify it
   goes red on a synthetic test deletion.
2. **`adr_seams.py` + S1 Stop sensor (advise)** — unit-test the detector L1 first (TDD),
   then wire `hooks.Stop`, then its ADR.
3. **S3 PostCompact re-inject** — wire `hooks.PostCompact`; verify it injects on `/compact`.
4. **sdd-lifecycle index skill** — author first so the others have a home; mirror.
5. **sdd-spec, sdd-brainstorm, sdd-converge, sdd-replan, sdd-implement** — author + mirror +
   index/log; each with a `description` trigger check (does a natural-language prompt
   auto-match?).

## Verification

- **S1:** edit `trust/models.py` with no new `docs/adr/*` → on Stop, the `additionalContext`
  reminder appears; with an ADR present → silent. Detector has L1 unit tests (seam hit/miss).
- **S2:** `pytest tests/architecture/test_no_test_weakening.py` passes clean; deleting a
  `def test_*` or adding a bare `@pytest.mark.skip` → it fails red. In `make check`.
- **S3:** run `/compact` → the active subtree `AGENTS.md` content is re-injected (visible in
  the next turn's context).
- **Skills:** each new `SKILL.md` renders; a representative natural-language prompt
  auto-matches the right skill (e.g. "let's brainstorm approaches for X" → sdd-brainstorm);
  `okf_lint` 0 failures after index/log update; mirrors byte-identical to canonical.
- **Whole:** `make check` green; `tests/architecture/` green; **no live-LLM in any hook/CI**.

## Out of scope (this phase)

- A blocking ADR gate (locked: advise-only).
- A SubagentStop reviewer gate — belongs to unified-reviewer **WI-6** (don't double-build).
- Spec Kit `/speckit.*` wiring — gated behind the 6.1b trial (DEFER).
- Cursor Stop/PostCompact entrypoints — Cursor lacks those events today; keep detectors
  tool-agnostic so it's a later add, not a rebuild.
