# GoalJudge Stage 5 — Fresh-Corpus A2 Labeling Session Plan

> **What this is.** The plan for the Annotator 2 (A2) labeling pass on the **79-row fresh-task
> corpus** (`GJ-F-001`…`GJ-F-105`, §6 gaps). This is the second blind labeling round that — together
> with A1's already-complete sheet — produces the **Krippendorff's α ≥ 0.8** number that gates
> `goaljudge_goldset_v1` for Stage 6 (the Tier 3 dataset gate).
>
> **Parent plans:**
> - [Stage 5 master plan](goaljudge_stage5_goldset.plan.md) — Tier 3 dataset gate
> - [Tier 3 assembly plan](goaljudge_stage5_tier3_assembly.plan.md) — Phase 4 handoff + Phase 5 procedure
> - [Phase 5 live labeling walkthrough](../research/goaljudge_stage5_goldset/phase5_live_labeling_walkthrough.md) — coordinator runbook
> - [A1 session plan](goaljudge_stage5_fresh_a1_labeling_session.plan.md) — sibling round (reference only; A2 must NOT read A1's labels)
>
> **Status:** **Authoring** — to start once Task #65 (len>80 heuristic fix) lands.
>
> **Date authored:** 2026-06-11.

---

## Table of contents

- [1. Why a separate A2 plan](#1-why-a-separate-a2-plan)
- [2. Locked design decisions](#2-locked-design-decisions)
- [3. Session goal](#3-session-goal)
- [4. Plan overview](#4-plan-overview)
- [5. Phase A — Grader fix (engineering prereq, NOT in A2's labeling path)](#5-phase-a--grader-fix-engineering-prereq)
- [6. Phase B — Build A2 blank sheet (coordinator)](#6-phase-b--build-a2-blank-sheet-coordinator)
- [7. Phase C — A2 cold-blind labeling](#7-phase-c--a2-cold-blind-labeling)
- [8. Phase D — A2 results doc + handoff to α gate](#8-phase-d--a2-results-doc--handoff-to-α-gate)
- [9. Blindness firewall — non-negotiable](#9-blindness-firewall--non-negotiable)
- [10. Grading protocol applied (same as A1)](#10-grading-protocol-applied-same-as-a1)
- [11. What A2 does NOT do](#11-what-a2-does-not-do)
- [12. Verification gates](#12-verification-gates)
- [13. Open items / risks](#13-open-items--risks)
- [14. Implementation checklist](#14-implementation-checklist)

---

## 1. Why a separate A2 plan

The A1 session ([`goaljudge_stage5_fresh_a1_labeling_session.plan.md`](goaljudge_stage5_fresh_a1_labeling_session.plan.md))
was built around a **coordinator-driven semi-automated grader + human confirm/override loop**. That
worked for A1 because A1 was *also* the engineering authority on the corpus and the source of truth
for the override patterns. **A2 must be structurally different** for the α number to be honest:

| Aspect | A1 (semi-auto + review) | A2 (cold blind) |
|---|---|---|
| Initial pre-fill | Semi-auto grader (Langfuse-primary) | **None** — A2 grades each row from scratch |
| Sheet | Combined `goaljudge_stage5_goldset_annotator1_sheet.csv` with `r1_*` columns | **Separate** `goaljudge_stage5_goldset_annotator2_sheet.csv` with only `r2_*` columns |
| Access to A1 labels | N/A (A1 was first) | **Forbidden** — see §9 firewall |
| Access to A1 override patterns table | N/A | **Forbidden** during labeling (read after submission only, if at all) |
| Batch run | A1 ran the rerun batch | A2 **does not** re-run — A1's corpus + UI capture is the shared evidence |
| Coordinator role | Active per-row confirm/override prompts | Hands-off until A2 submits |

The point of two independent raters is to measure *how much they agree without coordination*. Any
A1→A2 channel below the submission boundary inflates α toward 1 and invalidates the gate.

---

## 2. Locked design decisions

Captured 2026-06-11 (this session) via four AskUserQuestion prompts; all four chose the Recommended
option. Locking them here so the rest of the plan reads against a fixed design.

| # | Question | Decision | Rationale |
|---|---|---|---|
| 1 | A2 initial labels via semi-auto pre-fill or cold blind? | **Cold blind labeling** | Eliminates shared bias source between A1 and A2; cleanest α math. ~6–8 h labor cost is acceptable for the gating instrument. |
| 2 | Fix `len>80` false-positive heuristic before A2 starts? | **Fix first** (Task #65) | If we ever re-run the grader on A2's evidence (we won't, but defense-in-depth), the buggy heuristic is gone. Also closes A1 open item N-2; small spot-check on A1 rows the fixed heuristic flips. |
| 3 | How to shield A1's labels from A2? | **Separate sheet file** (`annotator2_sheet.csv`) | Strongest blindness: A1 columns aren't in the file A2 opens. Trivial to enforce — no Google Sheets ACL gymnastics, no honor-system hidden columns. |
| 4 | A1's 22 unflagged-row backfill before A2 starts? | **Skip; parallel-OK** | `r1_review_assessment` is documentation, not an agreement axis. A2 labels each of those 22 rows like every other row; if there's a disagreement at the α gate, the adjudicator walks both sides then. |

---

## 3. Session goal

Produce a **cold-blind Annotator 2 sheet** on the 79-row fresh corpus such that:

1. Every row has `r2_goal_met`, `r2_graceful_failure`, `r2_partial_fraction`, `r2_failure_mode`
   filled by direct human grading against Langfuse + UI evidence.
2. A2 never touched A1's labels, A1's review queue, or A1's override patterns.
3. A2 wrote a per-case rationale (analogous to the pilot's
   [`goaljudge_stage5_goldset_annotator2_results.md`](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_results.md))
   so the adjudicator and the post-α coverage check have audit trails on both sides.
4. The output is the input to
   [`compute_goaljudge_stage5_alpha.py --diff`](../../scripts/compute_goaljudge_stage5_alpha.py) for
   the Phase 5 round-1 α computation.

---

## 4. Plan overview

```mermaid
flowchart TD
  subgraph prereq [Phase A — Grader fix (Task #65; NOT in A2's labeling path)]
    A1["Gate has_tools+len>80 promotion<br/>on Langfuse goal_met=True"]
    A2["Re-run grader on A1 corpus;<br/>spot-check rows that flip"]
    A3["Unit test for new gate"]
  end
  subgraph build [Phase B — Build A2 sheet (coordinator)]
    B1["Generate annotator2_sheet.csv<br/>from template, 79 rows,<br/>r2_* columns ONLY"]
    B2["Embed evidence_summary<br/>from shared corpus sidecar"]
    B3["Verify NO r1_* columns present"]
  end
  subgraph label [Phase C — A2 cold-blind labeling]
    C1["For each row: read task + Langfuse trace + UI screenshot"]
    C2["Grade r2_goal_met (α axis) first,<br/>then graceful_failure / partial_fraction / failure_mode"]
    C3["Write per-case rationale into<br/>annotator2_results.md"]
  end
  subgraph handoff [Phase D — Handoff to α gate]
    D1["Coordinator merges r2_* into<br/>full_sheet.csv (combined)"]
    D2["compute_goaljudge_stage5_alpha.py<br/>--diff out.csv"]
    D3["If α ≥ 0.8 → Phase 5-F adjudicate.<br/>If < 0.8 → EvalGen revise loop (walkthrough §6)"]
  end
  A1 --> A2 --> A3 --> B1 --> B2 --> B3 --> C1 --> C2 --> C3 --> D1 --> D2 --> D3
```

**Evidence hierarchy (identical to A1; protocol identity is what makes α meaningful):**

| Priority | Source | Use |
|---|---|---|
| 1 (primary) | Langfuse trace — trajectory, `final_answer`, `eval.goal_judge` axes | Grade `goal_met`, `partial_fraction`, `failure_mode` |
| 2 (secondary) | Playwright `response_text` when UI admissible | Cross-check prose answer |
| — (inadmissible) | Status-feed-only DOM (`Using tools: …` with no substantive answer) | Langfuse-only; A2 should note `evidence-inadmissible-status-feed` in the row's note |

---

## 5. Phase A — Grader fix (engineering prereq)

> **Task #65.** This phase is NOT executed by A2 — it's a prereq that must land before Phase B
> opens. Listed here because it gates the start of A2's labeling.

### 5.1 Fix

`scripts/build_goaljudge_stage5_annotator1_fresh_sheet.py:521`:

```python
# BEFORE
if has_tools and len(substantive) > 80:
    return _finish_grade({"r1_goal_met": "true", "r1_partial_fraction": "1", ...})

# AFTER
lf_goal_met = (lf_eval or {}).get("goal_met")
if has_tools and len(substantive) > 80 and lf_goal_met is True:
    return _finish_grade({"r1_goal_met": "true", "r1_partial_fraction": "1", ...})
# If lf_goal_met is False or None, fall through to under-confident-review.
```

Why this gate: the bug was promoting rows to `goal_met=true` on *length alone* irrespective of
whether Langfuse's own goal-judge eval saw goal achievement. Gating on `lf_goal_met is True` makes
the promotion contingent on the primary evidence channel.

### 5.2 Spot-check A1 rows that flip — **RAN 2026-06-11**

Re-ran the fixed grader against the A1 corpus
(`corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl`); diffed against the A1 sheet. Report at
`cache/goaljudge_eval/a1_len80_fix_impact_report.md`. **Result:**

| Bucket | Count | Action |
|---|---|---|
| **Over-grades** (A1=true, fixed=false) | **14** | All 14 lack `r1_review_assessment` — these are R-6 candidates from the 22 unflagged rows |
| Under-grades (A1=false, fixed=true) | 2 | Both have `r1_review_assessment` — A1 actively overrode; human judgment is the authority, leave as-is |

The 14 over-grade R-6 candidates:

```
GJ-F-006  GJ-F-014  GJ-F-015  GJ-F-016  GJ-F-017  GJ-F-018  GJ-F-020
GJ-F-022  GJ-F-026  GJ-F-035  GJ-F-037  GJ-F-039  GJ-F-042  GJ-F-045
```

**Action policy (per §13 R-6):** do NOT modify A1's sheet pre-α. Route these to post-α
adjudication. The adjudicator opens the diff at Phase 5-F and uses this list to weight which
A2-vs-A1 disagreements are likely A1-side rather than A2-side. If α ≥ 0.8 with these 14 rows
in A1's `goal_met=true` state, the bias is contained within the adjudication budget; if α < 0.8
and these rows dominate the diff, the EvalGen revise loop (Phase 5-E) explicitly considers
re-labeling the unflagged A1 subset under the protocol.

### 5.3 Unit test

`tests/scripts/test_build_goaljudge_stage5_annotator1_fresh_sheet.py`:

```python
def test_len_gt_80_does_not_promote_when_langfuse_goal_met_false():
    # has_tools=True, len(substantive)=120, lf_eval={"goal_met": False}
    # → should fall through to under-confident-review, NOT goal_met=true
    ...
```

**Acceptance:** new test passes; existing tests still green; smoke re-run on A1 corpus produces a
fix-impact report (count of rows whose grader output flips, with item_ids listed).

---

## 6. Phase B — Build A2 blank sheet (coordinator)

> **Task #67.** Coordinator-only; A2 does not see the build process or A1 artifacts during this phase.

### 6.1 Source materials (shared with A1, NOT regenerated)

| Artifact | Path | Reuse policy |
|---|---|---|
| Authored task fixture | `tests/fixtures/goaljudge/fresh_test_tasks.py` | Read-only |
| UI batch JSONL | `cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl` | Read-only — **do NOT re-run Playwright** |
| Per-case screenshots | `cache/goaljudge_eval/ui_batch_screenshots_gcp_fresh_stage5_rerun_2026-06-10/` | Read-only |
| Langfuse corpus sidecar | `cache/goaljudge_eval/corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl` | Read-only |
| Sheet template | `docs/research/goaljudge_stage5_goldset/goaljudge_stage5_goldset_label_sheet_template.csv` | Column-contract source |

A2 must label against the SAME evidence A1 labeled against. Re-running the batch would create
trace-id drift and break the join at the α stage.

### 6.2 Output sheet shape

`docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv`:

```
item_id, split, provenance, stratum, domain, task, claim, evidence_summary,
r2_goal_met, r2_graceful_failure, r2_partial_fraction, r2_failure_mode,
r2_review_assessment, r2_review_open_question, note
```

**Explicitly excluded:** all `r1_*` columns, all `adjudicated_*` columns.

`evidence_summary` is the same trajectory + UI summary A1's sheet carries — built from the corpus +
UI JSONL, NOT copied from A1's sheet (to avoid any inadvertent A1-prose leak).

### 6.3 Build invocation (one-shot, coordinator side)

```bash
python scripts/build_goaljudge_stage5_annotator2_sheet.py \
  --batch cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl \
  --corpus cache/goaljudge_eval/corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl \
  --template docs/research/goaljudge_stage5_goldset/goaljudge_stage5_goldset_label_sheet_template.csv \
  --output docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv
```

> This script does **not yet exist** — it's a small variant of
> `build_goaljudge_stage5_annotator1_fresh_sheet.py` with the grader stripped out and
> r1_* columns replaced by r2_* columns. Adding it to Task #67's acceptance.

### 6.4 Sheet-shape assertion

Before handing to A2, run the row-count + column-set check:

```python
import csv
rows = list(csv.DictReader(open('docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv')))
assert len(rows) == 79, f"expected 79 rows, got {len(rows)}"
forbidden = {c for c in rows[0].keys() if c.startswith('r1_') or c.startswith('adjudicated_')}
assert not forbidden, f"forbidden A1/adjudicator columns present: {forbidden}"
required = {'r2_goal_met', 'r2_graceful_failure', 'r2_partial_fraction', 'r2_failure_mode'}
assert required.issubset(rows[0].keys()), f"missing r2_* columns: {required - rows[0].keys()}"
assert all(not r['r2_goal_met'] for r in rows), "r2_goal_met must be blank pre-labeling"
print('A2 sheet shape OK: 79 rows, r2_* only, all r2_goal_met blank')
```

---

## 7. Phase C — A2 cold-blind labeling

> **Task #60 (Phase 5-C of the master Phase 5 sequence).** This is the human-paced work.

### 7.1 Setup (A2's side)

A2 receives:
- The blank A2 sheet (`goaljudge_stage5_goldset_annotator2_sheet.csv`).
- Read access to the shared evidence bundle (Langfuse corpus JSONL + UI batch JSONL + screenshots dir).
- The protocol doc: [`full_set_labeling_protocol.md`](../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md).
- The fresh-task authoring guide: [`fresh_task_authoring_guide.md`](../research/goaljudge_stage5_goldset/fresh_task_authoring_guide.md)
  — to understand what each row's stratum and `expected_failure_mode` were authored to test.
- This plan, except for §10 (which references A1 patterns) — coordinator should give A2 §1–§9
  trimmed at §10 until after submission.

A2 does **NOT** receive:
- A1's sheet (`goaljudge_stage5_goldset_annotator1_sheet.csv`).
- A1's review queue (`goaljudge_stage5_goldset_annotator1_review_queue.md`).
- A1's session plan (`goaljudge_stage5_fresh_a1_labeling_session.plan.md`).
- This plan's §10 (override patterns derived from A1).

### 7.2 Per-row procedure

For each `item_id` (79 total, GJ-F-001 … GJ-F-105 with §6 gaps):

1. **Read the task.** From `tests/fixtures/goaljudge/fresh_test_tasks.py` look up the authored
   `task`, `stratum`, `expected_tool_cluster`, `expected_failure_mode`. The `expected_*` fields
   are *what the authoring intended* — A2 grades what the agent actually did, not the intent.
2. **Open the Langfuse trace.** Trajectory + `final_answer` + `eval.goal_judge` axes.
3. **Open the UI screenshot.** Confirm whether the DOM is admissible (substantive answer beyond
   status-feed prefix) or status-feed-only (inadmissible — Langfuse-only).
4. **Grade in α-axis order:**
   - `r2_goal_met` first (the α axis — the one number that matters for the gate).
   - Then `r2_graceful_failure`, `r2_partial_fraction` (use the ±0.05 spec band; see §10),
     `r2_failure_mode` (must be a `GOAL_FAILURE_MODES` code or blank).
5. **Write `r2_review_assessment`:** evidence summary + rationale, 1–3 sentences.
6. **Write `r2_review_open_question`:** `Resolved: …` or an open question for the adjudicator.
7. **`note`:** append any flags A2 thinks the adjudicator should know about
   (`evidence-inadmissible-status-feed`, etc.).

### 7.3 A2 cadence guidance

- ~6–8 h total expected labor (~4–6 min/row).
- Take a break every 20 rows; fatigue is the #1 IAA killer.
- If a row genuinely can't be graded with confidence after reading both evidence channels, mark
  `r2_goal_met` with best guess and note `low-confidence` in `r2_review_open_question` — the α
  computation needs a label on every row, and the adjudicator will resolve.

### 7.4 Per-case rationale doc (mirror of A1's results doc)

A2 writes `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_fresh_results.md`
(named to disambiguate from the pilot's `goaljudge_stage5_goldset_annotator2_results.md`),
with the same shape as the pilot doc: summary table + per-case verdict + 1–3 sentence rationale.
This is the audit trail.

> **Important.** The per-case rationale doc is written FROM A2's grading notes only — A2 must not
> read A1's `r1_review_assessment` while drafting this doc.

---

## 8. Phase D — A2 results doc + handoff to α gate

### 8.1 Coordinator merges A1 + A2 into combined sheet

```python
import csv
a1 = {r['item_id']: r for r in csv.DictReader(open('docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator1_sheet.csv'))}
a2 = {r['item_id']: r for r in csv.DictReader(open('docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv'))}
assert set(a1.keys()) == set(a2.keys()) == 79  # same 79 item_ids on both sides
# write to goaljudge_stage5_goldset_full_sheet.csv with both r1_* and r2_* columns
```

The combined sheet is the input to the α script.

### 8.2 Compute round-1 α + disagreement diff

```bash
python scripts/compute_goaljudge_stage5_alpha.py \
  docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
  --diff cache/goaljudge_eval/stage5_round1_diff.csv
```

**Outcomes:**

| α | Band | Action |
|---|---|---|
| ≥ 0.81 | Almost perfect | Proceed to adjudicate disagreements only (Phase 5-F) |
| 0.80 ≤ α < 0.81 | Right at gate | Same as above — gate is α ≥ 0.8 inclusive |
| 0.667 ≤ α < 0.80 | Substantial but below gate | EvalGen revise loop (walkthrough §6) on disagreement rows only |
| < 0.667 | Below tentative-conclusions floor | Escalate; protocol or rubric issue beyond rule-tightening |

### 8.3 If α ≥ 0.8 — feed Phase 5-F

Hand `stage5_round1_diff.csv` and the combined full sheet to the adjudicator (Phase 5-F per the
walkthrough). Adjudication produces `adjudicated_goal_met` / `adjudicated_failure_mode`. Then
Phase 5-G (post-α coverage check) and Phase 6 assembly.

### 8.4 If α < 0.8 — EvalGen revise on disagreement rows only

Per walkthrough §6: triage disagreements into idiosyncratic / recurring-pattern / authoring-defect
piles. Revise rule(s) if a pattern emerges. Re-label **only the disagreement rows** (NOT the full
79) under the revised rule. Recompute α. At most 2 revise loops before escalation.

---

## 9. Blindness firewall — non-negotiable

This section exists because protocol drift here invalidates the α number silently.

### 9.1 What A2 must NOT see during labeling

| Artifact | Why it leaks |
|---|---|
| `goaljudge_stage5_goldset_annotator1_sheet.csv` | Direct label leak |
| `goaljudge_stage5_goldset_annotator1_review_queue.md` | Tells A2 which rows A1 found ambiguous |
| `goaljudge_stage5_fresh_a1_labeling_session.plan.md` §7.3 (override patterns) | Tells A2 how A1 resolved ambiguity — A1's calibration becomes A2's prior |
| §10 of THIS plan (carries the same override patterns) | Same leak as above |
| Any Slack/chat thread where A1 discussed specific item_ids | Direct label leak |
| Adjudicated columns from prior labeling (none exist here — fresh corpus) | Would be a direct truth leak |

### 9.2 What A2 may see

| Artifact | Why it's safe |
|---|---|
| The protocol doc (`full_set_labeling_protocol.md`) | Shared protocol — same rules both annotators reason under |
| The fresh-task authoring guide | Same |
| The Phase 5 walkthrough §3–§5 (annotator brief + protocol) | Same |
| THIS plan §1–§9 (the structural plan; §10 trimmed) | §10 onward references A1 patterns; trim before sharing |
| The shared evidence bundle (Langfuse + UI + screenshots) | Same evidence A1 saw |
| The fresh-task fixture (`fresh_test_tasks.py`) | Same — authored intent is shared, observed grade is independent |

### 9.3 Coordinator-side enforcement

- The A2 sheet file is generated from the template + corpus, NOT from A1's sheet. (§6.4 assertion.)
- The coordinator does NOT discuss specific item-ids with A2 during labeling.
- If A2 asks a procedural question ("how do I grade an impossible-stratum row where the agent
  fabricated?"), the coordinator answers from the protocol doc, NOT from A1's session log.

### 9.4 Post-submission

Once A2 has submitted `r2_*` for all 79 rows AND written the rationale doc, the firewall lifts.
A2 may then read A1's sheet, the review queue, the override patterns table — useful for the
EvalGen loop if α < 0.8. Pre-submission, all forbidden.

---

## 10. Grading protocol applied (same as A1)

> ⚠️ **DO NOT share this section with A2 before submission.** The patterns below were derived
> from A1's overrides. Sharing them would calibrate A2 toward A1 and inflate α.

The same five rules from [`full_set_labeling_protocol.md`](../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md)
that drove A1's overrides will drive A2's:

| Rule | Application |
|---|---|
| **Rule 6 (messy English)** | Charitable reading; don't mark `goal_met=false` for parse difficulty alone. |
| **Rule 7 (wrong-tool)** | Grade what the agent **did with the evidence**, not instruction compliance. `ls` cannot verify file contents. |
| **Impossible stratum** | `impossible-task-reported` + `graceful_failure=true` only when agent honestly reports impossibility **without fabrication**. Fabrication → `fabricated-progress`. |
| **Evidence hierarchy** | Langfuse trajectory primary; UI secondary when admissible; status-feed-only inadmissible. |
| **Partial synthesis** | Multi-part tasks with incomplete branches → `incomplete-synthesis`, `partial_fraction` per verified subtasks; respect the ±0.05 spec band. |

### Representative A1 override patterns (FOR ADJUDICATOR + post-α audit ONLY)

| Pattern | Example | A1's override |
|---|---|---|
| Semi-auto false positive (`ui_admissible + has_tools + len>80`) | GJ-F-099 | `goal_met=false`, `failure_mode=incomplete-synthesis` |
| Impossible stratum: fabricated vs honest report | GJ-F-101, GJ-F-103 | `failure_mode=fabricated-progress` (not `impossible-task-reported`) |
| Langfuse `graceful_failure=False` on honest impossible report | GJ-F-102, GJ-F-104, GJ-F-105 | Human override `graceful_failure=true` per protocol |
| Wrong-tool + file missing, no fabrication | GJ-F-105 | `impossible-task-reported` + `graceful_failure=true` |

These patterns are useful for the adjudicator at Phase 5-F to recognize systemic protocol issues
in the diff. They MUST NOT be shown to A2 before submission.

---

## 11. What A2 does NOT do

- Does **NOT** re-run the Playwright batch (Phase 5-B). Reuses A1's `ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl`.
- Does **NOT** re-export the Langfuse corpus. Reuses `corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl`.
- Does **NOT** modify A1's sheet, review queue, or results doc.
- Does **NOT** touch any production config or deploy anything.
- Does **NOT** use the semi-auto grader for pre-fill (decision #1).
- Does **NOT** read A1's labels, review queue, or override patterns until after submission (§9).
- Does **NOT** backfill A1's 22 unflagged-row assessments — that's an optional A1-side parallel task (decision #4).

---

## 12. Verification gates

### 12.1 Phase A gates (engineering, before A2 starts)

```bash
# 1. Grader fix unit test
.venv/bin/python -m pytest tests/scripts/test_build_goaljudge_stage5_annotator1_fresh_sheet.py::test_len_gt_80_does_not_promote_when_langfuse_goal_met_false -q

# 2. Existing grader tests still green
.venv/bin/python -m pytest tests/scripts/test_build_goaljudge_stage5_annotator1_fresh_sheet.py -q

# 3. Fresh corpus drift-guard still green
.venv/bin/python -m pytest tests/services/test_fresh_task_authoring.py -q
```

### 12.2 Phase B gates (A2 sheet shape)

```bash
.venv/bin/python -c "
import csv
rows = list(csv.DictReader(open('docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv')))
assert len(rows) == 79
forbidden = {c for c in rows[0].keys() if c.startswith('r1_') or c.startswith('adjudicated_')}
assert not forbidden, forbidden
assert all(not r['r2_goal_met'] for r in rows)
print('A2 sheet shape OK')
"
```

### 12.3 Phase C gates (A2 submission completeness)

```bash
.venv/bin/python -c "
import csv
rows = list(csv.DictReader(open('docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv')))
gjf = [r for r in rows if r['item_id'].startswith('GJ-F-')]
assert len(gjf) == 79
assert all(r['r2_goal_met'] in {'true', 'false'} for r in gjf), 'all r2_goal_met must be true/false'
assert all(r['r2_graceful_failure'] in {'true', 'false'} for r in gjf)
assert all(r['r2_partial_fraction'] for r in gjf)
print('A2 submission OK:', len(gjf), 'rows, all r2_goal_met filled with true/false')
"
```

### 12.4 Phase D gates (α computation)

```bash
# α + diff
python scripts/compute_goaljudge_stage5_alpha.py \
  docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
  --diff cache/goaljudge_eval/stage5_round1_diff.csv

# Expected: PASS at α ≥ 0.8 (if α < 0.8, drop to EvalGen revise loop per §8.4)
```

---

## 13. Open items / risks

| ID | Item | Mitigation |
|---|---|---|
| R-1 | A2 accidentally sees A1's sheet via OS file picker / IDE recents | Coordinator stores A1 artifacts under a path A2 doesn't watch; A2 opens A2 sheet by absolute path |
| R-2 | A2 reads §10 of this plan before submission | Coordinator shares a trimmed copy (§1–§9 only) until A2 submits |
| R-3 | A2 fatigue → systematic late-row drift toward `goal_met=true` (path of least resistance) | §7.3 cadence guidance; coordinator does NOT pressure for completion time |
| R-4 | Langfuse trace missing for any row (corpus join gap) | A1 ran `verify_run.py 79/79` — should be zero. If a row is now missing, escalate before A2 grades that row |
| R-5 | A2 disagrees with the protocol on a systemic axis (e.g., wrong-tool grading) | A2 notes disagreement in `r2_review_open_question`; surfaces at α-gate diff; adjudicator + EvalGen handle |
| R-6 | A1's len>80 false-positive flipped some r1 grades that A1 didn't review (22 unflagged rows) | Phase A §5.2 spot-check; if any item_ids surface as buggy-r1 candidates, route to post-α adjudication, NOT to a pre-α A1 re-grade (would itself be a bias channel) |

---

## 14. Implementation checklist

| ID | Task | Owner | Status |
|---|---|---|---|
| #65 | Fix `len>80` heuristic + add gate test | Engineering | **done ✓** |
| #65a | Spot-check A1 rows that flip under fixed grader (14 R-6 over-grade candidates surfaced; routed to post-α adjudication per §5.2) | Coordinator | **done ✓** |
| #66 | This plan landed | Coordinator | **in_progress** |
| #67 | Build `goaljudge_stage5_goldset_annotator2_sheet.csv` + sheet-shape assertion (79 rows, all r2_* blank, no r1_*/adjudicated_* columns) | Coordinator | **done ✓** |
| #67a | Add `scripts/build_goaljudge_stage5_annotator2_sheet.py` (grader stripped; 8/8 L2 contract tests in `tests/scripts/test_build_goaljudge_stage5_annotator2_sheet.py`) | Engineering | **done ✓** |
| #60 | A2 cold-blind labeling (79 rows) | Annotator 2 | pending (blocked by #67) |
| #60a | A2 writes `goaljudge_stage5_goldset_annotator2_fresh_results.md` | Annotator 2 | pending |
| #61 | Coordinator merges A1+A2 into `full_sheet.csv`; runs α + diff | Coordinator | pending |
| #62 | (conditional) EvalGen revise loop on disagreement rows | Both annotators | pending |
| #63 | Adjudicate `adjudicated_goal_met` / `adjudicated_failure_mode` | Adjudicator | pending |
| #64 | Post-α coverage check (`evaluate_goldset_post_alpha_coverage`); hand to Phase 6 | Coordinator | pending |

---

## References

- [A1 session plan (sibling round, reference for plan structure)](goaljudge_stage5_fresh_a1_labeling_session.plan.md)
- [Phase 5 live labeling walkthrough](../research/goaljudge_stage5_goldset/phase5_live_labeling_walkthrough.md)
- [Full-set labeling protocol](../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md)
- [Fresh-task authoring guide](../research/goaljudge_stage5_goldset/fresh_task_authoring_guide.md)
- [Tier 3 assembly plan Phase 5](goaljudge_stage5_tier3_assembly.plan.md#phase-5--full-double-labeling--α-gate-medium-human-paced)
- [Goldset README](../IAA/goalJudge/goldset/README.md)
- [Pilot A2 results doc (shape reference for §7.4)](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_results.md)
- [Fresh task fixture](../../tests/fixtures/goaljudge/fresh_test_tasks.py)
- [α script](../../scripts/compute_goaljudge_stage5_alpha.py)
- [Assembly script (Phase 6 entry)](../../scripts/assemble_goaljudge_goldset.py)
