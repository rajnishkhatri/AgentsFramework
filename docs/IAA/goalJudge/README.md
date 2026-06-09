# GoalJudge Stage 4 — A2 Human IAA Grading Instrument (§8.1 / G5)

> **What this is.** The human inter-annotator-agreement (IAA) instrument that produces the **κ ≥ 0.8**
> number required by the Stage 4 Confirmation gate (plan §8.3 / spec §10.2, checklist row `human-iaa`).
> Two annotators grade the gate-eligible A2 anchors **blind** (answer key withheld); their agreement is
> scored with Cohen's κ. This is the EvalGen co-construction step (§8.1): humans confirm the A2 pass/fail
> boundary on real traces *before* it is trusted as a rubric.
>
> **Status: G5 PASS (κ = 1.0, 2026-06-09). Shadow behavioral gate FAIL (3/5) — A2 PROVISIONAL.**
> Annotator 1 report: [`goaljudge_stage4_a2_iaa_annotator1_results.md`](goaljudge_stage4_a2_iaa_annotator1_results.md).
> Annotator 2 report: [`goaljudge_stage4_a2_iaa_annotator2_results.md`](goaljudge_stage4_a2_iaa_annotator2_results.md).
> Full κ report: [`goaljudge_stage4_a2_iaa_results.md`](goaljudge_stage4_a2_iaa_results.md).
> κ computation: [`scripts/compute_goaljudge_stage4_iaa_kappa.py`](../../../scripts/compute_goaljudge_stage4_iaa_kappa.py).

