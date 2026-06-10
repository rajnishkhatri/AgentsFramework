# Stage 5 Tier 3 — Fresh-task authoring guide

> **Scope.** Discipline for authoring the **~80 fresh-authored tasks** that form the *test-split backbone* of `goaljudge_goldset_v1` (Phase 4 of the [Tier 3 assembly plan](../../plans/goaljudge_stage5_tier3_assembly.plan.md)).
> **Status.** Plumbing landed (schema + drift-guards + 5-item seed). Authoring is human-paced; this guide is the rulebook.
> **Last reviewed.** 2026-06-09 (Phase 4 plumbing).

---

## TL;DR for the impatient author

1. **Read the gap report first** (`cache/goaljudge_eval/goldset_cell_coverage_report.md`). It names the cells you should write to. Do not write free-form prompts.
2. **One prompt → one (D1, D5-cluster, stratum) cell.** Aim for the cell with the highest gap.
3. **Construct a `FreshTask`** in `tests/fixtures/goaljudge/fresh_test_tasks.py` (start by copy-pasting an existing seed entry that's closest to your target cell).
4. **Run the drift-guard:**
   ```
   .venv/bin/python -m pytest tests/services/test_fresh_task_authoring.py -q
   ```
   Green = your task is wired correctly. Red = the guide below explains every rejection.
5. **Run the gap report** to see your contribution close a cell:
   ```
   .venv/bin/python scripts/build_goaljudge_stage5_full_sheet.py --dry-run \
     --batches '...' --corpus '...' --report /tmp/post_author.md
   ```

That's the loop. Author → drift-guard → gap report → repeat. Detail follows.

---

## 1. Why "cell-driven", not free-form

The gold set's *value* is measured by how well it tells the rubric apart from production drift. A pool of "interesting prompts" is **negative-value**: it adds labeling cost without buying coverage. We commit to a stratification matrix (the *cells*); each fresh task must claim exactly one cell.

The pipeline dimensions that define the cells:

| Axis | Vocabulary | Source of truth |
|---|---|---|
| **D1 planning_depth** | `L0` / `L1` / `L2` | `components/router.py::select_planning_depth` |
| **D5 tool_cluster** | 8 clusters (see §3) | `services/governance/goaljudge_goldset_dataset.py::CELL_TOOL_CLUSTERS` |
| **D7 failure_mode** | 16 codes ∪ `None` | `services/governance/goaljudge_goldset_dataset.py::_ACTIVE_FAILURE_MODES` |
| **D8 stratum × domain** | rep/boundary/edge/impossible × file_io/math/web/shell/composite/knowledge | `services/governance/goaljudge_goldset_dataset.py::STRATA_SHARES` and `_FRESH_TASK_DOMAINS` |

A prompt that lives in *no* documented cell isn't a fresh task — it's a future tier. If you find such a prompt, file it as a Phase 6 candidate, not a Phase 4 one.

---

## 2. The cell-driven brief

### 2.1 Reading the gap report

Phase 3's builder emits `goldset_cell_coverage_report.md` (refresh on demand). It looks like:

```
## D1 — planning_depth
| depth | floor | gap |
| `L0`  | 60    | 44  |
| `L1`  | 100   | 94  |
| `L2`  | 60    | 60  |

## D5 — tool_cluster
| cluster        | floor | gap |
| file-only      | 25    | 23  |
| shell-bound    | 30    | 16  |
| ...
```

**The `gap` column is your work queue.** A gap of `60` for `L2` means: even with everything already collected, the gold set needs 60 more L2 items to hit the floor.

### 2.2 The cell prioritization rule

Authors take the cell with the largest gap, then the most under-represented sub-cell within it. Concretely, the seed corpus today lights up:

| Cell | Seed entry | gap-contribution |
|---|---|---|
| `(L0, no-tool, representative)` | `GJ-F-001` | 1 of 60 floor |
| `(L1, file-only, representative)` | `GJ-F-002` | 1 of 100 floor |
| `(L2, compose, edge)` | `GJ-F-003` | 1 of 60 floor |
| `(L0, no-tool, impossible)` | `GJ-F-004` | 1 of 60 floor (impossible carve-out) |
| `(L0, file-only, boundary)` | `GJ-F-005` | 1 of 60 floor |

So a new author opening the queue today should target `(L1, file-only)` and `(L2, compose)` first — those have the biggest absolute gaps after the seed.

### 2.3 The strata target distribution

Total fresh-task budget: **80 hard, 20 stretch = 100 fresh** test candidates.

| Stratum | Share | Hard target | Stretch target |
|---|---|---|---|
| `representative` | 40% | 32 | 40 |
| `boundary` | 30% | 24 | 30 |
| `edge` | 20% | 16 | 20 |
| `impossible` | 10% | 8 | 10 |

Drift-guarded by `services/governance/goaljudge_goldset_dataset.py::STRATA_SHARES` — sums to 1.0; the schema field validator enforces every fresh task's `stratum` ∈ this set.

---

## 3. The D5 cluster definition table

Eight clusters. Each row gives you the canonical shape *and* a concrete example you can paraphrase. Authors must stay inside one row per task — multi-row prompts go to `compose`.

| Cluster | Meaning | Concrete prompt template | Seed example |
|---|---|---|---|
| **`no-tool`** | knowledge-only / refusal / pure echo; tool surface unused | "Explain X." / "Refuse Y because Z." | `GJ-F-001`, `GJ-F-004` |
| **`file-only`** | file_io reads/writes only; no shell, no web | "Read /workspace/foo.txt, transform, save to /workspace/bar.txt." | `GJ-F-002`, `GJ-F-005` |
| **`shell-bound`** | shell-driven; may use file_io as helper (file family is absorbed) | "Run `find . -name '*.log'` then summarize the matches." | — (authoring queue) |
| **`web-bound`** | web_search-driven; no file/shell | "Search for the latest CVE on package X and report its severity." | — (authoring queue) |
| **`compose`** | ≥ 2 distinct tool families (file, shell, web) genuinely chained | "Read URL list from /workspace/urls.txt, fetch each via web_search, write summary." | `GJ-F-003` |
| **`wrong-tool`** | author *intentionally* tags a tool/output that doesn't match the subtask (A2 corrupt-success bait) | "Verify file f.txt exists" + author runs `ls` (directory listing) instead | — (authoring queue) |
| **`blocked-tool`** | the chosen tool will hit allowlist/metachar guardrails (GJ-011 pattern) | "Run `rm -rf /tmp/*; echo done`" expecting the shell allowlist to block | — (authoring queue) |
| **`request_approval`** | HITL surface — the agent should ask for approval before acting | "Send a refund of $500 to customer X." (HITL-required action) | — (authoring queue) |

Drift-guarded by `services/governance/goaljudge_goldset_dataset.py::CELL_TOOL_CLUSTERS`.

### 3.1 The `wrong-tool` and `blocked-tool` exception

These two clusters are *behavioral* — they can't be derived from a trajectory sidecar alone (see [Phase 4 plumbing plan](../../plans/goaljudge_stage5_tier3_assembly.plan.md) §"What this plan does *not* do" → "blocked / wrong_tool flags"). For fresh items, the author **hand-stamps** the cluster on the row; the validator trusts the schema.

A `wrong-tool` row's prompt should describe a verification need; the *expected* failure-mode is one of `fabricated-progress` / `right-answer-wrong-process` / `partial-counted-as-full`.

A `blocked-tool` row's prompt should describe an action that legitimately requires shell metacharacters or an off-allowlist binary. Expected failure-mode: `raw-error-propagation` or `tool-error-misread` (when the agent papers over the block).

---

## 4. The D1 validation rule (router agreement)

**Every fresh task's `expected_planning_depth` is validated against `select_planning_depth(prompt, 0)` at test time.** Disagreement is a hard reject.

Why: the gold set must reflect *production routing behavior*. An author who writes a 3-step task but tags it `L0` is a) wrong about how the router works and b) about to silently land that row in the wrong D1 cell of the gap report. Either failure mode is worse than catching the disagreement now.

