---
type: decision-record
title: 'ADR-0017: Subject-Coach rubric revision — operationalize indirect-leak detection'
status: proposed
created: 2026-07-04
updated: 2026-07-04
owner: Rajnish Khatri
related: coach-rubric-revision.spec.md, coach-rubric-revision.plan.md, coach-judge-validation-3.5f-handoff.md, coach-goldset-enable-policy.spec.md
tags: [decision-record]
---

# ADR-0017: Subject-Coach rubric revision — operationalize indirect-leak detection

**Status:** Proposed — 2026-07-04 (design-reviewed same day; four findings F1–F4
discharged in-text below — F1 settled before the schema lands).
**Related:** [3.6 spec](../plan/coach-rubric-revision.spec.md) ·
[3.5f handoff](../plan/coach-judge-validation-3.5f-handoff.md) ·
[enable-policy FR-G4.1](../plan/coach-goldset-enable-policy.spec.md).
**Audience:** anyone editing the coach judge rubrics or the `PedagogyVerdict`
contract, or reconsidering how leak detection is graded.

---

## Context

The Subject-Coach leakage judge (`prompts/subject_coach_pedagogy_judge.j2`) is
PROVISIONAL — a research-prior seed. Task 3.5 built a validation harness and
measured it against 22 human-coded fixtures. The result was unambiguous and is the
forcing function for this ADR:

- **Both `gpt-4o` (capable) and `claude-opus-4-8` (reasoning) caught 0/5 indirect
  leaks**, TNR=1.000. (Precise TPR form: gpt-4o fn=5/5; Opus fn=4 with A1 abstained
  and excluded from the denominator — the count-form "0/5 caught" is the exact
  claim.) The strongest reasoning model available cannot detect the leaks on the
  current rubric.
- The 200-trace human open/axial/selective coding found leakage is **entirely
  indirect** (0 direct `leak-states-answer` in 200 traces): rule-naming,
  Socratic-clothing, strong-implication, criterion-then-verdict (refusal theater),
  cross-question. Answer-string matching is worthless against this coach.
- The current rubric already *says* "strongly implies / eliminates-down-to," yet
  the judge cannot operationalize it — the wording is abstract, not a checkable
  procedure.
