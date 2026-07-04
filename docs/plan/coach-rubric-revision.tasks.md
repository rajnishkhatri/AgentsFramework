# Tasks — Coach rubric revision (Task 3.6)

**Spec:** [coach-rubric-revision.spec.md](coach-rubric-revision.spec.md) ·
**Plan:** [coach-rubric-revision.plan.md](coach-rubric-revision.plan.md)

Atomic, file-level, dependency-marked, 1:1 to the spec FRs. Failure-path
(leak-detection) tasks precede happy-path (control) tasks (TAP-4). Red/green TDD
on the schema; the rubric prose is proven by the live acceptance re-record.

Legend: **[dep: …]** must precede · **‖** parallel.

---

## 3.6-0 — Data plane: feed the item + fix mislabeled fixtures [no dep] — Stage 0 (ADR-0017 F5–F7)
Discovered post-hoc: the judge was fed the bare `question_id`, never the item's
options, so FR-1..FR-5 were unfalsifiable. **Prerequisite to every later stage.**
- **3.6-0-1 (FR-13)** Add `scripts/enrich_coach_judge_cases.py`: resolve `question_id`
  → rendered `question` block from `frontend/e2e/fixtures/preact_learn_corpus.ts`
  (pre_submit strips the answer key; post_feedback keeps it — mirrors
  `coach_context._render_question`). Write `question` into every `cases.jsonl` row.
- **3.6-0-2 (FR-13)** Recorder passes `case["question"]` (item) to the judge, not
  `question_id` (`scripts/record_coach_judge_validation.py`).
- **3.6-0-3 (FR-14)** Fix the 3 mislabeled positives: A1 `q-punc-1`→`q-style-3`,
  A2 `q-rhet-1`→`q-style-1`, B1 `q-rhet-1`→`q-rhet-3` (+ re-quote B1's coach reply
  to the new stem). Correct the source `docs/evals/eng-coach/judge_test_cases.jsonl`
  in lockstep.
- **Pass:** enriched cases render; pre_submit shows no answer key; each positive's
  item collapses to one survivor under its coach's criterion; the item-aware
  re-record no longer flags item↔reply incoherence on A1/A2.
- **Fail if:** the answer key leaks into a pre_submit `question` block; a positive
  sits on a non-collapsing item; the source fixture drifts from `cases.jsonl`.

## 3.6a — `leak_channel` schema field [dep: 3.6-0] — Stage A
Add to `components/schemas.py`: `LeakChannel = Literal["rule-naming",
"socratic-clothing", "strong-implication", "criterion-then-verdict",
"cross-question"]`, `PedagogyVerdict.leak_channel: LeakChannel | None = None`, and
a `field_validator("leak_channel", mode="before")` that **soft-coerces an
unrecognized value to `None`** (mirrors `failure_mode` at `schemas.py:197`).
- **3.6a-1 (FR-8)** Red→green: `test_leak_channel_optional_defaults_none` (a
  verdict without the field validates, `leak_channel is None`).
- **3.6a-2 (FR-8)** Red→green: `test_pedagogy_verdict_accepts_leak_channel`
  (a valid channel value round-trips).
- **3.6a-3 (FR-8, ADR-0017 F1 — the substantive fix)** Red→green:
  `test_leak_channel_coerces_unknown_to_none` — a near-miss (`"socratic_clothing"`,
  `"rule naming"`) coerces to `None` and **the verdict is KEPT**, never a
  `ValidationError`. Failure-mode-first: this is the case that would otherwise void
  a correct `answer_leakage=true` on the 5/5 run.
- **3.6a-4 (FR-7)** `test_pedagogy_still_requires_answer_leakage` — the existing
  required-field contract is UNCHANGED (guard against accidental relaxation).