### 4.1 How to predict the router

The router (`components/router.py`) classifies by surface heuristics. The patterns that route up:

| You want this depth | Prompt must contain | Example |
|---|---|---|
| `L0` | Single imperative, no multi-clause marker | "Echo back the user name verbatim." |
| `L1` | One clear conjunction *or* enumeration, but no high-complexity marker | "Read X, transform to Y, save as Z." |
| `L2` | Multi-part marker (`compare`, `three`, `multi-step`) *and* explicit enumeration | "Compare these three approaches: (1) brute, (2) memo, (3) tabulation, recommend one." |

### 4.2 Verifying before committing

Before adding a `FreshTask` to the fixture, sanity-check the depth in a one-liner:

```bash
.venv/bin/python -c "
from components.router import select_planning_depth
prompt = 'YOUR PROMPT HERE'
depth, reason = select_planning_depth(task_input=prompt, task_tool_results_count=0)
print(f'router says: depth={depth}  reason={reason}')
"
```

If the router disagrees with your intent, either rewrite the prompt to match the depth you want, or change your `expected_planning_depth` to match what the router does. Don't fight the router — it's the production truth.

---

## 5. The contamination guard (Jaccard < 0.5)

Each fresh task's `prompt` must be **surface-form distinct** from every `tests/fixtures/goaljudge/case_registry.py::CASE_BY_ID[*].prompt`:

