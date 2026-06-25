# Model A/B — L2/L3 Blind Adjudication & Gold-Set Bootstrap Plan

**Date:** 2026-06-25
**Status:** PLAN (not started). Deferred work — the current A/B cycle reports
**L1-deterministic only**; L2/L3 stay UNGRADED ("pending gold set") until this runs.
**Decision (user, 2026-06-25):** Option 3 — defer all L2/L3 judging to a disciplined
gold-set process rather than ad-hoc judge use. This plan is the walkthrough +
acceptance criteria for that process.

---

## Why this exists (the honest framing)

Three facts established this session forced this plan:
1. **Neither automated grader is trustworthy for L2/L3.** The deterministic
   substring scorer has false-POSITIVES (prompt-token leaks — fixed for L1 via the
   failure-phrase guard, but L2/L3 prose answers are too open for exact match).
   GoalJudge has false-NEGATIVES (it splits one instruction into sub-criteria and
   fails a correct single answer — e.g. `lookup-format-02` "domain is example.com"
   marked `goal_met=False` on every arm). GoalJudge is being used OFF-LABEL: it was
   built to judge "did the agent satisfy success_conditions" for the downgrade
   gate, NOT "is this short answer correct."
2. **A single rater (me, the agent) is not a calibrated gold set.** The repo's
   gold-set machinery (`services/governance/iaa.py`, κ/α, Stage 5) is multi-rater
   BY DESIGN. One rater's labels are a draft, not a gold set — and the rater here
   (the agent running the A/B) is NOT neutral: it has seen the answers and knows
   the hypothesis. Bias is a real risk.
3. **The repo already has the right pipeline** (`llm-eval-grounded-theory` +
   `agentsframework-eval`, `docs/plans/llm_eval_pipeline_skill.plan.md`). The
   correct move is to feed adjudicated labels INTO that pipeline as a starting
   gold set, not to invent a parallel judge.

So: this plan produces **blind, human-reviewed L2/L3 labels** that become the
**seed gold set** for the existing Stage 5/6 calibration process. It does NOT make
the agent a steady-state judge.

---

## Scope

- **Corpus:** the 9 L2/L3 rows of the general family
  (`cache/model_ab_answer/ui_batch.jsonl`, `difficulty ∈ {L2,L3}`).
- **Arms:** whatever arms ran in the A/B sweep (baseline + candidates). Each
  (case × arm) final answer is one adjudication item.
- **Out of scope:** L1 (deterministic scorer, already trustworthy after the
  failure-phrase guard); multi-turn/memory rows (deferred to Phase B entirely).

---

## The process (walkthrough)