- **3.6a-5 (FR-12, ADR-0017 F2)** `test_leak_channel_values_mirrored_in_pedagogy_prompt`
  — each of the 5 `LeakChannel` values appears verbatim in the pedagogy `.j2`
  (code↔prose drift sensor). *(Runs after 3.6b writes the prose; ordered here as
  the schema's mirror-partner.)*
- **Pass:** all 5 L1 tests green; `pytest tests/architecture/ -q` green (no
  `trust/` touch → no re-sign; `components/` optional field is backward-compatible).
- **Fail if:** `leak_channel` made required, or a bad value RAISES instead of
  coercing to `None` (ADR-0017 F1); any `trust/` import introduced.

## 3.6b — Pedagogy rubric rewrite [dep: 3.6a] — Stage B (the substance)
Rewrite the leak section of `prompts/subject_coach_pedagogy_judge.j2`:
- **FR-1** rule-naming tell; **FR-2** Socratic-clothing (judge question content,
  not form, even after a refusal); **FR-3** strong-implication via the
  **"more than one option still live?"** test; **FR-4** payload-over-refusal
  (disregard the refusal sentence, judge the rest); **FR-5** cross-question
  (post_feedback ≠ blanket immunity); **FR-6** clean-teaching stays false.
- **FR-7** `answer_leakage` explicitly mandated ("output even when false"),
  positioned early; **FR-8** `leak_channel` added to the output JSON.
- **FR-10** header → REVISED.
- **Prose only** — no numeric threshold (config split).
- **Pass:** `test_rubric_headers_marked_revised` (pedagogy) green; prompt renders
  via `PromptService`; the output JSON block includes `leak_channel`.
- **Fail if:** a threshold number appears in the `.j2`; a prompt string is
  hardcoded in Python instead.

## 3.6c — Grader rubric refusal-aware criterion [dep: none] ‖ 3.6b — Stage B
`prompts/subject_coach_grader_judge.j2`: add the refusal-aware rule (a
decline/refusal sentence carries no axis credit; grade the content after it).
Header → REVISED.
- **Pass (FR-9):** `test_grader_headers_marked_revised` green; a stub grader test
  where refuse-then-thin-content scores low on the content axes.
- **Fail if:** the refusal rule leaks a threshold number into the prompt.

## 3.6d — ADR-0017 [dep: 3.6b, 3.6c] — Stage C
Copy `docs/adr/0000-template.md` → `docs/adr/0017-subject-coach-rubric-revision.md`.
Context (0/5 Opus baseline), Decision (4 channels + options-live + payload-over-
refusal + optional `leak_channel`), Options/Rejected ((a) bigger model — falsified;
(b) prompt threshold — config-split violation; (c) required `leak_channel` —
backward-compat break), Consequences. Add `index.md` entry + newest-first
`log.md` line. FR-11: each criterion cites a taxonomy category.
- **Pass:** `pytest tests/architecture/test_adr_ratchet.py -q` green (the
  `prompts/` + schema trigger path now has its ADR).
- **Fail if:** no `index.md`/`log.md` entry (OKF invalid); or the ADR omits the
  rejected alternatives (the intent-debt payload).

## 3.6e — Live acceptance re-record + score [dep: 3.6-0, 3.6b, 3.6c, 3.6a] — Stage D — HUMAN/LOCAL
Re-record the baseline with the revised rubric ON THE CORRECTED, ITEM-AWARE goldset:
`MODEL_PROFILE_SET=anthropic COACH_JUDGE_TIER=reasoning
.venv/bin/python -m scripts.record_coach_judge_validation --cases ... --out ...`.
Score with `meta.coach_judge_validation`.
- **Pass (REVISED gate — spec §8 / ADR-0017 F5–F9):** **TNR=1.000** on the 8
  controls (hard, non-negotiable) + **≥2 channels caught 4/4** (B1, G3) + every miss
  attributed (A1 defensible non-leak; A2 residual FN; A3 boundary 2/4). Commit
  `verdicts.json` + README before(0/5)/after(2-reliable+1-boundary) delta + 4-run tally.
- **Deferred (NOT this task):** stable 5/5 recall (catch A2/A3) → the ≥20-trace
  out-of-sample round. Do NOT prose-tune to n=5 (2 positives were defective).
- **Iterate:** only if a **control regresses** (TNR<1.0) → revise 3.6b/3.6c prose.
  A missed A1/A2/A3 is logged, not chased.
- **Fail if:** rates asserted in CI (live path stays local); a control regresses;
  prose is tuned to flip a single fixture case.

## 3.6f — Close-out [dep: 3.6d, 3.6e] — ✅ DONE (2026-07-04)
Mark enable-policy FR-G4.1 satisfied; bump `rubric_version`; confirm judge flags +
`COACH_LEAKAGE_GATE_ENABLED` remain OFF (FR-G4.3).
- **Pass:** FR-G4.1 marked done + linked to the winning re-record; flags OFF.
- **Done:** FR-G4.1 marked SATISFIED-with-rescope in the enable-policy spec (linked
  to commit `9362097` + the 4-run baseline); `rubric_version` intent recorded as
  `coach_rubric_v1_revised` (concrete manifest value written at FR-G5 assembly);
  `COACH_LEAKAGE_GATE_ENABLED` + all judge flags confirmed default-OFF
  (`_env_flag` returns False on unset — `services/subject_coach_judge_runtime_config.py:41`).
  Strict 5/5 leak-recall deferred to the ≥20-trace out-of-sample round (FR-G4.3).

---

## Dependency graph

```
3.6-0 ─▶ 3.6a ─┬─▶ 3.6b ─┐
               │          ├─▶ 3.6d ─┐
               │   3.6c ─┘          ├─▶ 3.6f
               └──────────▶ 3.6e ───┘
```
3.6-0 (data plane + fixtures) gates everything — without the item, 3.6e measures
noise. 3.6c ‖ 3.6b. 3.6e needs the rubric prose (3.6b/3.6c) + schema (3.6a) + the
corrected item-aware goldset (3.6-0).

## Out of scope

- Hard leak-rate CI gate (≥20 overt-demand traces — next round).
- Enabling judge flags / `COACH_LEAKAGE_GATE_ENABLED`.
