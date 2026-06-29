# Model A/B — L2/L3 Blind Adjudication & Gold-Set Bootstrap Plan

**Date:** 2026-06-25 · **Last updated:** 2026-06-28
**Status:** ✅ Phases 0–5 COMPLETE — **settled at 97 rows / 5 growth arms** (glm-5.1
folded in). Clean gate **PASS** (TPR 1.0 / TNR 0.974, n=59 strict-clean). The
gpt-4o-mini + gpt-5 arms are **DEFERRED** (gpt-5 was harvested clean into side-files
but not merged; gpt-4o-mini is flaky in the loop). n≥100 not pursued further.
**Decision (user, 2026-06-25):** Option 3 — defer all L2/L3 judging to a disciplined
gold-set process rather than ad-hoc judge use. This plan is the walkthrough +
acceptance criteria for that process.

> **Current state (2026-06-28) — SETTLED.** The frozen seed is at
> `cache/goaljudge_eval/model_ab_l2l3_goldset_seed.json` — **97 rows**,
> `provisional: true` (base cases 07–15 across 6 arms + growth cases 16–24 across
> **5 live arms**: opus/haiku/deepseek-pro/deepseek-flash/**glm-5.1**). All waves
> 2-rater blind-adjudicated (Phases 0–4). Phase 5 (GoalJudge-vs-seed,
> `l2l3_full97_goaljudge_verdicts.json`) PASSES on the clean set: **TPR 1.000 /
> TNR 0.974** (n=59 strict-clean / 47 exclude-partial; 1 residual fp = the
> pre-existing base item). The CLEAN gate drops **15 env defects + 23
> truncated-at-source** answers (the 500-char harvest-clip data defect, same class
> as base item 70ff3369) via the audited `TRUNCATED_AT_SOURCE` set in
> `scripts/measure_l2l3_goaljudge.py` → `judge_validation --clean`. Recorded in the
> seed manifest's `phase5_validation` block.
>
> **DEFERRED (not pursued):** the gpt arms. **gpt-5** WAS harvested clean + unclipped
> (9/9, via the GoalJudge-on path `scripts/harvest_growth_gpt_arms.py` reading the
> 8192-char `final_answer`; case-20 was an `Errno 30 read-only /workspace` env defect)
> into side-files `cache/model_ab_answer/l2l3_growth_gpt_*` — **NOT merged** into the
> seed (decision: settle on glm-5.1 and move on). **gpt-4o-mini** is flaky in the
> tool-calling ReAct loop (empty tool-call turns) and was skipped. n≥100 not pursued
> further. See the **Progress log** for the wave-by-wave record.

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

---

## Progress log (newest first)

### 2026-06-28 — SETTLED at 97 rows (glm-5.1); gpt arms DEFERRED
**Decision (user): settle on the glm-5.1 5-arm state and move on.** The 5th-arm
(glm-5.1) sweep below completed — its 9 items were blind-adjudicated and frozen, taking
the seed to **97 rows / 5 growth arms**. Clean gate re-verified PASS on the 97-row seed:
**TPR 1.000 / TNR 0.974** (n=59 strict-clean / 47 exclude-partial; 1 residual base-wave
fp), with the CLEAN exclusion now covering 15 env defects + **23** truncated-at-source
items (the original 18 + 5 glm-5.1 under the same ≥498-char criterion). 74 focused tests
green.

The **gpt arms were explored but NOT merged**: **gpt-5** was harvested clean and
unclipped (9/9 via `scripts/harvest_growth_gpt_arms.py`, GoalJudge-on, reading the
8192-char `final_answer` — lengths 53–2349, zero clip artifacts; case-20 was an
`Errno 30 read-only /workspace` env defect, the other 8 clean) into side-files
`cache/model_ab_answer/l2l3_growth_gpt_*`. **gpt-4o-mini** is flaky in the tool-calling
ReAct loop (empty tool-call turns derail the run before final-answer synthesis; it
answers fine via direct `LLMService.invoke`) and was skipped. Per the settle decision,
gpt-5 stays in side-files (not folded into the seed) and n≥100 is not pursued further;
the gpt-5 harvest + the `harvest_growth_gpt_arms.py` GoalJudge-on path remain available
if the arm is wanted later.

### 2026-06-28 — GROWTH 5th arm (glm-5.1) sweep COMPLETE

Added `glm-5.1` as a 5th live arm (distinct from opus/haiku/deepseek-pro/deepseek-flash).
All steps done:
- ✅ Live run (9 cases, `glm-5.1` vs `deepseek-v4-flash` baseline).
- ✅ Harvest → 5 arms × 9 cases = 45 cells in `l2l3_growth_raw_answers.json`.
- ✅ Blind set rebuilt (45 items; existing 36 item_ids stable).
- ✅ Rater-1 re-graded all 45 (38 correct / 7 partial).
- ✅ Rater-2 (human) graded the 9 new items via
  `l2l3_growth_new9_rater2_worksheet.md` — **7 correct, 1 partial, 1 wrong**
  (case 19: file-read failures → wrong; case 24: clipped cut set → partial).
- ✅ Merged into full 45-item answered worksheet; freeze → **seed 97 rows**.
- ✅ Growth IAA α = 0.917 (44/45 agreement; 1 disagreement: glm-5.1 case 19,
  rater-1 partial → rater-2 wrong).
- ✅ `judge_validation --clean` PASS on 97-row seed (TPR 1.000 / TNR 0.974).

### 2026-06-28 — Phase 5 RAN + truncation-exclusion ADOPTED → clean gate PASS
**Outcome: full-88 was FAIL as-is (TNR 0.830); user adopted the truncation-exclusion
rule; clean gate now PASSES (TPR 1.0 / TNR 0.971).** The 18 truncated growth answers
are dropped from the CLEAN gate via the audited `TRUNCATED_AT_SOURCE` set in
`scripts/measure_l2l3_goaljudge.py` (folded into `_is_excluded_from_clean`, which
`judge_validation --clean` now calls) — keyed on the 500-char truncation criterion
applied to ALL 18 uniformly (7 were the false-downgrades; no outcome-driven
cherry-picking). 4 new exclusion tests + the `_count_for_label` regression are green
(74 in the focused suite). Result recorded in the seed manifest `phase5_validation`
block. Below is the original as-is analysis that motivated the rule.

- **GoalJudge had to be RUN, not harvested.** The growth A/B harvest never ran
  GoalJudge (its `evals.log` has only `guardrail`+`call_llm` targets, zero
  `goal_judge`), unlike the base wave (9 `goal_judge` records/arm). New runner
  `scripts/run_growth_goaljudge.py`: real `components.goal_judge.GoalJudge`,
  **gpt-4o** (matches the base wave's pinned judge — NOT a tier alias; reachable
  despite the OpenAI quota that still blocks the gpt *answer* arms). Judged only the
  36 in-seed growth rows (the sealed key holds 45/5-arms incl. a glm-5.1 arm that was
  never frozen into the seed).
- **Evidence reconstructed** (growth saved final-answer-only, no trajectory): READ
  entries carry real on-disk `workspace/` fixture bytes (so the deterministic
  verifier cascade fires as in the base wave); WRITE entries are synthetic
  `file_io write` from the on-disk `out/*.txt` artifacts when the prompt names a
  `/workspace/out/...` target (cases 16/18/22). **Documented approximation:** the
  `out/` files are shared+overwritten across arms → write evidence is NOT per-arm
  attributable. Without write-evidence the judge false-downgraded every correct
  write-task answer ("no write in evidence"); adding it flipped 9 (15→24 met).
- **Real verifier bug found + fixed (TDD red→green).**
  `components/answer_verifiers._count_for_label` matched the FIRST region mention and
  read a digit glued to an adjacent id — opus case-17 narrated `o2→c2→south`, so it
  read east=2/north=5 instead of the FINAL ANSWER east:4/north:1, rejecting a correct
  answer. Fix: require `(?<![\w])` before the digit + tally-only separators
  `[:|(=#.\s-]` + take the LAST pairing. Regression in
  `tests/components/test_answer_verifiers_value_shapes.py::TestCountByGroup` (31
  verifier/cascade tests green).
- **Gate, full 88 (`meta.judge_validation`, all four cells):** stable
  **TPR 1.000 / TNR 0.830**, 8 false-downgrades, 0 missed failures → **FAIL** (floor
  0.90). Root cause: **7 of the 8 fp are answers truncated at the 500-char harvest
  clip** (24/45 growth answers hit the clip) — the judge reasonably marks a cut-off
  answer not-met, the human read through it per the truncation protocol. Same
  mechanism as the already-excluded base item 70ff3369; the 8th fp is that base item.
  **Counterfactual excluding the 7 truncated-answer rows: TPR 1.000 / TNR 0.975 —
  PASS.**
- **Artifacts:** `cache/model_ab_answer/l2l3_growth_goaljudge_verdicts.json`,
  combined `cache/model_ab_answer/l2l3_full88_goaljudge_verdicts.json` (52 base
  cascade + 36 growth, 0 overlap, covers all 88 seed rows).
- **OPEN DECISION (user):** (a) apply the truncation-exclusion rule (precedent
  70ff3369) → gate passes on the clean set; or (b) re-harvest the growth answers
  UNCAPPED (no 500-char clip) and re-judge → honest full set, fresh live A/B. The
  verifier-bug fix is committable independently of either choice. Did NOT silently
  exclude rows or weaken the floor.

### 2026-06-28 — GROWTH wave (cases 16–24) Phases 0–4 COMPLETE
- Grew the frozen seed **52 → 88 rows**. 4 live arms harvested
  (opus/haiku/deepseek-pro/deepseek-flash; gpt-4o-mini + gpt-5 DEFERRED on OpenAI
  429). Blind set + sealed key built; rater-1 blind-graded; rater-2 (you) graded via
  a detailed per-case worksheet (`scripts/build_growth_detailed_worksheet.py` →
  `l2l3_growth_rater_worksheet_detailed_answered.md`).
- **IAA: 36/36 perfect agreement, α = 1.0** ("almost perfect", gate ≥0.80 PASS) via
  `services/governance/iaa.py`. Honesty caveat recorded in the manifest: α=1.0
  reflects a 2-class outcome (0 "wrong"), so the disagreement space was narrower than
  the base wave's 3-class grade. Blinding verified by hashing the BLIND ITEMS
  (`blind_items_sha256`) before opening the sealed key.
- Frozen by `scripts/freeze_l2l3_growth_into_seed.py` (appends, idempotent;
  manifest `provisional: true`, v0.2, `growth_wave` block records arms / agreement /
  caveat / deferred gpt arms → target 108 rows once OpenAI is topped up).

### (earlier) — BASE wave (cases 07–15) Phases 0–4 COMPLETE
- Original 9 cases × 6 arms blind-adjudicated → 52-row frozen seed (one item,
  70ff3369, EXCLUDED as truncated-at-source). Base gate (cascade-overlaid verdicts):
  **TPR 1.0 / TNR 0.9375 PASS** (strict + exclude-partial, `--clean`). The
  deterministic answer-verifier cascade (`components/answer_verifiers.py`) was added
  to fix GoalJudge's "grades process not correctness" weakness (it had scored a
  reversed topological sort 1.0).

> **Phase-scope note.** The original plan body above is written for the 9-case base
> wave; the growth wave (16–24) extended every phase identically (blind set → sealed
> key → 2-rater → α → freeze). The acceptance criteria are unchanged; only the row
> counts and arm sets grew.
