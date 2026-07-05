# Plan — Coach rubric revision (Task 3.6)

**Spec:** [coach-rubric-revision.spec.md](coach-rubric-revision.spec.md) ·
**ADR:** ADR-0017 (required — AP-3 + schema field) ·
**Acceptance:** [3.5f handoff](coach-judge-validation-3.5f-handoff.md).

## 1. Approach

The 3.5 baseline proved the failure is **abstraction, not model strength**. The
fix is to make the pedagogy rubric's leak section *operational*: name each
indirect channel with a concrete tell, and force the **"is more than one option
still live?"** reasoning as the decisive test — in prose (thresholds forbidden in
`.j2`). Add an optional `leak_channel` so the judge names what it caught (directly
comparable to the fixture's `expected.leak_channel`). Make `answer_leakage`
un-buriable. Add one refusal-aware criterion to the grader. Flip both headers to
REVISED. Prove it by re-recording the same Opus 4.8 baseline.

> **Amendment (2026-07-04 — ADR-0017 F5).** The re-record revealed the *primary*
> blocker was a **data-plane gap**, not abstraction: the judge was fed the bare
> `question_id`, never the item's options, so the decisive test could not run.
> Stage 0 below (feed the item + fix the mislabeled fixtures) is a prerequisite to
> Stage B making any measurable difference. The "abstraction" fix is real but was
> masking this.

## 2. File-level touchpoints

| File | Change | Layer / gate |
|---|---|---|
| `prompts/subject_coach_pedagogy_judge.j2` | Rewrite the leak section: 4 named channels + options-live test + payload-over-refusal rule + cross-question; make `answer_leakage` explicitly required + add `leak_channel` to output JSON; header → REVISED. | prompts/ — AP-3 / **ADR trigger** |
| `prompts/subject_coach_grader_judge.j2` | Add refusal-aware criterion (refusal sentence carries no axis credit); header → REVISED. | prompts/ — AP-3 |
| `components/schemas.py` | `PedagogyVerdict` gains optional `leak_channel: LeakChannel \| None = None`; add `LeakChannel = Literal[...]` (5 values) + a `field_validator(mode="before")` that **soft-coerces unknown → None** (ADR-0017 F1; never raises). | components/ — **schema field (ADR line)**; NOT trust → no re-sign |
| `tests/components/test_subject_coach_judges.py` | L1: `leak_channel` accepted/optional/**coerces-unknown-to-None** (ADR-0017 F1); `answer_leakage` still required; enum values mirrored in `.j2` (FR-12); headers REVISED. | tests/components/ |
| `docs/adr/0017-*.md` + `index.md` + `log.md` | The *why*: channels chosen, prose-not-threshold, rejected alternatives. | ADR bundle |
| `tests/fixtures/coach_judge_validation/verdicts.json` + README | Post-revision re-record (Opus) + before/after scoreboard. | fixture (live-recorded) |
| `docs/plan/coach-goldset-enable-policy.spec.md` | Mark FR-G4.1 satisfied once acceptance passes; bump `rubric_version`. | docs |

## 3. ADR / gate triggers (enumerated — two fire)

1. **AP-3 / ⚠️ Ask-first — prompt policy change.** Both `.j2` rewrites. → **ADR-0017**.
2. **Schema change — `PedagogyVerdict` gains a field.** A `components/` type, not
   `trust/` → **no re-signing**, but it is a durable contract change → folded into
   ADR-0017 (one ADR covers the coupled rubric+schema decision).

Triggers that do **not** fire: no new dependency, no new service, no new graph
node, no trust-kernel type. The `test_adr_ratchet.py` gate is satisfied by the new
`docs/adr/0017-*.md` (the `prompts/` + schema diff is the trigger path).

## 4. Build order (evidence-gated)

**Stage 0 — data plane (ADR-0017 F5–F7; discovered post-hoc, ordered first).**
0a. `scripts/enrich_coach_judge_cases.py`: resolve each `question_id` against the TS
    item bank, write a rendered `question` block into `cases.jsonl` (pre_submit
    strips the key, post_feedback keeps it — mirrors `coach_context._render_question`).
0b. Recorder passes `case["question"]` (the item) to the judge, not `question_id`.
0c. Fix the 3 mislabeled positives (FR-14): A1→`q-style-3`, A2→`q-style-1`,
    B1→`q-rhet-3` (+ B1 coach reply re-quoted to the new stem). Correct the source
    `docs/evals/eng-coach/judge_test_cases.jsonl` in lockstep. **Without Stage 0,
    Stages B/D measure noise.**

**Stage A — schema + L1 (offline, TDD).**
1. Red: `leak_channel` tests (accept/optional/reject-unknown) + `answer_leakage`
   still-required + headers-REVISED. Watch fail.
2. Green: add `LeakChannel` Literal + optional field to `PedagogyVerdict`;
   `make check` + `tests/architecture/` stay green.

**Stage B — rubric prose (the substance).**
3. Rewrite the pedagogy leak section (4 channels, options-live test,
   payload-over-refusal, cross-question, required `answer_leakage`, `leak_channel`
   output). Rewrite grader refusal-aware criterion. Flip headers → REVISED.
4. Each criterion traced to a taxonomy category (FR-11) in the ADR.

**Stage C — ADR-0017.**
5. Author ADR (Context/Decision/Options/Rationale/Consequences) + index + log.
   The rejected alternatives are the payload: (a) "just use a bigger model"
   (falsified by the 0/5 Opus baseline), (b) numeric leak-threshold in the prompt
   (violates config split), (c) `leak_channel` as required not optional (would
   break backward-compat / old verdicts).

**Stage D — live acceptance (manual, local).**
6. Re-record: `MODEL_PROFILE_SET=anthropic COACH_JUDGE_TIER=reasoning
   scripts/record_coach_judge_validation.py`. Score with `meta.coach_judge_validation`.
7. **Gate (REVISED — spec §8 / ADR-0017 F5–F9):** on the *corrected item-aware*
   goldset, require **TNR=1.000** (hard) + **≥2 channels caught 4/4** (B1, G3 —
   met) + every miss attributed (A1 defensible non-leak; A2 residual FN; A3 boundary
   2/4). The original 5/5 bar is **deferred to the ≥20-trace out-of-sample round**
   (n=5 with 2 defective positives is near-circular — do NOT prose-tune to it).
   Commit the winning `verdicts.json` + README delta with the 4-run tally.

## 5. Risk + iteration

- **The prose may not catch all 5 on the first pass** (n=5, subtle channels). The
  loop is Stage B ↔ Stage D — revise wording, re-record, re-score. This is
  *expected*; the strict bar is the exit condition, not a first-try assumption.
- **The goldset itself was defective (ADR-0017 F6/F7 — materialized, not hypothetical).**
  3 of the 5 positives were mislabeled or on non-collapsing items, invisible until
  the judge could see the item (Stage 0). Lesson: **fix the fixtures before iterating
  the prose** — otherwise Stage B chases noise. The corrected goldset is the baseline;
  A2/A3 recall is deferred to out-of-sample (do not overfit prose to n=5).
- **Over-correction risk:** a rule that catches A2/A3 could start flagging the
  clean control A4. FR-6 + the 8 controls are the guardrail — TNR=1.000 is
  non-negotiable; a control regression means the wording is too broad.
- **Determinism:** watch H1≡C2 on the re-record; if the revised prompt still
  diverges on a scored axis, tighten that axis's criterion.

## 6. Out of scope

- The hard leak-rate **CI gate** (waits for ≥20 overt-demand traces — next round).
- New corpus collection.
- Enabling the judge flags / `COACH_LEAKAGE_GATE_ENABLED` (stays OFF — FR-G4.3).
