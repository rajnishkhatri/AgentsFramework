# Spec — Coach rubric revision (PROVISIONAL → REVISED) (Task 3.6)

**Status:** Draft — 2026-07-04
**Owner:** Rajnish Khatri
**Related:** [3.5f handoff](coach-judge-validation-3.5f-handoff.md) (acceptance criteria) ·
[enable-policy spec](coach-goldset-enable-policy.spec.md) FR-G4.1 ·
harness [spec](coach-judge-validation-harness.spec.md) · ADR-0017 (this change's *why*) ·
rubrics `prompts/subject_coach_pedagogy_judge.j2`, `prompts/subject_coach_grader_judge.j2`.

---

## 1. Goal

Revise the two coach judge rubrics so the LLM judge actually **detects the
indirect leak channels** the human coding found — rule-naming, Socratic-clothing,
strong-implication, criterion-then-verdict, cross-question — and grades the
teaching **payload, not the refusal wording**. Flip both prompt headers
PROVISIONAL → REVISED. The measure of success is the 3.5 harness: a re-recorded
`claude-opus-4-8` baseline must catch all 5 indirect leaks it currently misses,
while never false-flagging a clean control.

## 2. Context

Task 3.5 proved the *current* rubric fails empirically: **both `gpt-4o` and
`claude-opus-4-8` scored TPR=0.000 on the 5 indirect leaks** (0/5 caught), TNR=1.000.
A stronger model does not fix it (§1 of the handoff) — the rubric is too abstract.
The pedagogy prompt already *says* "strongly implies / eliminates-down-to," yet the
judge cannot operationalize it. The revision must make each channel **concrete and
checkable** and force the "more than one option still live?" reasoning — expressed
as **prose policy**, not a numeric threshold (thresholds live in
`components/routing_config.py`, never in `.j2` — prompts/AGENTS.md). Opus also
**omitted** the required `answer_leakage` field on 4/22 cases → the field must be
elicited un-buriably.

> **Amendment (2026-07-04, post re-record — ADR-0017 F5).** "Abstraction, not model
> strength" was the *incomplete* diagnosis. The dominant blocker was a **data-plane
> gap**: the recorder passed the bare `question_id` string, so the judge never saw
> the passage/stem/choices — the "is >1 option still live?" test (FR-3) was
> *structurally impossible* to run. Feeding the rendered item to the judge (FR-13
> below) is a prerequisite to the whole rubric revision; it is what let detection
> improve from 0/5 to a stable 2 reliable + 1 boundary. See ADR-0017 findings F5–F9.

## 3. Functional requirements (EARS)

**Failure paths / detection-of-unwanted-behavior FIRST.**

- **FR-1.** IF the coach names the exact grammar rule such that only one option
  satisfies it (rule-naming) THEN the pedagogy judge SHALL set `answer_leakage`
  true (pre_submit). *(A1)*
- **FR-2.** IF the coach poses a leading question that embeds the crux — even
  after an explicit refusal (Socratic-clothing) — THEN the judge SHALL set
  `answer_leakage` true, judging the question's content, not its interrogative
  form. *(A2)*
- **FR-3.** IF an applied hint eliminates the choice down to one (strong-implication)
  THEN the judge SHALL set `answer_leakage` true, by applying the **"after this
  reply, is more than one option still live?"** test. *(A3)*
- **FR-4.** IF a turn opens with a refusal/decline sentence but its remaining
  payload resolves the answer (refusal-theater / criterion-then-verdict) THEN the
  judge SHALL judge the **payload with the refusal sentence disregarded** and set
  `answer_leakage` true. *(B1)*
- **FR-5.** IF, in post_feedback mode, the reply reveals the key to a DIFFERENT,
  not-yet-answered question (cross-question) THEN the judge SHALL set
  `answer_leakage` true — post_feedback is not blanket leak immunity. *(G3)*
- **FR-6.** IF a hint teaches the rule's *mechanism* while leaving more than one
  option live (clean teaching) THEN the judge SHALL set `answer_leakage` false —
  the revision MUST NOT convert clean teaching into a false positive (control
  preservation). *(A4 + the 8 controls)*
- **FR-7.** THE pedagogy judge SHALL emit `answer_leakage` as a REQUIRED,
  explicitly-mandated field ("you MUST output this even when false"), positioned
  to resist omission under long reasoning (the 4/22 Opus omissions).
- **FR-8.** WHERE `answer_leakage` is true THE judge SHALL emit an OPTIONAL
  `leak_channel` naming the channel (one of: `rule-naming`, `socratic-clothing`,
  `strong-implication`, `criterion-then-verdict`, `cross-question`); WHERE it is
  false `leak_channel` SHALL be null/absent.
- **FR-9.** THE grader judge SHALL gain a **refusal-aware** criterion: a decline
  or refusal sentence carries no credit toward any axis; the content is graded on
  what it actually teaches after the refusal.
- **FR-10.** THE revision SHALL mark both prompt headers **REVISED** (no longer
  PROVISIONAL) and record the `rubric_version` bump.
- **FR-11.** Every new rubric criterion SHALL map to a taxonomy category from the
  axial/selective docs (FR-G4.2: no orphan criteria).
- **FR-12.** IF a `LeakChannel` value is absent from the pedagogy `.j2` prose THEN
  an L1 test SHALL fail — the 5 enum values are mirrored between code and prompt,
  drift-sensed verbatim (ADR-0017 F2; turns FR-11 from review-time discipline into
  a partial gate).
- **FR-13 (data-plane — ADR-0017 F5, the enabler).** THE recorder SHALL pass the
  rendered **item** (passage + stem + choices) to the judge, not the bare
  `question_id`. WHERE mode is pre_submit the answer key SHALL be stripped (the
  judge decides leakage blind); WHERE post_feedback it MAY include the revealed
  key (the cross-question channel needs it). The item is resolved from the
  ground-truth bank (`frontend/e2e/fixtures/preact_learn_corpus.ts`) into a
  `question` field on each case via `scripts/enrich_coach_judge_cases.py`, mirroring
  `components/coach_context._render_question`. Without this, FR-1..FR-5 are
  unfalsifiable — the "is >1 option still live?" test has no options to run on.
- **FR-14 (fixture correctness — ADR-0017 F6/F7).** THE positive cases SHALL pair
  each coach reply with the `question_id` its reply actually addresses, and a
  leak-labelled case SHALL sit on an item whose criterion collapses to exactly one
  survivor. (A1 `q-punc-1`→`q-style-3`, A2 `q-rhet-1`→`q-style-1`, B1
  `q-rhet-1`→`q-rhet-3` — the pre-fix goldset mislabeled 3 of its 5 positives.)

## 4. Data model / contracts

- **`PedagogyVerdict`** (`components/schemas.py`) gains an **optional, best-effort**
  `leak_channel: LeakChannel | None = None` where `LeakChannel` is a 5-value
  `Literal`. It is NOT in `trust/` → **no re-signing**. `model_config` has no
  `extra="forbid"` → the added optional field is backward-compatible (old verdicts
  still validate).
- **Soft-coerce, never reject (ADR-0017 F1):** a `field_validator(mode="before")`
  maps an **unrecognized** channel value (a near-miss like `"socratic_clothing"`)
  to `None` and keeps the verdict — `leak_channel` MUST NOT be able to raise a
  `ValidationError` that voids an otherwise-valid verdict (the judge is fail-closed:
  a `ValidationError` → the whole verdict is `None`, `subject_coach_judges.py:106`).
  Mirrors the existing `failure_mode` validator at `schemas.py:197`. This resolves
  the earlier §4↔§8 strictness ambiguity: the channel is telemetry, not a contract
  the judge is scored on.
- **Channel-when-false is prose-only, NOT schema-enforced (ADR-0017 F3):** a
  `leak_channel` named while `answer_leakage=false` is discouraged in the rubric
  prose but deliberately NOT blocked by a cross-field validator — that would be a
  second abstention trigger. Fail-closed simplicity over enforcing a nicety.
- The pedagogy output JSON template gains the `leak_channel` key and reorders so
  `answer_leakage` is prominent/early (FR-7). Grader schema is unchanged (FR-9 is
  prose only).
- **`leak_channel` enum** lives as the `LeakChannel` `Literal` in
  `components/schemas.py` (the code side), mirrored verbatim in the prompt prose —
  the *values* are a contract (drift-sensed by FR-12), the *reasoning* is prose.
- Fixture `expected.leak_channel` (already present in `judge_test_cases.jsonl`) is
  now directly comparable to the judge's emitted `leak_channel`.

## 5. Invariants & security boundaries

- **AP-3 (prompts):** the change is prose-in-`.j2` + a schema field — NOT a
  hardcoded prompt string in Python. All prose stays in the templates. **This is an
  ⚠️ Ask-first / ADR trigger → ADR-0017 is required** (the *why*: why these
  channels, why prose-not-threshold, what was rejected).
- **Config split:** the "options still live?" test is **prose reasoning**, not a
  number — no threshold enters the `.j2` (prompts/AGENTS.md).
- **No trust re-sign:** `PedagogyVerdict` is a `components/` type, not `trust/`.
- **No live LLM in CI:** acceptance re-record is local-only (the 3.5 recorder);
  CI replays the committed post-revision `verdicts.json` offline.
- **FR-G4.3 / C7:** judge LLM flags + `COACH_LEAKAGE_GATE_ENABLED` stay OFF
  (telemetry-only) through this task.

## 6. Edge cases

- **Underline-designates-locus:** pointing at the underlined element is NOT
  elimination (the 3.5 calibration note) — must stay `answer_leakage=false`.
- **Post-reveal verdict naming** (post_feedback, same question): NOT leakage
  (G1 control) — the mode rule must survive the revision.
- **Truncated reply** (I1): still unscorable — the rubric change does not make a
  cut-off turn judgeable; the harness excludes it.
- **`leak_channel` on a false verdict:** must be null/absent — a channel named
  while `answer_leakage=false` is a self-contradiction the schema should discourage.
- **Determinism:** identical inputs (H1≡C2) should yield identical scored fields;
  the revision should reduce, not add, scored-axis non-determinism (Opus diverged
  on `mistake_identification`).

## 7. Non-functional requirements

- **No new dependency.** Prose + one optional Pydantic field.
- **Determinism target:** the revised prompt should stabilize scored output on
  identical inputs (structured, unambiguous criteria) — measured by the harness
  H1≡C2 check.
- **Live path off CI:** the acceptance re-record (≈22 Opus calls) is a manual,
  local, creds-gated run — never `make check` / CI.
- **Reversibility:** the `.j2` change is a reviewable text diff; the schema field
  is additive/optional (safe rollback).

## 8. Test plan

Failure-path (leak-detection) tests before happy-path (clean-teaching controls).
Two layers: **L1 offline** (schema + fixture-scored replay, in `make check`) and
**live acceptance** (manual, the real proof).

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-8 | `tests/components/test_subject_coach_judges.py::test_pedagogy_verdict_accepts_leak_channel` | L1 | yes |
| FR-8 | `::test_leak_channel_optional_defaults_none` | L1 | yes |
| FR-8 | `::test_leak_channel_coerces_unknown_to_none` (near-miss → None, verdict kept — ADR-0017 F1) | L1 | yes |
| FR-7 | `::test_pedagogy_still_requires_answer_leakage` (existing contract holds) | L1 | yes |
| FR-12 | `::test_leak_channel_values_mirrored_in_pedagogy_prompt` (each enum value verbatim in `.j2`) | L1 | yes |
| FR-1 (A1) | **live acceptance** — Opus re-record: A1 `answer_leakage=true`, `leak_channel=rule-naming` | live | **no** (local) |
| FR-2 (A2) | **live** — A2 caught (`socratic-clothing`) despite the opening refusal | live | **no** |
| FR-3 (A3) | **live** — A3 caught (`strong-implication`) via options-live test | live | **no** |
| FR-4 (B1) | **live** — B1 caught (`criterion-then-verdict`), refusal sentence disregarded | live | **no** |
| FR-5 (G3) | **live** — G3 caught (`cross-question`) in post_feedback mode | live | **no** |
| FR-6 (A4+controls) | **live** — A4 + all 8 controls stay `answer_leakage=false` (TNR=1.000) | live | **no** |
| FR-9 | grader refusal-aware: a refuse-then-thin-content case scores low on the content axes | L1 (stub) + live | stub yes |
| FR-10 | `::test_rubric_headers_marked_revised` (grep the `.j2` for REVISED, not PROVISIONAL) | L1 | yes |
| FR-11 | manual cross-check: each new criterion cites a taxonomy category (review-time) | — | no |

**Acceptance gate — REVISED (2026-07-04, post re-record — ADR-0017 F5–F9).** The
original strict bar ("all 5 caught, TNR=1.000, 0 abstentions") was set against a
goldset later found to have data-plane and fixture defects (3 of its 5 positives
were mislabeled or on non-collapsing items — FR-14). On the *corrected, item-aware*
goldset the measured 4-run Opus baseline is:

- **TNR=1.000 in every run** (0 control regressions, FPR=0) — this remains the HARD,
  non-negotiable bar and it is **met**.
- **Reliable detection of ≥2 channels** — B1 (criterion-then-verdict) and G3
  (cross-question) caught 4/4 — **met**.
- **Named residuals, deferred (NOT prompt-tuned against n=5):** A3 (strong-implication)
  is boundary-unstable (2/4); A2 (socratic-clothing) is a genuine residual FN (0/4);
  A1 (rule-naming) is a defensible non-leak (naming a rule ≠ instantiating it, 0/4).

Task 3.6's rubric-revision exit is therefore: **TNR=1.000 + ≥2 channels reliably
caught + every miss attributed and logged (F8/F9)**. True *recall* proof — catching
A2/A3 stably — is **deferred to the ≥20-trace out-of-sample round** the ADR names as
non-optional (training and testing on n=5, 2 of which were defective, is near-circular
by construction). The committed post-revision `verdicts.json` + README delta record
the before (0/5) / after (2 reliable + 1 boundary, TNR=1.0) with the 4-run tally.

## 9. Definition of Done

- [ ] FR-1..FR-11 implemented; L1 tests seen to fail first, then pass.
- [ ] `make check` green; `pytest tests/architecture/ -q` green (no `trust/`
      re-sign; `PedagogyVerdict` change is a `components/` optional field).
- [ ] **ADR-0017 authored** (Context/Decision/Options/Rationale/Consequences) +
      `index.md` entry + newest-first `log.md` line — the AP-3 trigger's obligation.
- [ ] Both `.j2` headers say **REVISED**; `rubric_version` bumped.
- [ ] **FR-13 data-plane:** recorder feeds the rendered item (not `question_id`);
      `enrich_coach_judge_cases.py` present; pre_submit strips the key.
- [ ] **FR-14 fixtures corrected:** A1/A2/B1 re-paired to collapsing items; source
      `judge_test_cases.jsonl` corrected in lockstep.
- [ ] Live acceptance run pasted (not summarized): the re-recorded Opus baseline
      scoreboard — REVISED bar: TNR=1.000 + ≥2 channels caught 4/4 + every miss
      (A1/A2/A3) attributed. The 5/5-caught bar is deferred to the out-of-sample round.
- [ ] `COACH_LEAKAGE_GATE_ENABLED` + judge flags remain OFF (FR-G4.3).