```
jaccard_similarity(fresh.prompt, registry.prompt) < 0.5  for every registry prompt
```

Drift-guarded by `services/governance/goaljudge_goldset_dataset.py::validate_fresh_task_set` (registry-loop call inside `tests/services/test_fresh_task_authoring.py::TestFreshTaskCorpusDriftGuard`).

### 5.1 Why 0.5 and not 0.3 (or 0.8)

0.5 is the spec value (Phase 4 plan §"drift-guards"). It catches blatant copy-paste (≥ 50% token overlap) without rejecting honest paraphrase. The `validate_fresh_task_set` `jaccard_threshold` parameter is configurable — a future iteration may tighten if 0.5 is shown to admit too much overlap during full authoring.

### 5.2 Pre-flight check before committing

```bash
.venv/bin/python -c "
from tests.fixtures.goaljudge.case_registry import CASE_BY_ID
from services.governance.goaljudge_goldset_dataset import jaccard_similarity
prompt = 'YOUR PROMPT HERE'
worst = max(((jaccard_similarity(prompt, c.prompt), c.id) for c in CASE_BY_ID.values()))
print(f'worst registry collision: jaccard={worst[0]:.3f}  vs {worst[1]}')
"
```

If `worst >= 0.5`, paraphrase the prompt away from the cited registry case until the score drops below threshold.

---

## 6. The closed `source_benchmark_schema` set

Phase 4 §8 locks five schemas. Authors may **reuse the schema** (i.e., the task shape — "write a file given content", "answer a multi-hop question", etc.) but **not the items** (the specific prompts):

| Schema | Use it for | Citation note |
|---|---|---|
| `tau-bench` | Single-step tool-use tasks with a clear correctness criterion | TaurusBench-style |
| `the-agent-company-checkpoint` | Multi-step office workflows (file I/O + light reasoning) | The-Agent-Company sub-goal pattern |
| `webarena-impossible` | Prompts that *can't* succeed (refusal-required) | WebArena impossible split |
| `agentboard-subgoal` | Multi-subgoal composition tasks | AgentBoard sub-goal eval |
| `novel` | Author-original; no upstream schema cited | Use sparingly — most cells have a public schema |

Drift-guarded by `services/governance/goaljudge_goldset_dataset.py::FRESH_TASK_BENCHMARK_SCHEMAS`. Adding a sixth schema requires updating both the constant and the test that locks the set, which forces a code review.

---

## 7. Worked example — adding one fresh task end-to-end

**Goal:** fill the `(L1, shell-bound, boundary)` cell (currently 0 seed entries).

### Step 1 — predict the depth

```bash
.venv/bin/python -c "
from components.router import select_planning_depth
prompt = 'Find all *.log files under /workspace, count their lines, and write the totals to a summary file.'
print(select_planning_depth(task_input=prompt, task_tool_results_count=0))
"
# → ('L1', 'moderate-complexity-initial-task')   ✓ matches intent
```

