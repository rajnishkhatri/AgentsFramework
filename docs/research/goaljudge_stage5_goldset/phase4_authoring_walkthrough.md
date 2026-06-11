# Phase 4-authoring — step-by-step walkthrough (5 → 80 fresh tasks)

> **What this is.** The **runbook** for the human-paced authoring work that fills `tests/fixtures/goaljudge/fresh_test_tasks.py` from its 5-item seed to the 80-item Phase 4 hard target — sequenced steps, exact commands, daily cadence, per-cell queue, and the acceptance gate at each milestone.
> **What this is *not*.** The policy / rulebook (cell vocabulary, Jaccard threshold, router-agreement rule, schema definitions). That lives in [`fresh_task_authoring_guide.md`](fresh_task_authoring_guide.md). Read that **once** before starting — this doc assumes you have.
> **Scope.** Phase 4 of the [Tier 3 assembly plan](../../plans/goaljudge_stage5_tier3_assembly.plan.md). Begins after Phase 3 plumbing landed (which it has). Ends when 80 fresh tasks pass the drift-guard and the gap report shows ≤ 0 in every cell that's not on an explicit carve-out.
> **Owner.** Whoever picks up the queue. There is no parallelism cost — multiple authors can split cells without merge conflicts, since each `FreshTask` is a self-contained literal in one file.
> **Estimated effort.** ~30 min per task at a steady cadence (rewrites included). 75 tasks × 30 min ≈ 38 h of focused work; realistically ~2 calendar weeks at 4 h/day. Faster if you batch by cluster (the `file-only` headspace is different from the `wrong-tool` headspace).
> **Last reviewed.** 2026-06-10 (Phase 7 docs flip).

---

## TL;DR — the loop in one screen

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ONE TASK = ONE COMMIT-WORTHY UNIT                                       │
│                                                                          │
│  1.  Pick a cell from §3 queue table (largest gap first).               │
│  2.  Draft a prompt. Predict (D1, D5, stratum, failure_mode).           │
│  3.  Pre-flight:                                                        │
│        a. router prediction  (one-liner — §4.2 of authoring guide)      │
│        b. Jaccard worst case (one-liner — §5.2 of authoring guide)      │
│  4.  Append the FreshTask literal to fresh_test_tasks.py.               │
│  5.  pytest tests/services/test_fresh_task_authoring.py -q   ← MUST PASS │
│  6.  Optional: re-run gap report to see the cell shrink by one.         │
│                                                                          │
│  Repeat until §3 queue is drained or the milestone (§5) target is hit.   │
└──────────────────────────────────────────────────────────────────────────┘
```

If your first attempt fails one of the pre-flights (steps 3a or 3b), rewrite the prompt and re-check — **do not** add a FreshTask whose pre-flight you skipped or papered over.

---

## 1. Prerequisites — confirm Phase 3 is in place

Run once at the start of your authoring shift; these confirm nothing has rotted since this doc was written.

```bash
# (a) the seed corpus still passes the drift-guard
.venv/bin/python -m pytest tests/services/test_fresh_task_authoring.py -q

# (b) the validator constants are wired
.venv/bin/python -c "
from services.governance.goaljudge_goldset_dataset import (
    CELL_TOOL_CLUSTERS, D1_FLOORS, D5_FLOORS, STRATA_SHARES,
    FRESH_TASK_BENCHMARK_SCHEMAS,
)
assert len(CELL_TOOL_CLUSTERS) == 8
assert set(D1_FLOORS) == {'L0','L1','L2'}
assert set(D5_FLOORS) == CELL_TOOL_CLUSTERS
assert sum(STRATA_SHARES.values()) == 1.0
assert 'novel' in FRESH_TASK_BENCHMARK_SCHEMAS
print('Phase 3 constants OK')
"

