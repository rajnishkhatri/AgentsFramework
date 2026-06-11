# Phase 5 — Live double-label & α ≥ 0.8 walkthrough

> **What this is.** The **runbook** for Phase 5 of the [Tier 3 assembly plan](../../plans/goaljudge_stage5_tier3_assembly.plan.md): two annotators blind-label the frozen 79-row fresh-task corpus, we compute Krippendorff's α on `goal_met`, and on α ≥ 0.8 the adjudicated column becomes `goaljudge_goldset_v1`'s gold truth (hands off to Phase 6 assembly).
> **What this is *not*.** The **rulebook** for *how* to label — the seven refined rules + decision tree + evidence hierarchy live in [`full_set_labeling_protocol.md`](full_set_labeling_protocol.md). The annotators read **that** doc; this doc is for **the coordinator** running the round.
> **Phase status assumed.** Phase 4-authoring **closed** (2026-06-10): 79 rows in `tests/fixtures/goaljudge/fresh_test_tasks.py`, drift-guard 161/161 PASS, stratum distribution within ±10 % of all four targets, labeling protocol Rules 1–7 published, authoring guide §3.1 reconciled with Rule 7. Pilot Phase 5 (Tier 1, ~50 items) **closed** at α = 0.8846 PASS ([results](../../IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md)).
> **Locked design decisions.**
> - **Annotators:** 2 raters on the full 79 rows. Krippendorff α on the binary `goal_met` axis (the L1 helper handles the 2-rater complete-data case as Cohen's κ; live code-path is the same).
> - **Tooling:** Google Sheet with two tabs (one per annotator) pre-populated from the full-sheet CSV. Annotators do not see each other's columns. Coordinator exports back to CSV for α computation.
> - **α-miss path:** EvalGen revise loop on disagreement rows only. If a pattern emerges across disagreements that the protocol does not already disambiguate, add **Rule 8** and re-label only the affected rows.
> **Owner.** Phase-5 coordinator (one human). Annotators are A1 and A2 — same pair as the pilot.
> **Estimated effort.** ~6–8 h per annotator (one focused day). ~1 h coordinator overhead for sheet setup + α/diff exports. Round-2 revise loop adds ~1–2 h per annotator on disagreement rows only.
> **Last reviewed.** 2026-06-10 (Phase 4 close).

---

## TL;DR — the loop in one screen

```
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 5 = ONE α NUMBER ON THE FROZEN 79-ROW CORPUS                      │
│                                                                          │
│  1. Build full-sheet CSV from corpus + GCP sidecars  (coord, ~10 min)    │
│  2. Upload to Google Sheets, split into A1 / A2 tabs (coord, ~10 min)    │
│  3. Both annotators label blind                       (~6-8 h each)      │
│  4. Coordinator exports CSVs, runs α + --diff         (coord, ~5 min)    │
│  5a.  α ≥ 0.8 → adjudicate disagreements, freeze, hand to Phase 6        │
│  5b.  α < 0.8 → EvalGen revise loop on disagreement rows only;           │
│                 if pattern: add Rule 8; re-label only those rows; re-α    │
│                                                                          │
│  Repeat 5b at most twice. Three rounds without α ≥ 0.8 ⇒ escalate         │
│  (rubric ambiguity in the cells the disagreement keeps lighting up).     │
└──────────────────────────────────────────────────────────────────────────┘
```

The α gate is the **only** number Phase 5 produces. Everything below is sequencing the work that produces it.

---

## 1. Prerequisites — confirm Phase 4 is in place

Run once before kicking off the round; these confirm nothing has rotted since Phase 4 closed.

```bash
# (a) the 79-row corpus still passes the drift-guard
.venv/bin/python -m pytest tests/services/test_fresh_task_authoring.py -q

# (b) the α / disagreement-diff helpers are importable from L1
.venv/bin/python -c "
from services.governance.iaa import (
    krippendorff_alpha_nominal,
    landis_koch_band,
    normalize_bool_label,
    compute_disagreement_diff,
    apply_adjudication,
)
from services.governance.goaljudge_goldset_dataset import (
    evaluate_goldset_post_alpha_coverage,
)
print('iaa + dataset helpers OK')
"

# (c) the α CLI works on the pilot sheet (sanity check; expect α=0.8846)
.venv/bin/python scripts/compute_goaljudge_stage5_alpha.py \
  docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv
```

If any of those three fail, **stop and fix Phase 4 (a) or the L1 iaa module (b, c) before scheduling annotators.** Annotators are slow and expensive; you cannot afford to discover a broken α script after they've spent a day labeling.

---

## 2. Build the full-sheet CSV

The full-sheet builder ([`scripts/build_goaljudge_stage5_full_sheet.py`](../../../scripts/build_goaljudge_stage5_full_sheet.py)) joins:

- UI-batch JSONL sidecars (one per Playwright GCP run — identity columns: `case_id`, `trace_id`, `session_id`, `prompt`, `response_text`)
- Corpus JSONL sidecar (behavior column: `trajectory[]` → `tool_calls_summary` via `services.governance.goaljudge_goldset_dataset.project_trajectory_tools`)
- The 79-row authored fresh-task corpus (`FRESH_TEST_TASKS`) for the test-split items not on production traces

It emits a sheet with the blank-label columns from [`goaljudge_stage5_goldset_label_sheet_template.csv`](goaljudge_stage5_goldset_label_sheet_template.csv) — the column contract Phase 5 commits to.

```bash
.venv/bin/python scripts/build_goaljudge_stage5_full_sheet.py \
  --batches cache/goaljudge_eval/ui_batch_gcp_2026-06-09.jsonl,cache/goaljudge_eval/ui_batch_gcp_confirmation_2026-06-09_v7_full.jsonl \
  --corpus  cache/goaljudge_eval/corpus_gcp_goldset_pilot_2026-06-09.jsonl \
  --fresh-tasks \
  --output  docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
  --report  cache/goaljudge_eval/goldset_cell_coverage_report.md
```

> **`--fresh-tasks` flag.** As of Phase 4 close, the builder must read `FRESH_TEST_TASKS` directly (the test split is authored synthesis, not production traces). If this flag does not yet exist in your tree, see §8 *Known gaps* below — wiring it is a one-line `from tests.fixtures.goaljudge.fresh_test_tasks import FRESH_TEST_TASKS` extension in the builder's row-loader and is on the §10 backlog.

**Acceptance** (run before sharing the sheet with annotators):

```bash
.venv/bin/python -c "
import csv
rows = list(csv.DictReader(open('docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv')))
# all 79 fresh items present
assert len([r for r in rows if r['item_id'].startswith('GJ-F-')]) == 79, len(rows)
# blank r1_/r2_/adjudicated_ columns
for r in rows[:3]:
    assert r['r1_goal_met'] == '' and r['r2_goal_met'] == ''
# stratum + D5 cluster populated (Phase 3 plumbing)
assert all(r['stratum'] for r in rows)
print('full sheet OK; rows=', len(rows))
"
```

If a row is missing a stratum or cluster value, the builder dropped it silently — investigate before continuing.

### 2b. Fresh-task batch rerun + Annotator 1 semi-automated grading (mandatory)

The June 10 initial fresh batch ran against **undeployed** saturation-bridge middleware, so Playwright `trace_id`s did not join Langfuse. **Do not grade from that JSONL.** Re-run with a new tag after deploying the bridge fix.

**Sub-steps (coordinator):**

1. **Deploy saturation bridge fix** (ships in `agent-backend-combined`):

   ```bash
   WRITE_TFVARS=1 ./scripts/deploy_gcp.sh images
   AUTO_APPROVE=1 ./scripts/deploy_gcp.sh backend
   ```

   Smoke one case (`GJ_CASE_FILTER=GJ-F-001 GOALJUDGE_BATCH_MODE=fresh`) and confirm Cloud Logging emits `goaljudge_saturation case=GJ-F-001 trace=<uuid5 hex>`.

2. **Re-run the 79-case fresh Playwright batch** (new JSONL tag — do not overwrite the broken run):

   ```bash
   GOALJUDGE_BATCH_MODE=fresh \
   GOALJUDGE_BATCH_JSONL=../cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl \
   GOALJUDGE_BATCH_SCREENSHOT_DIR=../cache/goaljudge_eval/ui_batch_screenshots_gcp_fresh_stage5_rerun_2026-06-10 \
   cd frontend && pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts --project=chromium-desktop
   ```

   Post-run gate:

   ```bash
   python docs/skills/playwright-agentic-e2e/scripts/verify_run.py \
     --jsonl cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl \
     --dedupe --expect-cases 79 --id-namespace dns
   ```

3. **Export Langfuse corpus sidecar** (coverage gate: 79/79 trace rows):

   ```bash
   python scripts/export_goaljudge_corpus.py \
     --user-id synthetic-saturation-user \
     --trace-ids-from-jsonl cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl \
     --hours 4 \
     --out cache/goaljudge_eval/corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl
   ```

4. **Build Annotator 1 sheet** (Langfuse-primary, `--corpus` required):

   ```bash
   python scripts/build_goaljudge_stage5_annotator1_fresh_sheet.py \
     --batch cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl \
     --corpus cache/goaljudge_eval/corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl \
     --sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
     --output docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator1_sheet.csv \
     --report docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator1_review_queue.md
   ```

5. **Human-review flagged rows** in `goaljudge_stage5_goldset_annotator1_review_queue.md` (wrong-tool, impossible, status-feed-only Langfuse rows). Cite Langfuse `trace_id` + trajectory tools in `note`; append `human-reviewed` when confirmed.

   ```bash
   python scripts/apply_goaljudge_stage5_annotator1_fresh_review.py \
     --sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator1_sheet.csv \
     --batch cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl \
     --corpus cache/goaljudge_eval/corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl
   ```

**Evidence hierarchy:** Langfuse trajectory + eval axes primary; Playwright `response_text` secondary; status-feed-only UI inadmissible (see [`full_set_labeling_protocol.md`](full_set_labeling_protocol.md) §3).

---

## 3. Set up the Google Sheet

The CSV becomes a Google Sheet with **two tabs**, one per annotator. The blind-labeling constraint is enforced by tab access, not by row-level redaction — Sheets does not have per-column ACLs.

| Tab | Audience | Visible columns | Hidden columns |
|---|---|---|---|
| `r1_labels` | Annotator A1 only | `item_id`, `provenance`, `stratum`, `domain`, `task`, `claim`, `evidence_summary`, `r1_goal_met`, `r1_graceful_failure`, `r1_partial_fraction`, `r1_failure_mode`, `note` | every `r2_*` and `adjudicated_*` |
| `r2_labels` | Annotator A2 only | same as above but with `r2_*` columns | every `r1_*` and `adjudicated_*` |
| `coordinator` | Coordinator only | full CSV (read-only mirror) | — |

Mechanics (~10 min):

1. Upload the CSV via **File → Import**.
2. Duplicate the imported tab twice; rename to `r1_labels` and `r2_labels`.
3. On `r1_labels`, hide every `r2_*` and `adjudicated_*` column (right-click → **Hide column**).
4. Mirror on `r2_labels` (hide `r1_*` and `adjudicated_*`).
5. **Share** the sheet two ways: A1 gets edit access to the whole document but is asked to only edit `r1_labels`; A2 the mirror. (Sheets honors hidden columns visually but does not deny edit access — the discipline is in the brief, not the ACL. This is acceptable because both annotators are trusted; the goal of blindness is to prevent anchoring, not to prevent collusion.)
6. **Lock** every column that isn't a label column on the corresponding tab (right-click → **Protect range** → **Show a warning when editing this range**). This catches a slip where an annotator edits the prompt instead of their label cell.

Drop two named-range validations to prevent typos:

| Column | Validation |
|---|---|
| `r{1,2}_goal_met` | List from: `true,false` |
| `r{1,2}_graceful_failure` | List from: `true,false` |
| `r{1,2}_partial_fraction` | Number between `0` and `1`, with step `0.05` (matches Stage 4 Phase A spec band; arbitrary numerics force the adjudicator to round later) |
| `r{1,2}_failure_mode` | List from: `A1,A2,A3,A4,A5,A6,A7,A8,fluent-evasion,fabricated-progress,graceful-failure-honest,partial-counted-as-full,right-answer-wrong-process,impossible-task-reported,goal-met-but-unsafe-wasteful,` (blank for `goal_met=true`) |

(The full failure_mode vocabulary lives in `services.governance.goaljudge_goldset_dataset.GOAL_FAILURE_MODES`; copy from source to avoid drift.)

---

## 4. The annotator brief

Send this verbatim to A1 and A2 when you share the sheet:

> **Phase 5 labeling kickoff.**
>
> 1. Re-read [`full_set_labeling_protocol.md`](full_set_labeling_protocol.md) **end to end** before you label your first row. Rules 6 (intentional non-native English) and 7 (`wrong-tool` semantics) are **new since the pilot** — they will catch you out if you do not read them.
> 2. Open your tab (`r{1,2}_labels`). Do not switch tabs.
> 3. For each row, label `goal_met` first (this is the α axis — every other column is metadata). Then fill `graceful_failure`, `partial_fraction`, `failure_mode`.
> 4. The evidence hierarchy is **Langfuse trace primary, Playwright `response_text` secondary, status-feed-only inadmissible** (Stage 4 spec §8.3). If the row's `evidence_summary` is inadmissible, mark `goal_met=false` with `note=evidence-inadmissible`.
> 5. If a prompt is **intentionally messy English** (Rule 6 signature: sustained informal register, code-switched closers), grade the charitable reading. Do not mark `goal_met=false` because the prompt is hard to parse.
> 6. If a prompt prescribes a tool (`wrong-tool` cluster), Rule 7 says: grade what the agent **did with the evidence**, not whether the agent **followed the instruction**. A `ls` cannot verify `debug=true` in a file regardless of who told the agent to use it.
> 7. The `note` column is yours. Use it to flag any row where you were under-confident, found an authoring typo (`authoring-typo-found`), or thought the prompt was genuinely ambiguous (`prompt-ambiguous-charitable-reading-failed`). The adjudicator reads every note.
> 8. **You do not see each other's labels.** This is the blindness constraint. Do not coordinate during the round.
> 9. Estimated time: 6–8 h. Take breaks; α suffers if you label fatigued. A common pattern is two 3 h sessions on consecutive days.
>
> When done, ping the coordinator. Do not edit your tab after that ping — round 1 is closed at the timestamp.

---

## 5. Compute round-1 α + the disagreement diff

Coordinator: once both tabs are checked in, export each tab to CSV (one CSV with both `r1_*` and `r2_*` columns merged is simplest — Sheets' **File → Download → Comma-separated values** on a coordinator-owned merged tab).

```bash
# (a) compute α and emit the disagreement diff in one go
.venv/bin/python scripts/compute_goaljudge_stage5_alpha.py \
  docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
  --diff cache/goaljudge_eval/stage5_full_alpha_disagreements_r1.csv

# expected output shape:
#   rows=79 agreements=N alpha=X.XXXX band=...
#   gate=PASS|FAIL (threshold α ≥ 0.8)
#   wrote disagreement diff (N rows) to cache/goaljudge_eval/stage5_full_alpha_disagreements_r1.csv
```

| α | Action |
|---|---|
| `≥ 0.81` | "Almost perfect" band — proceed to §7 *Adjudicate + freeze*. |
| `0.80 ≤ α < 0.81` | At the gate. Proceed to adjudication; flag for Stage 6 if calibration P/R/F1 looks off. |
| `0.667 ≤ α < 0.80` | **FAIL the gate** but above the tentative-conclusions floor. Run §6 *EvalGen revise loop*. |
| `α < 0.667` | **FAIL the gate** and below the tentative-conclusions floor. Run §6, but the protocol is probably under-specifying a recurring case (see §8 escalation guide). |

Record the round-1 number in [`docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_results.md`](../../IAA/goalJudge/goldset/goaljudge_stage5_goldset_results.md) immediately — every round is a row in that file.

---

## 6. EvalGen revise loop (round 2)

Fires only if round-1 α < 0.8. The principle (EvalGen co-construction): **revise the rubric on the rows that surfaced disagreement, then re-label only those rows.** Throwing away round-1 labels is wasteful and risks anchoring bias on round 2 (Stage 4 lesson).

### 6.1 Triage the diff

The `--diff` CSV has shape `item_id,r1,r2`. Open it alongside the full sheet (so you can see each disagreement row's prompt, evidence, and both annotators' `failure_mode` + `note`).

Sort the diff into three piles:

| Pile | Definition | Action |
|---|---|---|
| **(a) idiosyncratic** | A single row where one annotator misread the evidence. No pattern across rows. | Round-2 label only; no protocol change. |
| **(b) recurring pattern** | ≥3 rows where the same axis of ambiguity recurs (e.g., "does a graceful-failure prompt that the agent attempted *and failed safely* count as `goal_met=false` + `graceful_failure=true`?"). | Add **Rule 8** to the labeling protocol. Document the pattern, the disambiguation, and a worked example. **Both** annotators re-label the affected rows after reading the new rule. |
| **(c) authoring defect** | The row is genuinely ambiguous because the prompt is bad, not because the rubric is. | Mark the row `superseded` in the results doc. Do not re-label. Document the defect in the Phase 6 manifest's `excluded_items[]`. |

### 6.2 Add Rule 8 (only if pile (b) is non-empty)

If a recurring pattern emerges, extend `full_set_labeling_protocol.md` with **Rule 8**. The shape mirrors Rules 6 and 7:

1. One-sentence headline — what the rule disambiguates.
2. The **signature** that triggers it (so future annotators recognize the case).
3. The **grading procedure** — what the rubric grades.
4. A **worked example** lifted from a round-1 disagreement row (with the diff CSV cited so future maintainers can trace the rule back to its origin).
5. An **escape valve** — what to write in `note` if the rule still does not disambiguate (so round-3 disagreement does not get silently masked).

Update §2 of the protocol from "seven rules" → "eight rules" with a one-line preface. Do **not** renumber Rules 1–7.

### 6.3 Re-label only the affected rows

For each annotator:

1. Coordinator hands them a **filtered view** of the sheet — only their tab rows whose `item_id` is in the diff CSV (or in the rows newly covered by Rule 8).
2. Annotator sees only the prompt, evidence, and their own (now-blank) label columns. They do **not** see their round-1 labels (anchoring would lock in the disagreement).
3. They label fresh, citing Rule 8 in `note` if it applied.

### 6.4 Re-compute α

Merge round-2 labels back into the merged-coordinator CSV (replacing the round-1 labels on those rows only). Re-run the α script:

```bash
.venv/bin/python scripts/compute_goaljudge_stage5_alpha.py \
  docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
  --diff cache/goaljudge_eval/stage5_full_alpha_disagreements_r2.csv
```

Record the round-2 number in `goaljudge_stage5_goldset_results.md` (new row). If α ≥ 0.8 now: proceed to §7. If still failing and a *different* pattern emerges: at most one more revise loop (round 3). Three rounds without α ≥ 0.8 ⇒ §8 *escalation*.

> **Why "disagreement rows only" not "everyone re-labels everything".** Two reasons:
> 1. **Cost.** Re-labeling 79 rows after Rule 8 lands costs another 6–8 h × 2; re-labeling the ~5–15 disagreement rows costs ~30 min × 2. Same gate signal.
> 2. **Inference cleanliness.** Round-1 agreements are by definition not affected by Rule 8 (the rule by construction targets disagreements). Re-labeling them risks introducing **new** disagreements from annotator drift, which is not what we want the gate to measure.
>
> The EvalGen literature (`research/evalgen_eval_co_construction.md` §2.3) calls this "targeted criterion refinement" and it is the standard practice; full re-label is the conservative fallback when round 2 stays under α = 0.667.

---

## 7. Adjudicate + freeze gold labels

Fires once α ≥ 0.8 on `goal_met`.

### 7.1 Walk every disagreement row

For each row in the most recent `stage5_full_alpha_disagreements_r{N}.csv`:

1. Coordinator (or a senior reviewer with axis-A expertise) reads the prompt, evidence, and both annotators' label + note + failure_mode + partial_fraction.
2. Picks one label for `goal_met` (this is the gold value).
3. Picks one label for `failure_mode` (blank if `goal_met=true`).
4. Picks `partial_fraction` (average of the two if within ±0.05 spec band; otherwise side with the annotator whose `note` cites the evidence more concretely).
5. Writes the chosen values to `adjudicated_goal_met`, `adjudicated_failure_mode`, `adjudicated_partial_fraction` on the coordinator tab.
6. Logs the **adjudication reason** in `adjudicated_note` (one sentence — "agreed with A2 because the langfuse trace confirms the tool call returned an error and the agent did not retry").

### 7.2 Spec-band check (partial_fraction)

Per Stage 4 Phase A, `partial_fraction` is graded with a ±0.05 spec band. After adjudication:

```bash
.venv/bin/python -c "
import csv
rows = [r for r in csv.DictReader(open('docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv')) if r['adjudicated_partial_fraction']]
bad = []
for r in rows:
    r1 = float(r['r1_partial_fraction'] or 0)
    r2 = float(r['r2_partial_fraction'] or 0)
    adj = float(r['adjudicated_partial_fraction'])
    if abs(adj - (r1+r2)/2) > 0.10:  # 2x the band = serious skew
        bad.append((r['item_id'], r1, r2, adj))
print('out-of-band:', len(bad))
for b in bad: print(b)
"
```

Any out-of-band row is a flag: either the adjudicator over-rode both annotators (justifiable but requires `adjudicated_note` to explain why) or the annotators had a systemic skew the EvalGen loop missed.

### 7.3 Post-α coverage check

The post-α check filters down to `adjudicated_goal_met=false` rows and re-runs the per-(D1, D5) cell-gap math. The point: Phase 3 sourcing can satisfy floors on the COMBINED set yet leave a cell with no labeled failures once adjudication finishes — a "successful labeling collapse" that breaks Stage 6's failure-mode calibration. This gate catches it **before** Phase 6 hashes the manifest.

```bash
.venv/bin/python -c "
from services.governance.goaljudge_goldset_dataset import evaluate_goldset_post_alpha_coverage
import csv
rows = list(csv.DictReader(open('docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv')))
report = evaluate_goldset_post_alpha_coverage(rows)
print('total false-labeled items:', report.total_items)
print('cells with gaps:')
for cell, gap in report.gaps.items():
    if gap > 0:
        print(f'  {cell}: gap={gap}')
"
```

The function returns a `CoverageReport` (the same type Phase 3's sourcing gate produced); rows with `adjudicated_goal_met ∉ {\"false\"}` are dropped *before* scoring, so `total_items` reflects only the failure subset Stage 6 will actually calibrate against. Empty failure subset → every gap equals the corresponding floor (the gate fails loudly, not silently).

If gaps exist, the gold set has thin failure-signal in some cells. Acceptable if documented in the Phase 6 manifest's `coverage_caveats[]`; not acceptable to ignore.

---

## 8. Common failure modes & their resolutions

| Symptom | Likely cause | Resolution |
|---|---|---|
| α drops below 0.667 on round 1 | Protocol under-specifies a recurring case OR one annotator is grading on a different evidence hierarchy than the other (e.g., A1 admits status-feed UI captures, A2 marks them inadmissible) | §6 revise loop, **plus** a coordinator-led 30-min walkthrough of the evidence hierarchy with both annotators before round 2 |
| α ≥ 0.8 but post-α coverage check fails | The 79-row corpus is sound but the gold labels concentrated all `goal_met=false` in a few cells | Acceptable for Tier 3 freeze if documented; flag for Stage 6 calibration to weight cells with thin signal accordingly |
| Round-3 still α < 0.8 | Rubric ambiguity in axes the protocol cannot resolve via local rule additions | **Escalate.** Pause Phase 5; bring rubric ambiguity back to Stage 4 (Phase B-style update). Mark all Phase 5 rounds as `superseded` and re-label after the rubric revision lands |
| One annotator's notes are uniformly thin / generic | Annotator fatigue (the "boredom plateau" — common around row 50) | Coordinator pauses the round; annotator takes ≥24 h off; resumes from row 51. Do NOT push through fatigue — α suffers and you cannot tell from the number alone |
| Annotator finds a row with a typo / authoring defect | Phase 4 author missed it; Rule 6's `note=authoring-typo-found` escape valve fires | Adjudicator marks the row `superseded` in the results doc; coordinator files a follow-up to fix the typo in `fresh_test_tasks.py` (does **not** block freeze) |
| α script throws on bad CSV | A `partial_fraction` cell has a non-numeric string (Sheets occasionally emits `'0.5'` with stray whitespace) | `--column goal_met` is the default; the script only normalizes the goal_met column. For pre-flight cleanliness: `awk -F, 'NR>1 && $X !~ /^[0-9.]*$/' full_sheet.csv` to spot anomalies before α |

---

## 9. Acceptance summary — how Phase 5 closes

Phase 5 is **DONE** when **all** of the following are true:

- ☐ `goaljudge_stage5_goldset_full_sheet.csv` has 79 rows, all with non-blank `adjudicated_goal_met`.
- ☐ `compute_goaljudge_stage5_alpha.py` reports α ≥ 0.8 on `goal_met` (record band).
- ☐ `evaluate_goldset_post_alpha_coverage(rows)` returns a `CoverageReport` with `gaps == 0` in every cell (or remaining gaps are documented in the Phase 6 manifest's `coverage_caveats[]`).
- ☐ The disagreement diff CSV from the **final** round is committed under `cache/goaljudge_eval/` (auditable trail of what was resolved).
- ☐ `goaljudge_stage5_goldset_results.md` has one row per round with `(round, alpha, band, agreements, disagreements, gate)`, and the final row is `gate=PASS`.
- ☐ If Rule 8 was added: `full_set_labeling_protocol.md` cites the round-1 disagreement diff as the rule's origin (audit trail back to data).
- ☐ The labeling protocol's "five rules / seven rules / eight rules" header in §2 matches the actual rule count.

Once all six pass, **trigger Phase 6 assembly:**

```bash
.venv/bin/python scripts/assemble_goaljudge_goldset.py \
  --sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
  --output cache/goaljudge_eval/goaljudge_goldset_v1.json \
  --manifest cache/goaljudge_eval/goaljudge_goldset_v1_manifest.json
```

Phase 6's invariant-checker is the next gate; it consumes the adjudicated columns directly and verifies SHA-256 + cell coverage + split firewall.

---

## 10. Known gaps / backlog (does not block Phase 5)

- **`--fresh-tasks` flag on full-sheet builder.** As of this doc's last review, `scripts/build_goaljudge_stage5_full_sheet.py` reads from UI-batch + corpus sidecars; pulling the 79 authored fresh tasks in directly is a one-line `from tests.fixtures.goaljudge.fresh_test_tasks import FRESH_TEST_TASKS` extension. Until that lands, coordinator manually appends fresh-task rows to the CSV before §3 (column shape is identical; the only extra work is filling `provenance=fresh-authored`).
- **H-2 walkthrough §9 floor-gate clarification.** The Phase 4 walkthrough's §9 still describes D1/D5 floors as a "Phase 4 gate"; in the canonical sequencing they are a Phase 6 gate (post-α, pre-freeze). Low-priority doc fix; does not affect Phase 5 mechanics.
- **EvalGen Rule 8 template.** If a Rule 8 lands in the wild, capture its shape in `full_set_labeling_protocol.md`'s appendix as a worked example for future rule additions.

---

## 11. Cross-references

| Doc | Role |
|---|---|
| [`full_set_labeling_protocol.md`](full_set_labeling_protocol.md) | **Annotators' rulebook** — Rules 1–7, evidence hierarchy, decision tree |
| [`fresh_task_authoring_guide.md`](fresh_task_authoring_guide.md) | Phase 4 authoring discipline (cluster table + decision tree); §3.1 is the Phase-4-to-Phase-5 contract for `wrong-tool` |
| [`phase4_authoring_walkthrough.md`](phase4_authoring_walkthrough.md) | Phase 4 runbook (5 → 80 fresh tasks); this doc is its successor |
| [`../../IAA/goalJudge/goldset/README.md`](../../IAA/goalJudge/goldset/README.md) | Canonical IAA dir — pilot results, full-run results scaffold, three-tier gate table |
| [`../../IAA/goalJudge/goldset/goaljudge_stage5_goldset_results.md`](../../IAA/goalJudge/goldset/goaljudge_stage5_goldset_results.md) | Live α tracker — one row per round |
| [`../../IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md`](../../IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md) | Pilot α = 0.8846 PASS (Tier 1 precedent — Phase 5 inherits its evidence discipline) |
| [`../../plans/goaljudge_stage5_tier3_assembly.plan.md`](../../plans/goaljudge_stage5_tier3_assembly.plan.md) | Tier 3 assembly plan — Phase 5 is one step of seven |
| [`../../research/goaljudge_stage5_goldset_spec.md`](../goaljudge_stage5_goldset_spec.md) | Multi-axis label schema (§2), evidence hierarchy (§8.3), dataset field contract (§9) |
| [`services.governance.iaa`](../../../services/governance/iaa.py) | L1 module: α math (`krippendorff_alpha_nominal`), `normalize_bool_label`, `compute_disagreement_diff`, `apply_adjudication`, `landis_koch_band` |
| [`services.governance.goaljudge_goldset_dataset`](../../../services/governance/goaljudge_goldset_dataset.py) | L1 module: `evaluate_goldset_post_alpha_coverage` (returns `CoverageReport` — Phase 5 §7.3 gate) |
| [`scripts/compute_goaljudge_stage5_alpha.py`](../../../scripts/compute_goaljudge_stage5_alpha.py) | CLI wrapper — `--diff OUT.csv` for the adjudicator |
| [`scripts/assemble_goaljudge_goldset.py`](../../../scripts/assemble_goaljudge_goldset.py) | Phase 6 entry — runs after Phase 5 closes |