### Phase 0 — Author the L2/L3 answer keys (ground truth)
For each of the 9 L2/L3 cases, write a **rubric answer key** from the deterministic
fixtures: the correct result + the acceptable-variation notes (units, ordering,
rounding, format). L2/L3 answers are compound (e.g. "subtotal of paid invoices +
written to a file", "per-region order counts", "topological install order or the
cycle"), so the key is a SHORT RUBRIC (the must-have facts), not a single string.
Store as `cache/model_ab_answer/l2l3_answer_keys.json` (case → rubric).
- **Acceptance:** every L2/L3 case has a key whose correct answer is derivable from
  the seeded fixtures alone (no ambiguity); a second person could grade from it.

### Phase 1 — Build the BLINDED adjudication set
A script emits, for every (case × arm), an anonymized item:
`{item_id, prompt, fixture_facts, model_answer}` — **NO model name, NO arm label,
shuffled order**. The arm↔item_id mapping is written to a SEPARATE sealed file the
rater does not open until after grading.
- Rationale: the rater (agent or human) must not know which model produced an
  answer, or labels inherit the hypothesis bias. This is the load-bearing guardrail
  on "agent-as-reviewer."
- Output: `cache/model_ab_answer/l2l3_blind_items.jsonl` (no arm info) +
  `cache/model_ab_answer/l2l3_arm_key.sealed.json` (the mapping, opened post-hoc).
- **Acceptance:** no item contains a model/arm identifier; the sealed key round-trips
  (every item_id maps to exactly one (case, arm)).

### Phase 2 — Rater 1 grades blind (agent)
The agent grades each blinded item against its Phase-0 rubric: `correct` /
`partial` / `wrong` + a one-line justification + a `confidence` (high/low) flag.
Records to `cache/model_ab_answer/l2l3_labels_rater1.jsonl` (keyed by item_id).
- **Acceptance:** every item labeled; every label has a justification citing the
  rubric; low-confidence items flagged.

### Phase 3 — Rater 2 review (human / you)
You review (at minimum) every `low-confidence` item, every `partial`, and a random
sample of the `correct`/`wrong` — as the second rater. Disagreements are recorded.
This is what turns single-rater draft labels into a 2-rater set with a real
agreement signal.
- **Acceptance:** rater-2 labels recorded for the required subset; an agreement
  rate (rater1 vs rater2) is computed; disagreements have an adjudicated final
  label (rater 2 is tiebreaker, OR escalate to discussion).

### Phase 4 — Compute agreement + freeze the seed gold set
- Compute simple agreement + (if ≥2 raters on enough items) Krippendorff's α via the
  existing `services/governance/iaa.py` primitives — DO NOT hand-roll.
- Freeze the adjudicated labels as `cache/goaljudge_eval/model_ab_l2l3_goldset_seed.json`
  with a manifest: row count, `test_split_sha256`, **`provisional: true`** (it is —
  small + bootstrap), rater count, agreement stat, date.
- **Acceptance (the gate to "usable as a seed"):**
  - all 9 cases × all arms labeled with a final adjudicated verdict;
  - rater-1↔rater-2 agreement ≥ 0.80 on the reviewed subset (below that, the
    rubric is ambiguous → revise Phase 0 and re-grade — do not ship ambiguous keys);
  - manifest marked `provisional: true` (honesty: this is a v0.0 seed, NOT a
    calibrated gold set; it cannot pass the repo's v1 floor gate and must not be
    presented as if it could);
  - the blinding held (arm key opened ONLY after Phase 2 labels were frozen — proven
    by file mtimes / a recorded hash of the labels before the key was read).

### Phase 5 — Feed into the calibration pipeline (defer to agentsframework-eval)
The frozen seed becomes an INPUT to the Stage 5/6 process documented in
`docs/plans/llm_eval_pipeline_skill.plan.md`:
- It is wave-0 of a gold set; the repo's existing v0.9 (101 rows) + wave-2 (~250)
  process is the path to a calibrated judge. This seed does NOT replace that — it
  contributes GAIA-shape answer-correctness rows the current gold set lacks.
- ONLY THEN: fix GoalJudge's criteria-decomposition for single-answer tasks and
  MEASURE the fix against these labels (precision/recall/α vs the seed). Fixing the
  judge BEFORE having labels is the "diagnosis without artifact" anti-pattern the
  eval plan explicitly forbids.
- **Acceptance:** the seed is registered as a dataset the calibration replay harness
  can read; a documented "GoalJudge vs seed labels" agreement number exists BEFORE
  any criteria-split fix, and AFTER, so the fix is measured not assumed.

---

## Acceptance criteria summary (the bar for "L2/L3 grading is trustworthy")
1. Every L2/L3 case has an unambiguous fixture-derived rubric answer key.
2. Adjudication was BLIND (no arm/model labels during grading; blinding provably held).
3. ≥2 raters on the reviewed subset; agreement ≥ 0.80; disagreements adjudicated.
4. Labels frozen with a manifest, marked `provisional: true`, IAA computed via the
   repo's `iaa.py` (not hand-rolled).
5. GoalJudge (or any automated judge) is measured AGAINST these labels before being
   trusted or "fixed" — never the reverse.

## What the CURRENT A/B cycle does instead (until this runs)
- Report **L1-deterministic accuracy only** as the model-A/B signal (10 rows,
  hardened scorer, reproducible).
- Mark L2/L3 as **"ungraded — pending gold set (this plan)"** in the report. Do NOT
  publish a GoalJudge-derived L2/L3 number as a verdict input — it's off-label and
  uncalibrated.

## Non-negotiable honesty rules (carried from the eval pipeline's "teeth")
- A single-rater label set is a DRAFT, never called "the gold set."
- No judge fix without artifact labels to measure it against.
- The agent-rater is biased by construction → blinding is mandatory, not optional.
- `provisional: true` until the repo's real Stage 5 floor gate passes.