- Opus also **omitted** the required `answer_leakage` field on 4/22 cases (the
  judge's fail-closed contract yielded `None`, never faked) — the field is not
  reliably elicited under long reasoning.

A change is necessary now because FR-G4.1 gates the enable-policy cert on a REVISED
rubric, and 3.5 has produced the exact acceptance criteria (5 misses → catches,
TNR=1.000).

---

## Decision

Revise both coach judge rubrics from the grounded codes and mark them **REVISED**:

1. Rewrite the pedagogy leak section to name each of the **five indirect channels**
   with a concrete tell, and make the **"after this reply, is more than one option
   still live?"** question the decisive test — expressed as **prose reasoning, not
   a numeric threshold** (thresholds are forbidden in `.j2` per prompts/AGENTS.md).
2. Add a **payload-over-refusal** rule: a refusal/decline sentence carries no
   credit; grade what the turn resolves after it.
3. Make `answer_leakage` an **explicitly-mandated, un-buriable** output ("emit even
   when false"), and add an **optional, best-effort** `leak_channel: LeakChannel |
   None` to `PedagogyVerdict` naming the channel when a leak is found. **An
   unrecognized channel value is soft-coerced to `None`, never rejected** (a
   `field_validator(mode="before")`) — the channel is telemetry; it must NOT be
   able to void an otherwise-valid verdict (see Finding F1).
4. Add a **refusal-aware** criterion to the grader rubric.

Prove the revision by re-recording the same `claude-opus-4-8` baseline: the strict
exit bar is 5/5 indirect leaks caught, TNR=1.000, and the 4 abstentions resolved.

---

## Options considered & rejected

| Option | Why it lost |
|---|---|
| **(A) "Just use a bigger/reasoning model"** | **Empirically falsified.** `claude-opus-4-8` (reasoning tier) scored the *same* 0/5 as `gpt-4o`. The failure is in the rubric's abstraction, not model capacity — a stronger model given an un-operationalized criterion still cannot apply it. This is the whole reason 3.5 recorded the Opus baseline first. |
| **(B) Encode a numeric leak threshold in the prompt** (e.g. "flag if ≤1 option remains, score ≥0.7") | **Violates the config split** (prompts/AGENTS.md): `.j2` holds prose policy; numeric thresholds live in `components/routing_config.py` where the meta-optimizer tunes them. A number baked into the prompt is untunable and off-doctrine. The "options still live?" test is expressed as *reasoning*, not arithmetic. |
| **(C) Make `leak_channel` a REQUIRED field** | **Backward-incompatible.** `PedagogyVerdict.model_config` has no `extra="forbid"`, and every prior verdict (incl. the committed gpt-4o/Opus baselines) lacks the field. A required field would invalidate them and force a re-record of history. Optional-with-default is additive and safe to roll back. |
| **(D) Add a deterministic pre-filter (string/regex leak detector) in front of the judge** | The coach never states an answer string (0/200 direct) — a string detector catches nothing here and adds a component with no signal. The judgment is semantic ("does naming this rule resolve the choice?"), which only the LLM judge can make. |

---

## Rationale

The chosen option ties directly to the measured failure: the judge fails because
the criterion is a slogan, not a procedure. Naming each channel with its tell and
forcing the options-live test converts the slogan into steps a reasoning model can
execute — which is exactly what a bigger model *couldn't* compensate for (rejecting
A). Keeping the test as prose respects the config split (rejecting B). The optional
`leak_channel` gives directly-comparable telemetry against the fixture's existing
`expected.leak_channel` (whose 5 values already match the enum 1:1) without breaking
the contract (rejecting C). And because all observed leakage is indirect/semantic, a
deterministic pre-filter has nothing to bite on (rejecting D). Every new criterion
maps to a grounded taxonomy category (FR-G4.2), so the rubric stays anchored to the
human coding, not invented.

---

## Consequences

- **New commitments:** `PedagogyVerdict` gains an optional `leak_channel` (a
  `components/` type — **not** `trust/`, so no re-signing); a `LeakChannel` Literal
  of 5 values becomes a contract mirrored between code and prompt prose; both
  rubric headers flip PROVISIONAL → REVISED and `rubric_version` bumps.
- **Accepted risk — small positive cell (n=5):** the strict 5/5 bar rests on 5
  cases; a single stubborn channel may need prose iteration (the plan builds in a
  Stage B↔D re-record loop). This is prompt engineering, not a first-try promise.
  The hard invariant is **TNR=1.000** — a revision that catches leaks by
  false-flagging a clean control is rejected, not shipped.
- **Accepted risk — leakage still telemetry-only:** per FR-G4.3 the judge flags and
  `COACH_LEAKAGE_GATE_ENABLED` stay OFF through this task; the REVISED rubric
  improves detection but does not yet gate the live coach. The hard leak-rate CI
  gate waits for ≥20 overt-demand traces (next collection round).
- **Follow-on:** the live acceptance re-record is manual/local (creds-gated Opus);
  CI replays the committed post-revision `verdicts.json` offline (no live LLM in
  CI). The enable-policy cert (FR-G4.1) marks satisfied once acceptance passes.
- **Honest downside:** the revised prompt is longer and more prescriptive, which
  can raise cost/latency slightly and risks over-fitting the wording to these 22
  fixtures. Mitigation: the controls guard over-fitting on the false-positive side;
  the next-round corpus expansion guards it on the recall side.
- **Named circularity (design review):** the five channels *and* their concrete
  tells are reverse-engineered from the same 5 positive cases the acceptance bar
  measures — training and testing on n=5 is near-circular by construction. This is
  *acceptable only because* leakage stays telemetry-only (FR-G4.3) and no gate
  ships until the ≥20-trace next round re-validates on unseen cases. The next-round
  re-validation is therefore **not optional and not "already proven"** — it is the
  out-of-sample check this pass structurally cannot be.

---

## Findings & amendments (design review, 2026-07-04)

A review against the repo confirmed the core diagnosis and the four rejections,
and raised four points — discharged **in text** (the ADR-0016 pattern), F1 being
substantive and settled before the schema lands.

- **F1 (substantive — settled in Decision §3): strict `Literal` amplifies
  abstentions.** The judges are fail-closed: any `ValidationError` in
  `model_validate` yields `None` (`components/subject_coach_judges.py:106–113`).
  A strict `leak_channel: Literal[...]` would let a cosmetic near-miss
  (`"socratic_clothing"`, `"rule naming"`) **void an otherwise-correct
  `answer_leakage=true`** — catastrophic on a 5/5-bar run. **Decision: soft-coerce
  an unrecognized channel to `None` via a `field_validator(mode="before")`**
  (mirrors the existing `failure_mode` validator at `schemas.py:197`), keeping the
  verdict. This resolves the spec's §4↔§8 strictness inconsistency: `leak_channel`
  is best-effort telemetry, never a rejection trigger. The `rejects_unknown_value`
  test is replaced by `coerces_unknown_to_none`.
- **F2 (mechanical gap): code↔prose mirror has no drift sensor.** The "5 values
  mirrored between code and prompt" contract is now a **partial gate**: an L1 test
  asserts each `LeakChannel` value appears verbatim in the pedagogy `.j2` (extends
  the FR-10 header grep). Added as spec FR-12 / task 3.6a-5.
- **F3 (consistency): channel-when-false stays prose, deliberately.** §6's "a
  channel named while `answer_leakage=false` is a self-contradiction" is kept
  **prose-only, NOT schema-enforced** — a cross-field `model_validator` would be a
  second abstention trigger (it interacts with F1), and the fail-closed simplicity
  is worth more than enforcing a telemetry nicety. Stated here so the omission is a
  decision, not an oversight.
- **F4 (wording): the precise number is "0/5 caught," not "TPR=0.000 on 5."** Opus's
  TPR denominator is 4 (A1 abstained, excluded → fn=4); the count-form "0/5 caught"
  is exact and is the formulation future readers should cite.

---

## Findings & amendments (validation re-record, 2026-07-04 — data-plane gap)

The first post-revision re-record (Opus 4.8, reasoning tier) did **not** clear the
5/5 bar. Root-causing the misses surfaced a defect one layer BELOW the rubric that
the abstract wording had masked, plus two mislabeled fixtures. Discharged in text.

- **F5 (data-plane — the real blocker): the judge was never shown the item.** The
  recorder passed `question=case["question_id"]` — the judge received the bare
  string `"q-gram-1"`, not the passage/stem/choices. The ADR-0017 decisive test
  ("after this reply, is >1 option still live?") is *structurally impossible* to
  run without the options: the judge fell back to a syntactic proxy ("did the coach
  NAME an option?") and missed every indirect leak. **Fix:** `scripts/enrich_coach_judge_cases.py`
  resolves each `question_id` against the ground-truth item bank
  (`frontend/e2e/fixtures/preact_learn_corpus.ts` — the corpus the fixtures were
  authored against) and writes a rendered `question` block into `cases.jsonl`,
  mirroring `components/coach_context._render_question` (pre_submit strips the
  answer key; post_feedback includes it). The recorder now passes that block. This
  is a prerequisite the ADR's "small positive cell / prose iteration" framing did
  not account for — no amount of rubric prose helps a judge that can't see the item.

- **F6 (fixture defect — mislabeled `question_id`, present since `ad67f63`):** with
  the item visible, the judge correctly flagged item↔reply incoherence on A1 and A2.
  Their `question_id` did not match their own coach reply / `purpose`:
  - A1 (`purpose`: rule-naming on "redundancy") pointed at `q-punc-1` (a comma item).
    Corrected → `q-style-3` ("true and honest" → only "genuine" is the concise choice).
  - A2 (coach: "what does *return* tell you… the *book*… redundant") pointed at
    `q-rhet-1` ("very extremely"). Corrected → `q-style-1` ("returned the book back").
  The source fixture `docs/evals/eng-coach/judge_test_cases.jsonl` carries the same
  mislabels and should be corrected in lockstep.

- **F7 (fixture defect — non-collapsing item on a leak case):** B1's authored intent
  is a single-survivor collapse, but it sat on `q-rhet-1`, which has TWO single-word
  choices ("extremely"/"very") that both survive "most concise" — so the item-aware
  judge correctly read it as non-leak. Re-paired B1 → `q-rhet-3` ("important and
  significant" → only "significant"), where the criterion uniquely collapses; the
  coach reply was updated to quote that item's stem. (Adjudication: keep leak=true,
  tighten the item — the channel intent is sound, the item was wrong.)

- **F8 (residual genuine FN — the honest out-of-sample signal): A2 socratic-clothing
  on a deletion-style item is under-detected.** After correction, on `q-style-1` the
  "return… back" redundancy collapses to the single DELETE choice (C/D ADD redundancy),
  yet the judge counts C/D as live ("B, C, D all remove or alter 'back'") and returns
  non-leak. This is exactly the class ADR-0017 targets and it is **not** fixed by the
  current prose. Per the ADR's own anti-circularity stance (n=5, telemetry-only until
  the ≥20-trace next round), we do **not** prompt-tune against this single case — A2 is
  logged as the open residual and deferred to the out-of-sample re-validation.

- **F9 (determinism at temp>0): A3 sits on the decision boundary.** A 4-run repeat
  re-record on the corrected fixtures gives a stable picture, NOT random noise:
  B1 4/4, G3 4/4 (reliably caught); **A3 2/4** (strong-implication flips ~50% run to
  run); A1 0/4, A2 0/4 (reliably missed); the scorer's H1≡C2 pair also diverged on
  axis floats. Corrected-baseline confusion lands at TP=2–3 / FP=0 / FN=2–3 / TN=16,
  **TNR=1.000 stable in every run**, TPR=0.4–0.6. The honest claim is "2 channels
  reliably caught, 1 boundary-unstable, 2 reliably missed" — improved over the 0/5
  pre-revision baseline, but below the 5/5 bar and not a clean pass.

### Net effect on the exit bar
The strict "5/5 caught, TNR=1.000" bar is **not met** on honest data. TNR=1.000 holds
(no control regressions, FPR=0). The gap is now correctly attributed: 1 defensible
judge-stance miss (A1 rule-naming = naming a rule without instantiating it), 1 genuine
residual FN (A2), and boundary instability (A3, 2/4). The out-of-sample ≥20-trace round
(already named non-optional in Consequences) is where the rubric's real recall must be
proven; this pass's contribution is an *honest, item-aware* baseline and a corrected
goldset, not a green gate.

---

## Supersedes / related

Makes canonical the rubric-revision decision for FR-G4.1. Builds on the 3.5
validation harness (no ADR — same class as the GoalJudge validator). Does not
supersede a prior ADR. Pairs with the 3.6 spec/plan/tasks.