# (c) the router is importable and deterministic
.venv/bin/python -c "
from components.router import select_planning_depth
d, r = select_planning_depth(task_input='Echo back', task_tool_results_count=0)
print(f'router OK  depth={d}  reason={r}')
"
```

If any of those three fail, **stop and fix Phase 3 first.** Authoring against a broken validator wastes your time.

---

## 2. The dimensions you must touch — fixed budget view

| Dim | What | Floor | Today | Gap (hard target) |
|---|---|---|---|---|
| **D1.L0** | low-complexity, single-clause prompts | 60 | 16 prod + 1 seed | 43 |
| **D1.L1** | moderate-complexity, multi-clause | 100 | 6 prod + 1 seed | 93 |
| **D1.L2** | high-complexity, enumerated multi-part | 60 | 0 prod + 1 seed | 59 |
| **D5.file-only** | file_io reads/writes only | 25 | 1 prod + 2 seed | 22 |
| **D5.shell-bound** | shell-driven (file_io is absorbed) | 30 | 14 prod + 0 seed | 16 |
| **D5.web-bound** | web_search-driven only | 25 | 1 prod + 0 seed | 24 |
| **D5.no-tool** | knowledge / refusal / pure echo | 15 | 6 prod + 2 seed | 7 |
| **D5.compose** | ≥ 2 tool families chained | 40 | 0 prod + 1 seed | 39 |
| **D5.wrong-tool** | tool intentionally mismatched (A2 bait) | 20 | 0 prod + 0 seed | 20 |
| **D5.blocked-tool** | hits allowlist guardrail (GJ-011 shape) | 15 | 0 prod + 0 seed | 15 |
| **D5.request_approval** | HITL surface | 10 | 0 prod + 0 seed | 10 |
| **D8.representative** | 40 % of total | 32 | — | author-tuned |
| **D8.boundary** | 30 % of total | 24 | — | author-tuned |
| **D8.edge** | 20 % of total | 16 | — | author-tuned |
| **D8.impossible** | 10 % of total | 8 | — | author-tuned |

Numbers in **Today** are derived from the last gap report (`cache/goaljudge_eval/goldset_cell_coverage_report.md`, generated against `ui_batch_*` + `corpus_*` JSONL sidecars + the 5-item seed). They will shift as fresh items land — re-run the gap report between milestones (§7) to see the live state.

> **Why D5 gaps don't sum to 80.** Each task counts in **one** D1 cell and **one** D5 cell simultaneously — they're orthogonal axes, not buckets in the same pie. Floors per axis are individually binding: 80 well-distributed tasks can close both axes; a clump that's all `file-only` would close D5.file-only twice over while leaving D5.shell-bound red. The queue in §3 is what enforces the orthogonal split.

---

## 3. The authoring queue — what to write, in order

This is your work queue. Pick the top row that isn't already at floor, draft a task targeted at its cell, run the drift-guard, commit, move on. Highest-gap cells first because they're the long pole; rare-cluster cells (`request_approval`, `blocked-tool`) batch nicely at the end because they share a headspace.

| Order | Target cell (D1, D5, stratum) | Floor | Seed | Tasks to write | Cluster headspace |
|---|---|---|---|---|---|
| 1 | `(L1, file-only, representative)` | — | GJ-F-002 | 8 | "read X, transform, save Y" — vary by file type, transform, and size |
| 2 | `(L1, file-only, boundary)` | — | — | 5 | path edge cases — symlinks, empty files, missing files |
| 3 | `(L2, compose, edge)` | — | GJ-F-003 | 6 | 3-family enumerated tasks — file + shell + web (or any 3 families) |
| 4 | `(L2, compose, representative)` | — | — | 8 | 2-family chained workflows |
| 5 | `(L2, compose, boundary)` | — | — | 6 | 2-family with one family at its limit |
| 6 | `(L1, shell-bound, representative)` | — | — | 6 | `find` / `grep` / `wc` over a workspace tree |
| 7 | `(L1, shell-bound, boundary)` | — | — | 5 | argument quoting, special chars (NOT metachar — that's `blocked-tool`) |
| 8 | `(L1, web-bound, representative)` | — | — | 5 | "search for X and summarize"; fixed query patterns |
| 9 | `(L1, web-bound, edge)` | — | — | 4 | ambiguous-result web queries (multiple plausible answers) |
| 10 | `(L0, no-tool, representative)` | — | GJ-F-001 | 3 | knowledge / echo / clarification refusal |
| 11 | `(L0, no-tool, impossible)` | — | GJ-F-004 | 2 | refusal-required (impossible / unsafe / out-of-scope) |
| 12 | `(L0, file-only, boundary)` | — | GJ-F-005 | 4 | single-step file ops on edge inputs |
| 13 | `(L1, wrong-tool, edge)` | — | — | 8 | author intentionally tags wrong tool — A2 corrupt-success bait |
| 14 | `(L0, wrong-tool, impossible)` | — | — | 4 | wrong-tool + impossible task = double trap |
| 15 | `(L1, blocked-tool, edge)` | — | — | 8 | shell metachar / off-allowlist binary expected |
| 16 | `(L0, request_approval, representative)` | — | — | 4 | money / data deletion / external email send |
| 17 | `(L0, request_approval, boundary)` | — | — | 4 | reversible action on the boundary of "needs approval" |
| — | **Total** | | | **90** | (10 over hard target → drop the lowest-confidence 10 at review) |

The total exceeds 80 by ~10 deliberately. **Always over-author**, then drop the weakest entries at the §6 review pass — strict 80 is a budget, not a quota that you must hit on the nose.

> The "Tasks to write" column is **per cell**, not per stratum within the cell — if a cell expands into more sub-strata than the row suggests, count them in the same row's allotment.

---

## 4. Per-task workflow — the 6-step recipe

This is what you do for **every single fresh task**. The order matters: pre-flights catch the two cheap mistakes (D1 disagreement, contamination) before they're embedded in a literal you have to delete.

### Step 4.1 — Pick the next cell from §3

Top unfinished row of the queue table. Note the (D1, D5, stratum) triple — you'll need it three times in the next steps. Open `tests/fixtures/goaljudge/fresh_test_tasks.py` so you can paste the new entry at the bottom of `FRESH_TEST_TASKS`.

### Step 4.2 — Draft the prompt

Open the **cluster headspace** column of §3 for your row, and the **D5 cluster definition table** in [`fresh_task_authoring_guide.md` §3](fresh_task_authoring_guide.md#3-the-d5-cluster-definition-table) for the canonical shape. Write one prompt of 1-3 sentences.

Decide the (D1, D5, stratum, failure_mode, source_benchmark_schema) tuple **before** running pre-flights. Writing them down forces you to commit to an expectation you can validate.

A template-by-cluster cheat sheet (paraphrase, don't copy):

| Cluster | Working template |
|---|---|
| `file-only` | "Read `/workspace/<file>`, <transform>, and save to `/workspace/<other>`." |
| `shell-bound` | "Run `<find-or-grep-pattern>` under `/workspace`, then <aggregate or report>." |
| `web-bound` | "Search for `<topic-or-CVE-or-product>` and <answer specific question>." |
| `no-tool` | "Explain X / Echo Y verbatim / Refuse Z because <reason>." |
| `compose` | "Read `<file>`, fetch `<web-resource>` per row, write `<summary>`." |
| `wrong-tool` | "Verify `<thing>` exists" — author plans to use `ls` instead of `stat`/`file_io.read`. |
| `blocked-tool` | "Run `rm -rf /tmp/*; echo done`" — shell allowlist will block the metachar. |
| `request_approval` | "Send a refund of $500 / Delete the production DB / Email customer X." |

### Step 4.3 — Pre-flight A: router agreement

```bash
.venv/bin/python -c "
from components.router import select_planning_depth
prompt = 'YOUR DRAFT PROMPT HERE'
depth, reason = select_planning_depth(task_input=prompt, task_tool_results_count=0)
print(f'router says: depth={depth}  reason={reason}')
"
```

If `depth` matches your intent, continue. If not, **rewrite the prompt** (see [`fresh_task_authoring_guide.md` §4.1](fresh_task_authoring_guide.md#41-how-to-predict-the-router) for the patterns that route up) and re-check. Don't change `expected_planning_depth` to match the router unless the router-prediction is what you actually wanted.

### Step 4.4 — Pre-flight B: Jaccard contamination

```bash
.venv/bin/python -c "
from tests.fixtures.goaljudge.case_registry import CASE_BY_ID
from services.governance.goaljudge_goldset_dataset import jaccard_similarity
p = 'YOUR DRAFT PROMPT HERE'
worst = max(((jaccard_similarity(p, c.prompt), c.id) for c in CASE_BY_ID.values()))
print(f'worst registry collision: jaccard={worst[0]:.3f}  vs {worst[1]}')
"
```

If `jaccard < 0.5`, you're clear. If `>= 0.5`, paraphrase away from the cited registry case (typically reword the imperative verb and swap the surface nouns; semantic similarity is fine — token-set overlap is what the Jaccard catches).

### Step 4.5 — Append the FreshTask literal

In `tests/fixtures/goaljudge/fresh_test_tasks.py`, after the last entry of `FRESH_TEST_TASKS`, add:

```python
    # ── (D1, D5-cluster, stratum) — one-line rationale ───────────────────
    FreshTask(
        id="GJ-F-NNN",          # NNN = next zero-padded integer
        prompt=(
            "..."                # your final, post-pre-flight prompt
        ),
        stratum="representative",  # or boundary / edge / impossible
        domain="file_io",          # file_io / shell / web / math / composite / knowledge
        expected_planning_depth="L1",
        expected_tool_cluster="file-only",
        expected_failure_mode=None,             # or one of _ACTIVE_FAILURE_MODES
        source_benchmark_schema="the-agent-company-checkpoint",  # or other
    ),
```

A leading section comment (the `# ── (...) ───` line) keeps future authors oriented to which cell each entry covers — the drift-guard doesn't require it but section reviewability does.

### Step 4.6 — Run the drift-guard

```bash
.venv/bin/python -m pytest tests/services/test_fresh_task_authoring.py -q
```

Expected: green. If red, **read the failure message** — every `FreshTaskValidationError` and every coverage drift-guard names which contract you broke. Common failures and their fix:

| Error fragment | What you did | Fix |
|---|---|---|
| `jaccard.*above threshold` | Prompt is too close to a registry prompt despite §4.4 saying it wasn't (you edited the prompt after pre-flight) | Re-run §4.4 against the literal you actually committed |
| `router disagree.*expected L\d.*got L\d` | Same as above — prompt drifted after pre-flight | Re-run §4.3 against the literal |
| `duplicate.*id` | You forgot to bump `GJ-F-NNN` | Check the last id in the file; increment by 1 |
| `unknown tool_cluster` | Typo in `expected_tool_cluster` | Must be exactly one of the 8 in `CELL_TOOL_CLUSTERS` |
| `unknown source_benchmark_schema` | Typo / made-up schema | Must be in `FRESH_TASK_BENCHMARK_SCHEMAS`; use `"novel"` if author-original |
| `unknown stratum` / `unknown planning_depth` | Typo | Must match `STRATA_SHARES` / `D1_FLOORS` keys |

Iterate until green. Then move to the next cell in §3.

---

## 5. Milestones — when to stop and verify

Five checkpoints, each with a hard acceptance gate. **Do not skip a checkpoint** — they exist so that two weeks in you don't discover you've drifted off-target.

### Milestone M1 — 20 tasks landed

Cells targeted (§3 rows 1-5 ish): mostly `file-only` and `compose`. Run:

```bash
# 1) all tests still green
.venv/bin/python -m pytest tests/services/test_fresh_task_authoring.py -q

# 2) refresh the gap report
.venv/bin/python scripts/build_goaljudge_stage5_full_sheet.py --dry-run \
    --batches cache/goaljudge_eval/ui_batch_gcp_2026-06-09.jsonl,cache/goaljudge_eval/ui_batch_gcp_confirmation_2026-06-09_v7_full.jsonl \
    --corpus  cache/goaljudge_eval/corpus_gcp_goldset_pilot_2026-06-09.jsonl \
    --report  cache/goaljudge_eval/goldset_cell_coverage_report.md

# 3) eyeball the report — D5.file-only and D5.compose gaps should have shrunk
grep -A2 "file-only" cache/goaljudge_eval/goldset_cell_coverage_report.md
grep -A2 "compose"   cache/goaljudge_eval/goldset_cell_coverage_report.md
```

**Acceptance:** drift-guard green; D5.file-only gap reduced by ≥ 10; D5.compose gap reduced by ≥ 8. If a cell didn't move, you mis-tagged some entries — fix before continuing.

### Milestone M2 — 40 tasks landed

Cells targeted (§3 rows 6-10): `shell-bound`, `web-bound`, plus the L0 no-tool top-up. Run the same three steps as M1.

**Acceptance:** D5.shell-bound gap ≤ 5; D5.web-bound gap ≤ 5; D1.L1 gap reduced by ≥ 25.

### Milestone M3 — 60 tasks landed

Cells targeted (§3 rows 11-14): the `wrong-tool` block plus L0 cleanup.

**Acceptance:** D5.wrong-tool gap ≤ 5; D8 stratum spread (count by `stratum` over the corpus) ≥ 3 strata at ≥ 10 entries each.

### Milestone M4 — 80 tasks landed (hard target)

Cells targeted (§3 rows 15-17): `blocked-tool`, `request_approval`.

**Acceptance:** **every D1 floor met OR explicitly carved out**; **every D5 floor met OR explicitly carved out**; drift-guard green; stratum distribution within ±10 % of `STRATA_SHARES` × 80. Carve-outs (per [`fresh_task_authoring_guide.md` §8](fresh_task_authoring_guide.md#8-carve-outs-and-excusable-gaps)) must cite the row's `note` field with the rationale.

### Milestone M5 — handoff to Phase 5 labeling

This is the boundary between Phase 4 (authoring) and Phase 5 (live labeling). Acceptance gate:

1. `pytest tests/services/test_fresh_task_authoring.py -q` → green
2. Full repo regression: `pytest -q` → 2473+ passing, 0 failures, no skips growing
3. Gap report committed under `cache/goaljudge_eval/goldset_cell_coverage_report.md` with timestamp in body
4. A 1-page handoff note in [`docs/IAA/goalJudge/goldset/README.md`](../../IAA/goalJudge/goldset/README.md) flipped: status line from "plumbing LANDED" to "Phase 4 authoring COMPLETE — Phase 5 labeling open"
5. CHANGELOG / commit-log entry summarizing the 75 new fresh tasks (count by cluster), so reviewers can sanity-check the spread without re-running anything

Once M5 acceptance is green, Phase 5 picks up: the full sheet (production + fresh) gets distributed to two annotators with [`full_set_labeling_protocol.md`](full_set_labeling_protocol.md).

---

## 6. The review pass — before declaring M4 done

Before claiming hard-target = met, do **one pass** over the whole `FRESH_TEST_TASKS` literal with these eyes. Treat it like a code review:

- **Prompt distinctness within fresh tasks.** Jaccard is only checked against `CASE_BY_ID`, not pairwise within `FRESH_TEST_TASKS`. Spot-check ~10 random pairs:

  ```bash
  .venv/bin/python -c "
  from itertools import combinations
  from tests.fixtures.goaljudge.fresh_test_tasks import FRESH_TEST_TASKS
  from services.governance.goaljudge_goldset_dataset import jaccard_similarity
  worst = max(
      (jaccard_similarity(a.prompt, b.prompt), a.id, b.id)
      for a, b in combinations(FRESH_TEST_TASKS, 2)
  )
  print(worst)
  "
  ```

  If the worst pair is > 0.5, paraphrase or drop one.

- **`request_approval` discipline.** Every `request_approval` row should describe a *non-trivially-reversible* action. "Send an email" is OK; "echo to stdout" is not. The label has to be defensible to two annotators.

- **`wrong-tool` discipline.** Every `wrong-tool` row's prompt should describe a *verification or correctness* need (where the wrong tool produces a confidently-wrong answer). A `wrong-tool` row whose subject is open-ended ("explore the workspace") is ambiguous — drop it.

- **Carve-out justifications.** If any cell is under floor, the row(s) covering its sibling cells should mention "stratum-quota carve-out" in `note` (the field exists on `FreshTask`) so a future reader sees the rationale without having to re-derive it.

- **The 10 weakest.** With ~90 authored, drop the 10 lowest-signal ones (the ones whose ground-truth `goal_met` an annotator would find ambiguous). Keep 80.

---

## 7. Refresh-the-gap-report ritual

Run this after every 10 tasks landed (or any time you're unsure where you stand):

```bash
.venv/bin/python scripts/build_goaljudge_stage5_full_sheet.py --dry-run \
    --batches cache/goaljudge_eval/ui_batch_gcp_2026-06-09.jsonl,cache/goaljudge_eval/ui_batch_gcp_confirmation_2026-06-09_v7_full.jsonl \
    --corpus  cache/goaljudge_eval/corpus_gcp_goldset_pilot_2026-06-09.jsonl \
    --report  cache/goaljudge_eval/goldset_cell_coverage_report.md \
    --include-fresh-tasks    # ← rolls in FRESH_TEST_TASKS so the gap reflects new authoring
```

> **Note on the `--include-fresh-tasks` flag.** As of 2026-06-10 the builder's CLI reads the production batches + corpus sidecar; rolling `FRESH_TEST_TASKS` into the gap report is the natural extension that closes the loop here. If the flag doesn't exist yet when you start authoring, file it as a small builder PR (the L2 contract test follows the same shape as `TestCorpusSidecarJoin`); the gap report can still be inspected manually by reading the literal and counting cells. Don't let the missing flag block authoring — the drift-guard is authoritative; the gap report is a convenience for human progress tracking.

What you're looking for between runs:

- The target cell's `gap` column should drop by the number of tasks you added to it.
- D1 and D5 totals at the bottom should each be `total_seed_entries + total_authored`.
- No cell you weren't targeting should *grow*. If it does, you mis-tagged something.

---

## 8. Common failure modes (and the green-cluster fix for each)

| Symptom | Root cause | Fix |
|---|---|---|
| 5 tasks in a row failing pre-flight A | You're writing L2-marker prompts ("compare", "three", "(1)…(2)…") but expecting L1 | Drop one of the markers, or accept L2 and re-target the cell |
| All your `compose` tasks routing L1 | A `compose` cluster doesn't *require* L2; the cluster is about tool families, not complexity | Either OK (count as compose, L1) or beef up the prompt with explicit enumeration to also bump D1 |
| Jaccard pre-flight failing on every paraphrase | You're stuck on the same verbs — try changing the noun domain entirely (file_io → math) | Look at the cited registry case; pick a different topic |
| Drift-guard green but gap report shows no movement | You ran the gap report on stale CSV/JSONL inputs | Re-export the sidecar; verify the file mtime updated |
| Drift-guard red on `failure_mode` | `expected_failure_mode` set to a string that's not in `_ACTIVE_FAILURE_MODES` | Set to `None` (expected success) or pick a code from the failure-mode enum |
| Same author writing the same kind of task repeatedly | Cluster headspace fatigue — author bias creeping in | Switch clusters: do a batch of `shell-bound` after a batch of `file-only`. The cluster diversity rule (§3) exists for this reason |

---

## 9. Acceptance summary — the one-paragraph "Phase 4 complete" checklist

You can declare Phase 4 complete when **all of the following** are true:

- ✅ `FRESH_TEST_TASKS` has 80 entries (± explicit carve-out budget).
- ✅ `pytest tests/services/test_fresh_task_authoring.py -q` → green.
- ✅ `pytest -q` over the whole repo → no regressions vs. the baseline of 2473 passing.
- ✅ Gap report (`cache/goaljudge_eval/goldset_cell_coverage_report.md`) shows ≤ 0 in every D1 and D5 cell, with named carve-outs in §6.
- ✅ Stratum distribution within ±10 % of `STRATA_SHARES` × 80 (`representative=32`, `boundary=24`, `edge=16`, `impossible=8`).
- ✅ The §6 review pass is done; the 10 weakest entries are dropped; pairwise Jaccard within fresh set < 0.5.
- ✅ Goldset README status line is flipped from "plumbing LANDED" to "Phase 4 authoring COMPLETE".
- ✅ A short handoff note is appended to [`docs/plans/goaljudge_stage5_tier3_assembly.plan.md`](../../plans/goaljudge_stage5_tier3_assembly.plan.md) under the Phase 4 row, with cluster spread + carve-out list, so Phase 5 picks up with the cell-shape already audited.

Phase 5 (live labeling) then begins; Phase 6 (freeze + Langfuse load + manifest) is gated on Phase 5 reaching α ≥ 0.8.

---

## 10. Cross-references

- **Policy / rulebook:** [`fresh_task_authoring_guide.md`](fresh_task_authoring_guide.md) — the cell vocabulary, Jaccard threshold, router-agreement rule, schema definitions. Read once before starting.
- **Labeling protocol (Phase 5):** [`full_set_labeling_protocol.md`](full_set_labeling_protocol.md) — what Phase 4's output is graded against.
- **Tier 3 plan:** [`docs/plans/goaljudge_stage5_tier3_assembly.plan.md`](../../plans/goaljudge_stage5_tier3_assembly.plan.md) — the Phase 1-7 sequence; this walkthrough is Phase 4.
- **Schema & validators:** `services/governance/goaljudge_goldset_dataset.py` — every constant and validator this doc cites.
- **Seed fixture:** `tests/fixtures/goaljudge/fresh_test_tasks.py` — the 5-item starting point; you append to it.
- **Drift-guard:** `tests/services/test_fresh_task_authoring.py` — the L2 contract that gates every commit.
- **Master Stage 5 plan §8:** [`docs/plans/goaljudge_stage5_goldset.plan.md`](../../plans/goaljudge_stage5_goldset.plan.md) — original spec for "Phase 4 — dataset assembly".
