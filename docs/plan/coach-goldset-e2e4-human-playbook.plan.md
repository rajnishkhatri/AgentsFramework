---
type: plan
title: 'E2 + E4 human-execution playbook — the runbook'
authored: 2026-07-05
---

# E2 + E4 human playbook — the runbook

**Spec:** [coach-goldset-e2e4-human-playbook.spec.md](coach-goldset-e2e4-human-playbook.spec.md) ·
**Parent:** [coach-goldset-corpus-expansion.plan.md](coach-goldset-corpus-expansion.plan.md)

Roles: **Author** (writes the fresh test batch) · **Rater A**, **Rater B** (label
blind, independently) · **Adjudicator** (scores α, resolves disagreements). One
person may wear ≥1 hat *except* the two raters must be different people (AC-6).

---

## Phase E2 — author the fresh test batch  (Author)

1. Open the template:
   [../evals/eng-coach/coach_test_batch_v1.template.md](../evals/eng-coach/coach_test_batch_v1.template.md).
   Author ~80 rows into `docs/evals/eng-coach/coach_test_batch_v1.jsonl`, one JSON
   object per line, hitting the coverage table's per-prefix minimums.
2. **Self-check before handoff** (the AC gates):
   - each row: `provenance="fresh-authored"`, `split="test"`, no `answer_leakage`
     / `leak_channel` (AC-4);
   - all 5 channels + 2 carve-outs present by `item_id` prefix (AC-3);
   - leak-likely prefixes (RN/SC/SI/CV/CQ) ≈ 20–25% of rows (AC-5);
   - eyeball for caricature — clean vs leaking members of a channel should differ
     *minimally* (AC-2).
3. **Disjointness pre-check** (catches AC-1 before labeling): the E6 freeze runs
   `assert_dev_test_disjoint`, but check early — no authored `(learner_utterance,
   coach_reply)` may match a 292-corpus turn or a round-1 row. (Agent can run a
   quick overlap scan when E3 wires the batch in.)
4. Handoff → the **agent resumes E3** (extends the exporter to join the E1 dev
   sample + this batch into expanded blind sheets). Nothing to label yet.

## Phase E4 — blind double-label round 2  (Rater A, Rater B, Adjudicator)

5. Agent produces `coach_goldset_annotator1_sheet.csv` +
   `coach_goldset_annotator2_sheet.csv` (~210 rows each, blind — no leak guess).
6. **Read first:**
   [../IAA/coach/goldset/coach_labeling_walkthrough.md](../IAA/coach/goldset/coach_labeling_walkthrough.md).
   The whole job is the operational test: *after the reply, is > 1 option still
   live?* `mode` first; the 5 channels; the 2 carve-outs.
7. **Label blind + independent** (AC-6): Rater A fills `r1_answer_leakage`, Rater B
   fills `r2_answer_leakage`, each in their own sheet, **no discussion** until both
   are done. Use `rN_note` for the *why* on any row you hesitate on.
8. **Score α** (Adjudicator, AC-7):
   ```
   .venv/bin/python scripts/compute_coach_goldset_alpha.py \
     docs/IAA/coach/goldset/coach_goldset_combined_sheet.csv \
     --diff cache/coach_eval/coach_goldset_alpha_disagreements.csv
   ```
   (Agent builds the combined sheet by joining the two on `item_id`.) Record the
   result in `coach_goldset_alpha_results.md`.
9. **If α ≥ 0.80** → go to step 11. **If α < 0.80** → the bounded recovery loop
   (AC-8): the disagreement diff names the channel(s) driving it; clarify the
   walkthrough guideline on *that channel*, re-label the affected rows blind,
   re-score. **≤ 2 rounds.** Still < 0.80 after 2 → **STOP, escalate** (do not
   adjudicate to a number).
10. (loop back to 8 if within the 2-round budget.)
11. **Adjudicate** (AC-9): for every `r1 ≠ r2` row, the Adjudicator sets
    `adjudicated_answer_leakage` with a one-line note (mirror the round-1 A2
    record). Agreed rows keep the agreed label.
12. **Final check** (AC-10): zero blank `adjudicated_answer_leakage` cells.
13. Handoff → the **agent resumes E6** (re-freeze non-provisional) → E7 cert run.

---

## Constitution check

No code, no dependency, no ⚠️ Ask-first trigger → **no ADR**. The two clarify
decisions (2 human raters; 2-round α-fail ceiling) are recorded in
`docs/adr/decisions.md`. Fresh-text discipline is mechanically enforced by the
existing `assert_dev_test_disjoint` gate.

## Risk / mitigation

| Risk | Mitigation |
|---|---|
| α drops on the harder fresh channels | AC-8 bounded loop; walkthrough already codifies the 5 channels + 2 carve-outs |
| Raters coordinate → inflated α | AC-6 blind/independent DoD gate; different people required |
| Thin leak class in test split → undecidable TPR | AC-5 targets 20–25% leak-likely; edge-case check flags back to E2 |
| Authoring caricatures → judge over/under-fits | AC-2 minimal-pair realism gate |
