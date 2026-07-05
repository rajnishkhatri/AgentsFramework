# Spec — E2 + E4 human-execution playbook (authoring + double-labeling)

**Status:** Draft — 2026-07-05
**Owner:** human author + 2 human raters + adjudicator
**Related:** parent [coach-goldset-corpus-expansion.spec.md](coach-goldset-corpus-expansion.spec.md)
(E2/E4); template [../evals/eng-coach/coach_test_batch_v1.template.md](../evals/eng-coach/coach_test_batch_v1.template.md);
labeler guide [../IAA/coach/goldset/coach_labeling_walkthrough.md](../IAA/coach/goldset/coach_labeling_walkthrough.md);
round-1 α [../IAA/coach/goldset/coach_goldset_alpha_results.md](../IAA/coach/goldset/coach_goldset_alpha_results.md) (0.8327).

---

## 1. Goal

Give the humans a **step-by-step, gated playbook** to (E2) author ~80 fresh
held-out test rows and (E4) run a blind double-label round over the ~210-row
expanded set to α ≥ 0.80 — the two irreducibly human gates that unblock the 3.9
cert. This is an **execution playbook, not code**: every acceptance criterion is a
human-checkable Definition-of-Done gate.

## 2. Context

E1 (dev sampler) and E5 (disjointness gate) are done; E3/E6/E7 are blocked on
these two human gates. Round 1 proved the α *instrument* works (0.8327 on 21 easy
rows) — but round 2 is harder: ~80 of the rows are freshly authored across the 5
indirect-leak channels (the subtle cases), so agreement is not guaranteed. The
playbook must make the authoring balanced and the labeling genuinely blind, and
bound the recovery loop if α misses.

Decisions locked in clarify (2026-07-05):
- **Two independent human raters** label blind; a third person (or one of the two,
  post-labeling) **adjudicates** disagreements. α measures genuine inter-annotator
  agreement.
- **α-fail recovery is bounded to 2 revise-relabel rounds**, then escalate to a
  human decision (the axis may be genuinely ambiguous / rubric under-specified).

## 3. Acceptance criteria (EARS — human-checkable DoD)

Failure paths first.

### E2 — authoring
- **AC-1.** IF any authored `learner_utterance`+`coach_reply` (or `item_id`)
  duplicates a dev row (the 292 corpus or the 21 round-1 rows) THEN the author
  SHALL rewrite it — the freeze's `assert_dev_test_disjoint` gate WILL reject an
  overlap, so this is caught before labeling wastes effort.
- **AC-2.** IF a `coach_reply` reads as a caricature (obviously-leaking or
  obviously-clean in a way the deployed coach never would) THEN the author SHALL
  revise it toward a realistic minimal-pair contrast (per `coach_axial_coding.md`
  §4.1) — the judge is graded on *subtle* leaks.
- **AC-3.** THE authored batch SHALL cover **all 5 indirect-leak channels**
  (rule-naming, socratic-clothing, strong-implication, criterion-then-verdict,
  cross-question) AND **both carve-outs** (post-reveal naming, underline-locus),
  at the per-prefix minimums in the E2 template's coverage table.
- **AC-4.** THE authored batch SHALL be ~80 rows with every row
  `provenance="fresh-authored"`, `split="test"`, and **no** `answer_leakage` /
  `leak_channel` pre-filled (those are E4's blind output).
- **AC-5.** THE leak-likely channels (RN/SC/SI/CV/CQ) SHALL be ~20–25% of the
  batch — enough positive rows for a decidable test-split TPR — authored honestly
  (no forced leaks).

### E4 — double-labeling
- **AC-6.** WHILE labeling, the two raters SHALL work from separate blind sheets
  and SHALL NOT discuss any row until both sheets are complete (independence is
  what α measures).
- **AC-7.** WHEN both sheets are complete THE adjudicator SHALL compute α via
  `scripts/compute_coach_goldset_alpha.py` over the combined sheet and record it in
  `coach_goldset_alpha_results.md`.
- **AC-8.** IF α < 0.80 THEN the team SHALL (a) clarify the walkthrough guideline
  on the channel(s) driving disagreement, (b) re-label the affected rows blind, (c)
  re-score — for **at most 2 rounds**. IF still < 0.80 after 2 rounds THEN the team
  SHALL STOP and escalate (do NOT adjudicate to a number).
- **AC-9.** WHEN α ≥ 0.80 THE adjudicator SHALL resolve every `r1 ≠ r2` row into
  `adjudicated_answer_leakage` with a one-line rationale in the note (mirrors the
  round-1 A2 adjudication record).
- **AC-10.** THE final combined sheet SHALL have **zero** blank
  `adjudicated_answer_leakage` cells before the freeze (E6) runs.

## 4. Data / artifacts (no code)

| Artifact | Produced by | Consumed by |
|---|---|---|
| `docs/evals/eng-coach/coach_test_batch_v1.jsonl` | E2 author | E3 exporter |
| expanded `coach_goldset_annotator{1,2}_sheet.csv` | E3 (agent) | E4 raters |
| filled annotator sheets | E4 raters | adjudicator |
| `coach_goldset_combined_sheet.csv` (adjudicated) | adjudicator | E6 freeze |
| `coach_goldset_alpha_results.md` (round 2) | adjudicator | ledger / 3.9 |

## 5. Invariants & boundaries

- **§9 fresh-text discipline** — the test batch is authored on FRESH text, never
  re-using the batch-2 utterances the rubric was validated on. Enforced mechanically
  by `assert_dev_test_disjoint` (AC-1).
- **Blind independence (AC-6)** — the α number is only trustworthy if the raters
  didn't coordinate; this is a process invariant the tooling can't enforce, so it's
  a stated DoD gate.
- **No label leakage into authoring (AC-4)** — the author does not assign
  `answer_leakage`; blind labeling would be void if they did.
- **No live LLM / no flags** — this playbook produces data only; the cert run (E7)
  and any flag flip stay downstream and human-gated.

## 6. Edge cases

- **A channel is genuinely hard to author cleanly** (e.g. cross-question needs a
  two-item context) — allow fewer rows for that channel but never zero; note it in
  the batch header.
- **Raters systematically disagree on one channel** (e.g. socratic-clothing) — that
  is the AC-8 signal to clarify the walkthrough on *that channel*, not to re-label
  everything.
- **α passes but the leak class in the test split is thin** (< ~10 positives after
  labeling) — TPR may be undecidable at cert time → `REFUSE` (honest). Flag back to
  E2 to author more leak rows before freezing.
- **An authored row turns out unscorable** (truncated/ambiguous) — drop it, don't
  force a label (mirrors the I1 exclusion).

## 7. Non-functional

- **Human-paced** — the binding cost is ~80 authored + ~210×2 labels; no agent
  throughput target. Bounded by AC-8's 2-round ceiling so it can't run away.
- **Reproducible α** — always recomputable from the combined CSV (the tooling
  reads the sheet, not memory).
- **Auditable** — every adjudication carries a rationale (AC-9), so the gold labels
  are defensible at cert time.

## 8. Out of scope

- E3/E6/E7 (agent/automated — resume after this gate).
- Production harvest, rubric `.j2` edits, threshold changes, flag flips.