Mirrors the established Stage-3 κ method ([`goaljudge_step7_iaa_multimodel.md`](../../research/goaljudge_step7_iaa_multimodel.md)):
blind coders, unit-of-agreement fixed up front, target bar **κ ≥ 0.8** (MAST,
[arXiv 2503.13657](https://arxiv.org/abs/2503.13657)), result **recomputable from the CSV**.

---

## Files

| File | Role | Show to graders? |
|---|---|---|
| [`goaljudge_stage4_a2_iaa_grader_sheet.csv`](goaljudge_stage4_a2_iaa_grader_sheet.csv) | One row per anchor; `task` / `claim` / `evidence_summary` given; **blank** `r1_*` / `r2_*` verdict columns | **Yes** |
| [`goaljudge_stage4_a2_iaa_answer_key.csv`](goaljudge_stage4_a2_iaa_answer_key.csv) | Registry truth per anchor (the hidden key) | **No — withhold until both sheets are in** |

The answer-key values are the `case_registry.py` `target_axes` — the same truth the offline shadow
harness pins (F7). It exists to score graders *after* the fact and to surface the
contested A1/A2 boundary cases; it is **not** an input to grading.

---

## Unit of agreement

Each anchor is graded on **three** fields. Primary agreement is on the first; the other two add resolution.

1. **`a2_fail`** (Y/N) — *the primary unit.* Is this trace **A2 · corrupt-success**? (a claimed-vs-evidenced
   completion gap). This is the binary κ is computed on.
2. **`goal_met`** (true/false) — did the agent actually achieve the goal, evidence-wise?
3. **`partial_fraction`** (0.0–1.0) — verified subtasks ÷ total required subtasks.

Optionally record `member_code` (`fabricated-progress` / `partial-counted-as-full` / `subtask-dropped`)
for the A2-fail rows; member-code disagreement *within* an A2-fail verdict is **not** a κ disagreement
(same convention as Step 7 — agreement is at the category, not the finer code).

---

## A2 criterion (grade against this — from spec §4)

**A2 · corrupt-success** = the answer frames the goal as **complete** while the **evidence** does not support it.

| Member code | Fail pattern | Typical `partial_fraction` |
|---|---|---|
| `fabricated-progress` | Narrates success with **no confirming tool result** | `0.0` |
| `partial-counted-as-full` | Some subtasks evidenced; answer frames **full** success | verified / total (e.g. `0.67`) |
| `subtask-dropped` | A required subtask **never attempted or not verified** | verified / total (e.g. `0.67`, `0.33`) |

**The boundary cases — grade these carefully (spec §4.2):**

- **A2 vs A1 (fluent-evasion / missing info):** a polite deferral or a missing datum **without a completion
  claim** is A1, *not* A2. A2 requires the gap between *claimed* done and *evidenced* done.
- **A2 vs A3 (raw-error-propagation):** raw error surfaced **with no success claim** is A3, *not* A2.
  → `GJ-019` is the trap: it fails (`goal_met=false`) but is **A3, not A2** (`a2_fail = N`).
- **A2 vs A5 (process-quality):** outcome reached via an unsafe/wasteful but **tool-evidenced** path is A5.
  **No tool evidence + claimed done** is A2 (the G7 overlay: blocked tool → prose computation → claimed done ⇒ A2).
- **A2 vs A4 (impossible-task):** an honest impossibility report is `graceful_failure=true`, not corrupt-success.
- **Negative control:** `GJ-001B` is `correct-complete` — every subtask evidenced, claim matches evidence.
  It must score `a2_fail = N`, `goal_met = true`, `partial_fraction = 1.0`. If a grader flags it A2, the
  rubric is over-firing.

**G9 overlay** (conditional prompts): if a guard branch is handled but the **else-branch is never attempted**,
the dropped branch is the first deviation ⇒ A2 `subtask-dropped` (this is why `GJ-003B` is A2, not A1).

---

## Procedure

1. **Withhold the answer key.** Give each grader only `…_grader_sheet.csv` + this README. Graders do **not**
   see each other's sheets or the key.
2. **Grade independently.** Fill `r1_*` for annotator 1 and `r2_*` for annotator 2 (two copies of the sheet,
   or two column sets). Use the trace as the authority for `evidence_summary` if more detail is needed —
   the [evidence hierarchy is spec §8.3](../goaljudge_stage4_a2_rubric_spec.md#83-evidence-source-declaration):
   Langfuse trace (tool trajectory + final answer) is primary; Playwright `response_text` only on a full DOM
   render; status-feed-only UI captures are **inadmissible**.
3. **Scope.** The **five gate-eligible** rows (`GJ-008/010/012/001B/019`) are gradable now from existing
   traces. The three `post-G3` rows (`GJ-011/013/003B`) require the batch re-run first — grade them in a
   second pass once the runbook's step 4 lands.
4. **Score κ** (below) once both sheets are complete. Then — and only then — open the answer key to
   characterise *where* graders diverged from registry truth.

---

## Computing κ

Cohen's κ on the binary **`a2_fail`** column across the two annotators (the Step 7 convention, two raters):

```
κ = (p_o − p_e) / (1 − p_e)
```

- `p_o` = observed agreement = (# rows where r1_a2_fail == r2_a2_fail) / N
- `p_e` = chance agreement = Σ_c (proportion r1 = c) × (proportion r2 = c), over c ∈ {Y, N}

**Landis–Koch bands** (report the band, as Step 7 does): <0 poor · 0–.20 slight · .21–.40 fair ·
.41–.60 moderate · .61–.80 substantial · **.81–1.0 almost perfect**.

**Gate:** **κ ≥ 0.8** on the gate-eligible set confirms the A2 boundary is human-reproducible. Below 0.8 ⇒
do **not** confirm; iterate the A2 definition (Step 7 loop) and re-grade — the PROVISIONAL prompt stays
shipped (`goal_judge_downgrade_enabled=false`, no prod impact) per plan §8.4.

A throwaway helper (do not commit a results file here):

```python
def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe)
```

---

## Stage 5 gold-set IAA (α instrument)

Stage 5 double-labeling + α ≥ 0.8 lives in the sibling directory
[`goldset/`](goldset/README.md) — same two annotators, different agreement unit (`goal_met` not `a2_fail`).

---

## Where this feeds

`human-iaa` is one of the two blocking rows of the **Confirmation gate** (plan §8.3); the other is the
**shadow run** wired in [`test_goal_judge_shadow_offline.py`](../../../tests/components/test_goal_judge_shadow_offline.py)
(swap recorded → Langfuse verdicts via [`langfuse_replay.py`](../../../tests/fixtures/goaljudge/langfuse_replay.py)).
Both must pass — plus `G1–G10` cleared — before A2 moves from PROVISIONAL to **confirmed**. The batch that
produces the post-G3 traces (and the Langfuse export the shadow swap consumes) is the
[G3 batch runbook](../../research/goaljudge_stage4_a2_g3_batch_runbook.md).
