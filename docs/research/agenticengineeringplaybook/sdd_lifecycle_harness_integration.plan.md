# SDD Lifecycle → Sensors/Hooks + Skills — Integration Plan

> **Status:** EXECUTED 2026-07-02 (uncommitted). **Part A:** S1 SHIPPED-AS
> `scripts/hooks/stop_adr_reminder.py` + `tests/architecture/test_adr_ratchet.py`
> (superseded this plan's `adr_seams.py`/`stop_adr_check.py` — never built); S2 DONE
> (`tests/architecture/test_no_test_weakening.py`); **S3 DEFECT FIXED 2026-07-02** —
> the re-inject was re-homed from the context-injection-incapable `PostCompact` event onto
> **`SessionStart` gated on `source == "compact"`**. `postcompact_reinject.py` →
> `sessionstart_reinject.py` (+ `tests/scripts/test_sessionstart_reinject.py`, now with a
> non-compact-source silent-no-op test); `.claude/settings.local.json` rewired
> `PostCompact` → `SessionStart` (matcher `compact`); HOOK-4 in `scripts/hooks/AGENTS.md`
> updated. Official CC docs confirm: `SessionStart` accepts `additionalContext` and has a
> `compact` source that fires after auto/manual compaction; `PostCompact` has *no decision
> control* (side-effects only). This **corrects the original verified-fact claim** at
> "PostCompact … can return additionalContext" (false on CC 2.1.185 — a `PostCompact`
> payload is rejected `(root): Invalid input`). **Part B DONE:** 6 `sdd-*` skills authored + `scripts/sync_skills.py` +
> `make skills-sync` + `tests/architecture/test_skills_mirror_parity.py`; `.claude/skills`
> un-gitignored. `make check` green (4540 passed). Skill-distribution decision (2026-07-02):
> track `.claude/skills` in git + `make skills-sync` + parity arch-test. Authored 2026-06-28.
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
- **PostCompact** takes a `manual|auto` matcher and **cannot block**. ⚠️ **CORRECTION
  (2026-07-02):** this section originally claimed PostCompact *can* return
  `additionalContext` — **that is false on CC 2.1.185.** The live hook-output schema has
  **no PostCompact case**; `additionalContext` is only accepted for `UserPromptSubmit`,
  `PostToolUse`, `PostToolBatch`, `Stop`, and `SubagentStop`. A PostCompact hook that emits
  `{"hookSpecificOutput":{"hookEventName":"PostCompact","additionalContext":…}}` is rejected
  with `Hook JSON output validation failed — (root): Invalid input`, so the re-injection
  never reaches the model. The S3 design below inherited this wrong assumption; see "S3
  defect" for the fix options.
- Skills are **purely model-dispatched** (no `Skill()` calls in scripts); the
  `description` field is the trigger. `disable-model-invocation: true` = human-only.
  House pattern: `docs/skills/<name>/SKILL.md` (+ `reference.md`/`commands.md`), mirrored to
  `.cursor/skills/` + `.claude/skills/`; bundle has `index.md` + `log.md`, linted by
  `scripts/okf_lint.py` (`docs/skills` is a registered bundle).

## Part A — Sensors / hooks (deterministic, mechanical)

All three obey the existing **HOOK-1/2/3** contracts in `scripts/hooks/AGENTS.md` and
reuse the `pre_bash_guard.py` shared-detection pattern (one pure detection module, imported
by both the Claude entrypoint and any future Cursor entrypoint).

**S1 — ADR-trigger Stop sensor (advise). ✅ SUPERSEDED — SHIPPED in a different shape.**
What landed (before this plan executed): `scripts/hooks/stop_adr_reminder.py` wired under
`hooks.Stop`, sharing the pure detector `utils.code_analysis.detect_adr1_missing` with the
CI-enforced `tests/architecture/test_adr_ratchet.py` (waiver token `ADR-OK` in a range
commit message). That is *better* than this plan's design — one detector feeds both the
advisory hook and the hard CI gate, so they cannot drift. The `adr_seams.py` +
`stop_adr_check.py` files proposed here **must not be built**: they would be a second,
drifting implementation of the same seam detection. See `docs/adr/decisions.md` (the
arch-test-not-Stop-hook entry) for the recorded rationale.

**S2 — test-weakening sensor (the mechanical G8). ✅ DONE** — landed as designed
(waiver tokens: `G8-OK`, `flaky-tracked:`, `env-gated:`, `live_llm`). Original design
kept for the record: implement as
`tests/architecture/test_no_test_weakening.py` (preferred over a hook — runs in CI, is a
trusted gate, already covered by `make check`). It shells `git diff` on `tests/**` and fails
on: a removed `def test_*`, a newly-added `@pytest.mark.skip`/`xfail`/`pytest.skip(` without
a tracking-ref justification token, or a net test-count drop. The ratchet move v2-3.1/H4
names. (`AGENTS.md` G8 already references this sensor by name — landing it closes that
forward-reference.) A pre-commit mirror is optional; the arch-test is the source of truth.

**S3 — PostCompact AGENTS.md re-inject. ⚠️ BUILT, but the delivery mechanism is rejected
by the harness (open defect).** `scripts/hooks/postcompact_reinject.py` ships with 8 tests
(`tests/scripts/test_postcompact_reinject.py`, red→green): it detects the active subtree(s)
from `git diff --name-only HEAD` + `git ls-files --others --exclude-standard` (changed **and**
untracked files), maps each to the deepest enclosing nested `AGENTS.md`, and builds a
≤10 KB `additionalContext` block (over budget → degrade to a "re-read these paths" list).
It is the repo's first `hookSpecificOutput.additionalContext` hook; contract = HOOK-4 in
`scripts/hooks/AGENTS.md`; wired under `hooks.PostCompact` (matcher `manual|auto`) in
`.claude/settings.local.json`. HOOK-3 fail-safe holds (malformed stdin → silent exit 0).

**S3 defect (found 2026-07-02 by a live `/compact`) — FIXED same day via option (i).** The
pure logic was correct, but the **output shape was invalid**: Claude Code 2.1.185 has no
`PostCompact` case in its hook-output schema, so the emitted
`{"hookSpecificOutput":{"hookEventName":"PostCompact","additionalContext":…}}` failed
validation (`(root): Invalid input`) and the re-injection was silently dropped. **Fix
applied:** re-homed to a **`SessionStart`** hook gated on `source == "compact"` — the
official CC docs confirm `SessionStart` both accepts `additionalContext` *and* exposes a
`compact` source that fires after auto/manual compaction, so this reproduces the
post-compaction timing without injecting on every startup/resume/clear. `postcompact_reinject.py`
→ `sessionstart_reinject.py` (`render_output` now emits `hookEventName: "SessionStart"`;
`main` returns early unless `source == "compact"`); the 8 pure detection/budget tests
transferred unchanged and a `test_non_compact_source_is_silent_noop` was added.
The rejected options — (ii) `UserPromptSubmit` (fires every turn), (iii) a bare
PostCompact `additionalContext` — were both dominated by the `compact`-source gate on
`SessionStart`.

**Cursor parity:** S1/S3 are Claude-event-specific (Cursor has no Stop/PostCompact today);
keep the *detection modules* tool-agnostic so a Cursor entrypoint is a later add, not a
rebuild. S2 is CI-level → already tool-agnostic.

## Part B — Per-stage skills (auto-detected + human-invocable)

Authored in `docs/skills/<name>/` (canonical OKF), mirrored to `.cursor/skills/` +
`.claude/skills/`. **Mirror mechanics revised 2026-07-02:** the assumed convention did not
exist — `.claude/skills` was gitignored, no sync tooling, and the mirrors had already
drifted (`deploy-gcp` mirror-only; `agentsframework-eval-probe/SKILL.md` differs between
canonical and `.cursor`). Since auto-trigger requires skills in a discovery path, mirroring
is load-bearing, not cosmetic. Decision: un-ignore `.claude/skills/`, add
`scripts/sync_skills.py` + `make skills-sync`, and a parity arch-test
(`tests/architecture/test_skills_mirror_parity.py`) so drift fails CI; repair the existing
drift canonical-wins (diff first, fold unique mirror content back). Each `SKILL.md`: a
trigger-optimized `description` (the house
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

- **Hooks:** `sessionstart_reinject.py` (new; was `postcompact_reinject.py` until the S3
  re-home), `.claude/settings.local.json` (wire `SessionStart` matcher `compact`),
  `scripts/hooks/AGENTS.md` (the HOOK-4 advisory-`additionalContext` contract + the
  PostCompact-can't-inject note). ~~`adr_seams.py`/`stop_adr_check.py`~~
  superseded by shipped `stop_adr_reminder.py`; ~~`test_no_test_weakening.py`~~ shipped.
- **Skills:** `docs/skills/sdd-*/SKILL.md` (+ `reference.md` where deep), mirrors under
  `.cursor/skills/` + `.claude/skills/`, `docs/skills/index.md` + `log.md` updated;
  `scripts/sync_skills.py` (new) + `Makefile` `skills-sync` + `.gitignore` negation +
  `tests/architecture/test_skills_mirror_parity.py` (new).
- **Reuse, don't rebuild:** `pre_bash_guard.py` shared-detection pattern, `_spec_template.md`,
  `decisions.md`, `code-review`/`security-review` skills, `meta/judge_validation.py`,
  `components/answer_verifiers.py` (cited by sdd-spec's verifier-checkable criteria).
- **ADRs:** one for the Stop sensor (new gate); `decisions.md` lines for the small calls.

## Build order (EXECUTED 2026-07-02 — all steps done except the S3 delivery-contract fix)

1. ~~S2 test-weakening arch-test~~ ✅ shipped (`test_no_test_weakening.py`).
2. ~~S1 ADR Stop sensor~~ ✅ superseded/shipped (`stop_adr_reminder.py` + `test_adr_ratchet.py`).
3. ~~S3 PostCompact re-inject~~ ✅ **built + delivery-contract FIXED** — re-homed to
   `sessionstart_reinject.py` on `SessionStart` (matcher/gate `source == "compact"`), 10
   tests, HOOK-4 contract, wired. The original `PostCompact` shape was schema-rejected (see
   "S3 defect"); logic transferred unchanged. CLOSED.
4. ~~Skills-sync tooling~~ ✅ done — `scripts/sync_skills.py` + `make skills-sync` +
   `.gitignore` negation (`.claude/*` + `!.claude/skills/`) + `test_skills_mirror_parity.py`
   (red→green→red-probe→green). Ripple fixes: ruff `.claude/**` per-file-ignores + hidden-dir
   skips in `cite_lint.py` / `test_deep_agent_cleanup.py` / `test_middleware_layer.py` (stale
   `.claude/worktrees/*` checkouts trip repo-root `rglob`).
5. ~~sdd-lifecycle index skill~~ ✅ authored + synced.
6. ~~sdd-spec, sdd-brainstorm, sdd-converge, sdd-replan, sdd-implement~~ ✅ authored + synced
   + index/log; the harness live-loaded all six mid-session once mirrored (auto-trigger
   proven). `make check` green: **4540 passed, 52 skipped**; okf_lint 0 failures.

## Follow-ups (not this plan)

- ~~**S3 delivery-contract fix**~~ ✅ DONE 2026-07-02 — re-homed to `SessionStart`
  (`source == "compact"` gate); proven pure helpers + tests transferred.
- **Adopt `deploy-gcp` into canonical `docs/skills/`** — it is mirror-only today (on the
  parity test's exempt list with a TODO).
- **Relocate the stray `docs/skills/SKILL.md`** (idea-to-design skill at bundle root,
  overlaps sdd-brainstorm/sdd-spec territory).

## Verification

- **S1:** edit `trust/models.py` with no new `docs/adr/*` → on Stop, the `additionalContext`
  reminder appears; with an ADR present → silent. Detector has L1 unit tests (seam hit/miss).
- **S2:** `pytest tests/architecture/test_no_test_weakening.py` passes clean; deleting a
  `def test_*` or adding a bare `@pytest.mark.skip` → it fails red. In `make check`.
- **S3:** unit level — 10 tests green (malformed-stdin no-op, **non-compact-source
  silent-no-op**, `source == "compact"` emits a well-formed `SessionStart` payload, subtree
  mapping deepest-wins, budget degrade-to-path-list, output shape). Manual check:
  `echo '{"source":"compact"}' | .venv/bin/python scripts/hooks/sessionstart_reinject.py`
  emits an 8 KB `hookEventName: "SessionStart"` payload; `{"source":"startup"}` is silent.
  Live level (next `/compact`) should now inject rather than return `(root): Invalid input`.
  The original PostCompact shape returned that validation error 2026-07-02 — the honest
  result that drove the re-home.
- **Skills:** each new `SKILL.md` renders; a representative natural-language prompt
  auto-matches the right skill (e.g. "let's brainstorm approaches for X" → sdd-brainstorm);
  `okf_lint` 0 failures after index/log update; mirrors byte-identical to canonical.
- **Whole:** `make check` green; `tests/architecture/` green; **no live-LLM in any hook/CI**.

## Out of scope (this phase)

- A blocking ADR gate (locked: advise-only).
- A SubagentStop reviewer gate — **update 2026-07-02: this shipped anyway** as
  `scripts/hooks/subagent_stop_review.py` (wired). Still out of scope *here* — don't touch it.
- Spec Kit `/speckit.*` wiring — gated behind the 6.1b trial (DEFER).
- Cursor Stop/PostCompact entrypoints — Cursor lacks those events today; keep detectors
  tool-agnostic so it's a later add, not a rebuild.