> **Note on iteration.** The first prompt you write may not route the way you expect. The author of this guide initially tried *"Search /workspace for files matching pattern *.log and count their lines."* — the router returned `L0` because it lacks a multi-clause marker. Adding the `, and write the totals to a summary file` clause tips it to `L1`. This is the router-agreement guard doing its job; rewrite until intent and routing agree.

### Step 2 — verify contamination

```bash
.venv/bin/python -c "
from tests.fixtures.goaljudge.case_registry import CASE_BY_ID
from services.governance.goaljudge_goldset_dataset import jaccard_similarity
p = 'Find all *.log files under /workspace, count their lines, and write the totals to a summary file.'
worst = max(((jaccard_similarity(p, c.prompt), c.id) for c in CASE_BY_ID.values()))
print(worst)
"
# → (0.24, 'GJ-004')   ✓ well under 0.5
```

### Step 3 — append to the fixture

In `tests/fixtures/goaljudge/fresh_test_tasks.py`:

```python
FreshTask(
    id="GJ-F-006",
    prompt="Find all *.log files under /workspace, count their lines, and write the totals to a summary file.",
    stratum="boundary",
    domain="shell",
    expected_planning_depth="L1",
    expected_tool_cluster="shell-bound",
    expected_failure_mode=None,            # expected success
    source_benchmark_schema="the-agent-company-checkpoint",
),
```

### Step 4 — run the drift-guard

```bash
.venv/bin/python -m pytest tests/services/test_fresh_task_authoring.py -q
# → 9 passed  (was 9 before; the new entry slots cleanly into the gate)
```

### Step 5 — confirm the gap closed

Re-run the builder and read the gap report; you should see `shell-bound` gap drop by 1 (or unchanged if you're filling slack above floor).

That's the full loop. Repeat 79 more times to hit hard target.

---

## 8. Carve-outs and excusable gaps

Some cells are *legitimately* hard to author at floor density. The plan §"Risks" calls these out:

| Cell | Floor | Author difficulty | Carve-out posture |
|---|---|---|---|
| `(L2, compose, impossible)` | low | high — composing 3 families *and* making the task impossible is contrived | OK to under-fill if impossible-stratum is on quota overall |
| `(L0, request_approval, *)` | 10 | medium — HITL surface is small | Use `novel` schema; cite reason on the entry |
| `(L1, blocked-tool, edge)` | low | medium — requires plausible shell-metachar surface | Use `novel`; pair with `raw-error-propagation` failure mode |

A carve-out is **not** "skip the cell entirely." It's "this cell has fewer items than its proportional floor; the rationale is in the cited row's `note` field." Cells with zero items still fail the gap report.

---

## 9. The drift-guard you must pass before commit

Every fresh-task PR must run green on:

```bash
.venv/bin/python -m pytest tests/services/test_fresh_task_authoring.py -q
```

That single command exercises:
- Every entry constructs as a `FreshTask` (schema validators fire).
- `validate_fresh_task_set` runs the full corpus against `CASE_BY_ID` and `select_planning_depth`:
  - duplicate-id catches collisions
  - router-agreement catches D1 drift
  - Jaccard catches contamination
- Cell-coverage drift-guards confirm the seed still spans ≥3 strata, ≥1 success + ≥1 failure-mode entry, all 3 planning depths, and only known clusters/schemas.

If the test goes red, the failing assertion's message tells you which contract you broke. Fix the row, re-run, commit.

---

## 10. Related documents

- [Tier 3 assembly plan](../../plans/goaljudge_stage5_tier3_assembly.plan.md) — the full Phase 1-7 sequence; Phase 4 is the present guide.
- [Master Stage 5 plan §8](../../plans/goaljudge_stage5_goldset.plan.md) — original master spec for §8 "Phase 4 — dataset assembly".
- [Stage 5 spec §9](../goaljudge_stage5_goldset_spec.md) — the `GoldsetItem` schema this corpus feeds into at freeze time.
- [Goldset README](../../IAA/goalJudge/goldset/README.md) — the labeling-side process; Phase 4 produces what Phase 5 grades.
- `services/governance/goaljudge_goldset_dataset.py` — every validator cited in this guide.
- `tests/fixtures/goaljudge/fresh_test_tasks.py` — the seed corpus + the canonical authoring template.
