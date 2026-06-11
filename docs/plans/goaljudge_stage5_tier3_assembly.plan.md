# Plan — GoalJudge Stage 5 Tier 3: Assemble `goaljudge_goldset_v1`

> **Goal:** assemble, double-label, freeze, and load the **~250-item gold-set** that Stage 6 calibration consumes — meeting **Krippendorff's α ≥ 0.8 on `goal_met`** with a hash-frozen test split **and** measurable coverage across the pipeline's dimension space so Stage 6 can isolate the axis on which a regression appears.
> **Status:** Tier 1 PASS (pilot α=0.8846), Tier 2 **CLEARED** 2026-06-09 v7_full, Tier 3 **READY**. **Plan file only — no code changes yet.**
> **Scope owner:** the [Stage 5 master plan](goaljudge_stage5_goldset.plan.md) §8 (Phase 4 — assembly) defers the live runbook to this plan.

---

## Context

The Tier 2 unblock session produced (a) a confirmed A2 rubric, (b) two corrected agent fixes (planner per-task scoping + saturation `task_id` decoupling), and (c) enriched `eval.goal_judge` telemetry that now carries `final_answer`, `evidence_digest`, `tool_calls_summary`, `plan_steps` end-to-end. The motivating regression — a planner truncation that collapsed L2 prompts to L0 and dropped subtasks — was **dimension-specific** (axis D1 below). A 1-D, stratum-only gold set would not have detected it without luck. This plan therefore treats the pipeline's dimension space as a **first-class stratification axis**, alongside the spec §4 stratum/domain split.

Every prerequisite the master plan's Phase 4 listed as "before live run" is now in place:

| Prerequisite (master plan §8) | Status | Evidence |
|---|---|---|
| `failure_mode` schema seam landed | done | `components/schemas.py`, drift-guarded by `TestFailureModeEnumIntegrity` |
| Corpus export carries `failure_mode` | done | `scripts/export_goaljudge_corpus.py` |
| Langfuse dataset CRUD seam + firewall | done | `services/governance/goaljudge_goldset_dataset.py` (`GoldsetItem` validator enforces `synthetic ⇒ dev`) |
| α-computation script | done | `scripts/compute_goaljudge_stage5_alpha.py` |
| Pilot sheet builder | done | `scripts/build_goaljudge_stage5_pilot_sheet.py` |
| Pilot α ≥ 0.8 + guideline revision | done | `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md` (α=0.8846) |
| Stage 4 G5 κ ≥ 0.8 | done | κ=1.0 |
| Shadow §10.2 anchors PASS | done | 5/5 on goal_met rail (v7_full) |
| `eval.goal_judge` telemetry enrichment (`final_answer`, `evidence_digest`, `tool_calls_summary`, `plan_steps`) | done | Phase E.1 of Tier 2 unblock |

---

## The pipeline dimension space (read this before sizing)

Every gold-set item is a point in the cross-product of these dimensions. Stage 6 will slice metrics across them; the gold set must therefore **sample each cell that the production pipeline actually traverses** — otherwise P/R on `goal_met=False` is a single average masking a dimension-specific blind spot.

Each axis is sourced from existing code. No new dimensions invented.

| ID | Dimension | Values | Source of truth | Captured in `eval.goal_judge` today? |
|---|---|---|---|---|
| **D1** | **Planning depth** | `L0` · `L1` · `L2` | `components/router.py:select_planning_depth()` — heuristic on word count, multi-part markers, `,...and`/`,...then`, line count, `(1)…(2)…` enumerations | yes — `state["planning_depth"]`; mirrored into `gj_ai_input` via Phase E.1 (indirect, through `plan_steps` count) |
| **D2** | **Plan size (deterministic cap)** | int — `{L0: 1, L1: 3, L2: 5}` | `components/plan_builder.py:build_plan_artifact()` × `_extract_branches()` splitter | yes — `gj_ai_input.plan_steps` |
| **D3** | **Routing reason** | `budget-downgrade` · `retry-after-backoff` · `escalate-after-N-failures` · `capable-for-planning` · `steady-state-fast` (5-branch MECE) | `components/router.py:select_model()` | yes — `state["routing_reason"]`, log-line on `step.planned` |
| **D4** | **Model tier** | `fast` (default `gpt-4o-mini`) · `capable` | `ModelProfile.tier` in `services/base_config.py`; tier swaps logged via `model_history` | yes — `gj_ai_response.model_used` |
| **D5** | **Tool surface** | subset of `{file_io, file_tools, shell, web_search, think_tool, todo_tools, task_tool, request_approval}` | `services/tools/registry.py:ToolRegistry`; per-call recorded in `tool_results` | yes — `gj_ai_input.tool_calls_summary` (last 8: name + arg keys) |
| **D6** | **Budget pressure (cost fraction)** | float ∈ `[0.0, 1.0+]`; `≥ 0.8` triggers D3=`budget-downgrade` | `RoutingConfig.budget_downgrade_threshold = 0.8`; `state["total_cost_usd"]` / `agent_config.max_cost_usd` | **partial** — `total_cost_usd` is in step state but **not** in `gj_ai_input`. Closed by Phase 2.5 below |
| **D7** | **Failure mode** | 16-member enum (`GOAL_FAILURE_MODES`) | `components/schemas.py`; spec §3 Axis-A crosswalk | yes — `gj_ai_response.failure_mode` (Stage 4 v1: A2 dense, A1/A3/A4/A5 best-available) |
| **D8** | **Task stratum × domain (registry)** | `{representative, boundary, edge, impossible, red_team}` × `{file_io, math, web, shell, composite, knowledge}` | `tests/fixtures/goaljudge/case_registry.py` (`Case.stratum`, `Case.domain`); fresh tasks tagged by author | label-only — joined via registry, not in trace |

### Why this matters concretely

The Tier 2 unblock regression was a **D1-axis fault**: planner collapsed L2 to L0 on long-lived threads. The pilot's 50 items had no D1 stratification — they were sampled by D8 only. If the same regression surfaced in Stage 6 calibration on a similarly-stratified set, the false-downgrade-rate would have moved by maybe 1–2 % (well inside noise) and the §2.8 enable gates would have passed despite the bug.

Stratifying by D1 alone is not enough — D5 (tool surface) had its own carve-out (GJ-012 strict-pf carve-out because `web_search` is missing from the agent's tool selection). D7 (failure_mode) is mostly A2 today but the schema permits A1/A3/A4/A5 and Stage 6 must per-code; that's already in the spec §4. The plan **operationalizes** all of these as concrete coverage targets the builder asserts.

---

## Stratification matrix (sizing math)

### Primary 1-D allocation (spec §4 — unchanged)

| Stratum | Share | ~250 count | dev (synth-OK) | test (prod/fresh only) |
|---|---|---|---|---|
| Representative | 40 % | 100 | 60 | 40 |
| Boundary | 30 % | 75 | 45 | 30 |
| Edge | 20 % | 50 | 30 | 20 |
| Impossible | 10 % | 25 | 15 | 10 |
| **Total** | 100 % | **250** | **150 (≈60 %)** | **100 (≈40 %)** |

Goal_met-false oversample: registry is 38/50 false (76 %); the pilot landed annotator 1 at 40/50 false (80 %). Keep ≥ 60 % false in the gold set overall so per-code P/R is estimable.

### Secondary cell-coverage targets (D1 × D5, the dimensions Stage 6 will slice)

These are **minimums per cell**, not allocations — items can satisfy multiple cells. The minimums are sized for the spec's foundation §C.6 binomial-CI rule of thumb (n ≥ ~15 per cell for a usable per-cell estimate at 95 % CI).

**D1 cell minimums (planning depth):**

| Planning depth | Min items | Floor rationale |
|---|---|---|
| L0 | 60 | dominant production behavior; floor for "no regression hides here" power |
| L1 | 100 | the failure-mode regression vector (Tier 2 v6 bug was an L2→L0 collapse via L1) — generous coverage |
| L2 | 60 | rarer but high-value; the bug that broke v6 |

The L0+L1+L2 floors sum to 220, which fits inside 250. The remainder (~30) absorbs cell-overlap and double-coverage.

**D5 cell minimums (tool surface):**

| Cluster | Tool combination | Min items |
|---|---|---|
| file-only | `file_io` only | 25 |
| shell-bound | `shell` ± `file_io` | 30 |
| web-bound | `web_search` (must call) | 25 |
| no-tool | knowledge-only, **no tool calls** | 15 |
| compose | ≥ 2 distinct tool families (file + web, shell + web, file + shell + web) | 40 |
| wrong-tool | the agent picks the wrong verification tool (the GJ-012 pattern: ls when contents asked) | 20 |
| blocked-tool | tool exists but is blocked by allowlist/policy (the GJ-011 pattern) | 15 |
| `request_approval` (HITL) | items where the agent asks for human approval | 10 |

The `wrong-tool` and `blocked-tool` cells are **new explicit targets** — they were under-represented in the pilot and were the source of two of the Tier 2 strict-pf carve-outs. The `request_approval` cell exists because HITL is in `services/tools/hitl.py`; if Stage 6 never tests it, a HITL-specific regression cannot be detected.

**D7 cell minimums (failure_mode, where Stage 6 reports per-code P/R):**

Inherited from spec §3 — A2 dense (≥ 40 items across `subtask-dropped` / `partial-counted-as-full` / `fabricated-progress`), other axes best-available (≥ 5 per active code). Pilot already biased here; Phase 3 builder asserts the floor.

**D3, D4, D6 cells (runtime routing):**

These dimensions are mostly **emergent from the prompt** (the router decides them, not the author). The plan does **not** target per-cell minimums for D3/D4/D6 in the prompt-design step. Instead:

- The builder **records** the observed D3/D4/D6 values for every production-trace item from its trace.
- The plan **reports** the resulting distribution in the manifest (Phase 6) — so Stage 6 can decide whether to weight metrics or carve out under-sampled cells.
- If a production batch yields D3-distribution skewed (say, < 5 % of items hit `escalate-after-N-failures`), Phase 4's fresh-task authoring can author **escalation-bait prompts** (deliberately ambiguous or near-budget) to fill the gap.

This keeps the human-author burden bounded: authoring for D1/D5/D7 is feasible (these are properties of the task), authoring for D3/D4/D6 isn't (these are properties of the agent's response to the task).

### Source inventory and feasibility

| Source | Available items | Provenance | Eligible split | Naturally covers |
|---|---|---|---|---|
| Registry cases (`CASE_BY_ID`) | 50 (rep 20, boundary 11, edge 10, red_team 3, impossible 6) | synthetic (authors saw rubric) | **dev only** | D1: mixed (router decides per prompt); D5: file_io 16, shell 10, web 6, compose 8, no-tool 4, wrong-tool 4, blocked-tool 2 |
| Stress fixtures (`ALL_STRESS_CASES`) | 7 | synthetic | dev only | D5: red-team-heavy |
| Production batch traces (Tier 2 unblock batches + future) | ≈22/batch deduped by `case_id` | production | dev + test | D1/D3/D4/D6 emergent; D5/D7 inherited from registry prompt |
| **Fresh human-authored tasks** | **80 landed (2026-06-10)** | production | test split backbone | targets (D1, D5, D7) cells; see Phase 4 handoff |

The 100-item test split is the binding constraint. Path:
- 3 walkthrough re-batches × ≈22 unique cases ≈ 22–30 production traces (dedupe by case_id; production cases) → **~25 prod-trace test candidates**.
- Fresh-authored items aimed at the (D1, D5) cells that production traces under-fill → **~75 fresh test candidates**.

Concretely the Phase 4 authoring brief is going to look like *"author 25 L1-file_io tasks, 15 L2-compose tasks, 10 L0-no-tool tasks, …"* — not "author N items in stratum X."

---

## Reused, not reinvented (CRITICAL — read first)

- `services/governance/goaljudge_goldset_dataset.py:GoldsetItem` — pydantic model with firewall (`synthetic ⇒ dev`), enum validation, ge/le checks. **Do not** write a parallel item class.
- `services/governance/goaljudge_goldset_dataset.py:InMemoryLangfuseDatasetClient` — test double; the real wrapper plugs the same `LangfuseDatasetClient` Protocol.
- `components/router.py:select_planning_depth` — D1 source of truth; Phase 3 builder calls it to compute the *predicted* D1 for fresh tasks, so authors know the cell they're filling without running the agent.
- `components/plan_builder.py:build_plan_artifact` + `_extract_branches` — D2 source of truth.
- `components/router.py:select_model` — D3/D4 source of truth.
- `services/tools/registry.py:ToolRegistry` — D5 tool name list.
- `scripts/build_goaljudge_stage5_pilot_sheet.py` — FIELDS contract + row shape this plan's full builder extends.
- `scripts/compute_goaljudge_stage5_alpha.py` — already takes a CSV and emits α. No new α math.
- `scripts/export_goaljudge_corpus.py` — pulls registry-joined `eval.goal_judge`-bearing traces with `failure_mode`. Already wired.
- `tests/fixtures/goaljudge/case_registry.py:CASE_BY_ID` — D8 stratum/domain source.
- `agentsframework-playwright` skill — owns GCP walkthrough invocation, `RUN_TAG` discipline, screenshot capture, `verify_run.py` reconciliation.
- `services/evidence_digest.py:_summarize_evidence` (factored out in Phase E.1) — gold-set `evidence_digest` column uses this verbatim.

---

## Approach (seven phases, sequenced)

### Phase 1 — Real-SDK Langfuse dataset client (small, foundational)

**Goal:** ship the production wrapper that the in-memory client's Protocol shape was designed around, so Phase 6's load step has a target.

**Files:**
- `scripts/langfuse_dataset_client.py` (new) — `RealLangfuseDatasetClient` implementing the `LangfuseDatasetClient` Protocol from `services/governance/goaljudge_goldset_dataset.py`. Thin pass-through to `langfuse.api.dataset.create` / `langfuse.api.dataset_items.create`. Authentication via `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` env vars. **Host = `cloud.langfuse.com`** (not `us.cloud.langfuse.com` — past-session gotcha).
- `tests/services/test_goaljudge_goldset_dataset.py` — one Protocol-shape test (`isinstance(client, LangfuseDatasetClient)`). No live SDK calls in CI.

**Why under `scripts/` not `services/governance/`:** the governance module is langgraph/langchain-free by AGENTS.md invariant #4; the Langfuse SDK is an I/O surface that belongs at the script boundary. `services/` owns shape + invariants; `scripts/` owns provider I/O. The `GoldsetDatasetLoader.__init__(client: LangfuseDatasetClient)` injection keeps the boundary clean.

**Acceptance:** `pytest tests/services/test_goaljudge_goldset_dataset.py -q` green.

---

### Phase 2 — Test-split content-hash + dataset-integrity helper (small, foundational)

**Goal:** the master plan §6 / spec §9 says "content-hash the test split; diff the hash on every Stage-6 run" — but no helper exists. Author once, used by Phase 6 and every future Stage 6 run.

**Files:**
- `services/governance/goaljudge_goldset_dataset.py` — add module-level `compute_test_split_hash(items: Iterable[GoldsetItem]) -> str`. SHA-256 over `json.dumps(..., sort_keys=True, separators=(',', ':'))` of `[item.model_dump(exclude_none=False) for item in sorted_test_items]`. Sort by `item_id`.
- `tests/services/test_goaljudge_goldset_dataset.py` — three tests: stable (different insertion order → same hash); sensitive (one-field change → different hash); test-only (dev items in the input list ignored).

**Acceptance:** offline tests green.

---

### Phase 2.5 — Close the D6 telemetry gap (small, foundational)

**Goal:** `gj_ai_input` carries `final_answer`, `evidence_digest`, `tool_calls_summary`, `plan_steps` (Phase E.1) but **does not** carry the cost fraction. Stage 6 cannot slice metrics by D6 (budget pressure) from Langfuse alone. This is a 2-line edit that pays for itself the first time Stage 6 wants to ask "does the judge over-flag on budget-pressed runs?".

**Files:**
- `orchestration/react_loop.py:1322–1330` — extend `gj_ai_input`:
  ```python
  gj_ai_input = {
      ...,
      "plan_steps": len(plan_steps),
      "planning_depth": state.get("planning_depth", "L0"),  # D1 explicit
      "routing_reason": state.get("routing_reason", ""),    # D3
      "model_tier": _profile_tier(state),                   # D4
      "cost_fraction": round(state.get("total_cost_usd", 0.0) / max(agent_config.max_cost_usd, 1e-9), 3),  # D6
  }
  ```
  Note: `model_used` is already on `gj_ai_response`; `model_tier` is the categorical we want on the input side so the slicer doesn't have to re-look-up the tier from the model name.
- `tests/orchestration/test_react_loop_goal_judge.py` (or nearest) — extend the existing Phase E.1 shape test with the four new keys.

**Risk control:** all four values are already on `state` — no extra computation, no new redaction surface. Payload growth is bounded (4 keys × ~10 chars). `_redact_mapping` handles them.

**Acceptance:** offline tests green; one fresh GJ-012 smoke shows the four new keys in the Langfuse `eval.goal_judge.input` payload.

---

### Phase 3 — Full ~250-item corpus join + cell-aware stratifier (medium)

**Goal:** scale the pilot sheet builder from 50 rows to ~250 rows, with cell-coverage checks against D1, D5, D7 — not just D8.

**Files:**
- `scripts/build_goaljudge_stage5_full_sheet.py` (new) — extends `build_goaljudge_stage5_pilot_sheet.py` patterns. Differences:
  - Reads **multiple** batch JSONLs (env `GOALJUDGE_BATCH_JSONLS` = comma-separated, or a directory). Dedupes by `(case_id, trace_id)`; keeps most-recent batch by file mtime.
  - Reads **fresh-authored tasks** from `tests/fixtures/goaljudge/fresh_test_tasks.py` (added in Phase 4); merges them as `provenance=production` and `split=test` candidates.
  - **Computes predicted D1 (`planning_depth`) for each fresh task** by calling `components.router.select_planning_depth(task_input=..., task_tool_results_count=0)`. For production-trace items, reads observed D1 from the joined batch JSONL's `planning_depth` field (already emitted by react_loop).
  - **Records observed D3/D4/D6 from the trace** for production items; leaves these fields blank for synthetic / unrun fresh items.
  - **Records D5 (tool family)** from `tool_calls_summary` for production items; for fresh items, the author tags an `expected_tool_cluster` ∈ `{file-only, shell-bound, web-bound, no-tool, compose, wrong-tool, blocked-tool, request_approval}` (Phase 4 fixture schema).
  - **Stratification step:** bucket all rows by:
    1. Primary: `stratum` (D8) — gap report vs spec §4 share targets.
    2. Secondary: `(predicted_d1, tool_cluster)` — gap report vs the D1/D5 cell minimums above.
    3. Tertiary: `failure_mode` (D7) — gap report vs spec §3 A2-dense / A1-A5 best-available.
  - **Emits `cache/goaljudge_eval/goldset_cell_coverage_report.md`** with:
    - per-stratum count + gap
    - per-(D1 × D5-cluster) matrix with min/actual/gap
    - per-failure_mode count + gap
    - per-D3 / per-D4 / per-D6-bin distribution (informational; no gap targets)
  - **Split assignment:** firewall — every `provenance=synthetic` row gets `split=dev`. Among `provenance=production` rows, the test split is filled by a **deterministic per-cell allocator**: walk the (D1, D5-cluster) cells in a fixed order; for each, take the first `ceil(0.4 × min)` items by sorted `item_id`. This keeps cells balanced in the test split too — avoids a test split that's all L0-file_io.
- `scripts/build_goaljudge_stage5_full_sheet.py:CELL_MINIMUMS` — module constant encoding the D1 × D5-cluster matrix from the sizing table above; tweakable in one place.
- Output: `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv` (extended FIELDS — see below) + the coverage report.

**Extended FIELDS** (additive to the pilot sheet's columns):

| New column | Source | Used by |
|---|---|---|
| `planning_depth` | trace (prod) or `select_planning_depth()` (fresh) | D1 cell-coverage check |
| `plan_steps` | trace `plan_steps` or `len(_extract_branches(...))` for fresh | D2 sanity (≥ predicted D1's max) |
| `routing_reason` | trace; blank for fresh-unrun | D3 distribution |
| `model_tier` | trace; blank for fresh-unrun | D4 distribution |
| `cost_fraction` | trace `total_cost_usd / max_cost_usd`; blank for fresh-unrun | D6 distribution |
| `tool_cluster` | tagged in fresh fixture; derived for prod from `tool_calls_summary` | D5 cell-coverage check |

**Pre-acceptance dry-run:** `--dry-run` emits only the cell-coverage report — so Phase 4 authoring knows which (D1, D5-cluster) cells need items before any author writes a prompt.

**Acceptance:** builder runs against existing batches + fresh fixtures; cell-coverage report shows every (D1, D5-cluster) cell ≥ its minimum (or documented carve-out); firewall asserted at write time.

---

### Phase 4 — Cell-targeted fresh-task authoring (medium, human-paced)

**Goal:** author ~80 fresh tasks — **targeted by (D1, D5-cluster, stratum) cells the production-trace pool under-fills** — reusing public-benchmark schemas (spec §8) but not items. This is the test-split backbone.

**Files:**
- `tests/fixtures/goaljudge/fresh_test_tasks.py` (new) — exports `FRESH_TEST_TASKS: list[FreshTask]`. Each entry:
  ```python
  FreshTask(
      id: str,                    # e.g. "GJ-F-001"
      prompt: str,
      stratum: Literal["representative", "boundary", "edge", "impossible"],  # D8
      domain: Literal["file_io", "math", "web", "shell", "composite", "knowledge"],  # D8
      expected_planning_depth: Literal["L0", "L1", "L2"],  # D1 author intent (validated against select_planning_depth)
      expected_tool_cluster: Literal[                       # D5 cluster
          "file-only", "shell-bound", "web-bound", "no-tool",
          "compose", "wrong-tool", "blocked-tool", "request_approval"
      ],
      expected_failure_mode: str | None,                    # D7 — one of GOAL_FAILURE_MODES or null
      source_benchmark_schema: Literal[                     # spec §8
          "tau-bench", "the-agent-company-checkpoint",
          "webarena-impossible", "agentboard-subgoal", "novel"
      ],
  )
  ```
- `docs/research/goaljudge_stage5_goldset/fresh_task_authoring_guide.md` (new) — discipline document:
  - **Cell-driven brief:** Phase 3's coverage report names the cells short. Authors write to that list, not free-form. Example: "we need 8 more `(L2, compose, edge)` items — write tasks that explicitly chain ≥ 3 tool families on a rare combination."
  - **D1 validation:** every fresh task's `expected_planning_depth` is checked against `select_planning_depth(prompt, 0)`; if they disagree, the task is rejected (the rubric authors' D1 prediction must match the router's). This prevents the gold set from drifting away from production behavior.
  - **D5 cluster definition table** — concrete examples per cluster so authors stay consistent.
  - **Contamination guard:** each fresh task must be distinct in surface form from any `CASE_BY_ID` prompt (Jaccard < 0.5). Drift-guarded.
  - Strata target distribution: rep 40, boundary 30, edge 20, impossible 10 (= 100 fresh test candidates; budget **80 hard, 20 stretch**).
- `tests/fixtures/goaljudge/test_fresh_task_authoring.py` (new) — drift-guards:
  - Required keys present per entry.
  - `expected_planning_depth` matches `select_planning_depth(prompt, 0)`.
  - `expected_tool_cluster` ∈ allowed set.
  - `expected_failure_mode` ∈ `GOAL_FAILURE_MODES ∪ {None}`.
  - `source_benchmark_schema` ∈ allowed set.
  - No prompt with > 0.5 Jaccard overlap to any `CASE_BY_ID[*].prompt`.
  - Per-(D1, D5-cluster) coverage hits the per-cell minimums OR the cell is explicitly excused in a `CARVED_OUT_CELLS` constant with a written rationale.

**Acceptance:** drift-guard tests pass; `--dry-run` on Phase 3 builder shows zero gaps (or only excused carve-outs).

**Risk:** human authoring is the longest pole. Floor: **60 fresh items** (vs 80 target); test split shrinks to ~80 production-only items (32 % of 250) — still inside spec §6 60/40 tolerance band as a slight tilt to dev.

#### Phase 4 handoff (2026-06-10 — M5 complete)

**Corpus:** `tests/fixtures/goaljudge/fresh_test_tasks.py` — **80** `FreshTask` rows (`GJ-F-001`…`100` with §6 gaps; no renumbering). Authored 100, dropped **20** in §6 review using priority order **wrong-tool > HITL > stratum**.

**D5 cluster spread (80 items):**

| cluster | count | §6 note |
|---|---:|---|
| `compose` | 26 | includes 5 messy-English L2 (096–100) |
| `file-only` | 15 | |
| `shell-bound` | 11 | |
| `web-bound` | 8 | |
| `no-tool` | 7 | |
| `wrong-tool` | **5** | kept sharp traps: 068, 070, 072, 074, 075 |
| `blocked-tool` | **4** | kept: 080, 081, 084, 086 |
| `request_approval` | **4** | kept high-stakes: 088–091 |

**D8 stratum (actual vs `STRATA_SHARES` × 80):** representative **32/32** ✓ · boundary **22/24** (−2, carved) · edge **23/16** (+7, carved) · impossible **3/8** (−5, carved; 076 dropped in §6).

**Carve-outs (documented in gap report):** edge overweight and impossible under-target accepted to preserve wrong-tool trap quality and messy-English L2 coverage; weak HITL boundary rows (092–095) dropped; `request_approval` runtime registry gap noted for Phase 5 labeling (`note` column: grade on approval ask / refusal intent).

**Verification:** `pytest tests/services/test_fresh_task_authoring.py -q` → 9 passed; `pytest tests/components/test_router_d3_mece_review.py -q` → 6 passed; full repo **2479** passed. Pairwise fresh Jaccard worst **0.441** (019 vs 025) < 0.5.

**Artifacts:** [`cache/goaljudge_eval/goldset_cell_coverage_report.md`](../../cache/goaljudge_eval/goldset_cell_coverage_report.md) (fresh-only snapshot); D3 MECE review fixtures in `tests/fixtures/goaljudge/d3_routing_review_cases.py`.

**Next:** Phase 5 — distribute full sheet per [`full_set_labeling_protocol.md`](../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md); re-run Phase 3 builder dry-run when GCP batch JSONLs are merged for combined D1/D5 gap closure.

---

### Phase 5 — Full double-labeling + α gate (medium, human-paced)

**Goal:** the same 2 annotators from the pilot label all ~250 items blind; α ≥ 0.8 on `goal_met`; adjudication produces the gold column.

**Files / artifacts:**
- `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv` — produced in Phase 3; `r1_*` + `r2_*` filled here.
- `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_results.md` — currently a stub; fill with same shape as `goaljudge_stage5_goldset_pilot_results.md` (status banner, scope, α table, annotator summary, disagreement post-mortem, execution appendix). Status banner flips from BLOCKED → PASS at the end.
- `scripts/apply_goaljudge_stage5_annotator{1,2}_full_grades.py` (new) — extends pilot apply scripts; separate scripts per annotator so each can re-grade independently.

**Procedure** (mirrors pilot, with refined guidelines from pilot's disagreement post-mortem):

1. Distribute the empty-`r*` sheet + `goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md` + pilot's disagreement post-mortem to both annotators.
2. Annotators label blind, each scoping their own `r1_*` or `r2_*` columns.
3. Run `compute_goaljudge_stage5_alpha.py` against the labeled sheet.
4. **If α < 0.8:** revise guidelines on the disagreements (EvalGen co-construction loop); add disambiguating examples to `docs/IAA/goalJudge/goldset/README.md`; re-label **only the disagreement rows**. Recompute α.
5. **If α ≥ 0.8:** adjudicate disagreements to `adjudicated_goal_met` / `adjudicated_failure_mode`; that column becomes the gold label.
6. **Cell-coverage check on the adjudicated set:** rerun the Phase 3 cell-coverage report against the **adjudicated `goal_met=false` subset** (Stage 6's primary metric class). Every D1, D5-cluster, D7 cell that the spec requires for per-code/per-axis P/R must have ≥ 5 `goal_met=false` items (or carve-out). This is a quality check on the labeling, not the sourcing — if the label distribution collapses a cell, fresh authoring extension may be needed before freeze.

**Guideline refinements carried forward** (from pilot results):
- "Scaffold items with explicit process constraints default to process-verified `goal_met=false` unless the task text is purely outcome-only." (GJ-052)
- "Computation items requiring tool evidence default to `goal_met=false` if the answer is correct but unverified by tool." (GJ-039)
- Member-code disagreement within an agreed `goal_met=false` is **not** an α disagreement (Stage 4 convention).
- **New (dimension-aware):** "If a task is L2 by router prediction but the trace shows the agent executed it at L0, grade based on the **observed batch behavior** (Stage 4 working rule), not against the L2 intent. Note `planner_truncation_suspected` in the row's `note` column for Phase E.2-style follow-up."

**Acceptance:** α ≥ 0.8 on `goal_met` across all ~250 items; adjudicated columns fully populated; cell coverage check on `goal_met=false` subset passes; results doc filled; sheet committed.

---

### Phase 6 — Assemble, freeze, load, verify (small once Phases 1–5 done)

**Goal:** turn the adjudicated CSV into `GoldsetItem` rows, assert all invariants (including cell-coverage), content-hash the test split, load into Langfuse, record the manifest Stage 6 diffs against.

**Files:**
- `scripts/assemble_goaljudge_goldset.py` (new) — single-shot:
  1. Read `goaljudge_stage5_goldset_full_sheet.csv`.
  2. For each row, construct `GoldsetItem(...)` — pydantic `model_validator(mode="after")` enforces `synthetic ⇒ dev` (the firewall).
  3. **Assert cell-coverage invariants** at the integration boundary (defense in depth — they were also asserted at builder time):
     - Per-D1 minimum: `count_by("planning_depth")` ≥ `{L0: 60, L1: 100, L2: 60}` (or fewer items total).
     - Per-D5-cluster minimum: per-cluster count ≥ matrix above.
     - Per-D7 minimum: A2 codes ≥ 40 combined; other-active codes ≥ 5 each.
     - `goal_met=false` ≥ 60 % of total.
     - `test ∩ synthetic == ∅`.
     - `set(item_ids)` no duplicates.
  4. Compute `compute_test_split_hash(items)` (Phase 2).
  5. Authenticate `RealLangfuseDatasetClient` (Phase 1) via env.
  6. `GoldsetDatasetLoader(client=...).upsert_many(items)`.
  7. Verify Langfuse counts match CSV counts.
  8. Write `cache/goaljudge_eval/goldset_v1_manifest.json`:
     ```json
     {
       "dataset_name": "goaljudge_goldset_v1",
       "total_items": 250,
       "dev_count": 150,
       "test_count": 100,
       "test_split_sha256": "...",
       "rubric_version": "stage4_confirmed",
       "frozen_at": "2026-MM-DDThh:mm:ssZ",
       "stratum_distribution": {...},
       "planning_depth_distribution": {"L0": 62, "L1": 105, "L2": 83},
       "tool_cluster_distribution": {...},
       "failure_mode_distribution": {...},
       "routing_reason_distribution_observed": {...},  // informational (prod items only)
       "model_tier_distribution_observed": {...},      // informational
       "cost_fraction_bins_observed": {...},           // informational
       "goal_met_false_share": 0.62
     }
     ```
- `tests/services/test_goaljudge_goldset_dataset.py` — extend with **end-to-end shape test**: 10-row CSV fixture, assemble, assert all invariants pass, assert manifest has all keys including the new distribution dicts.
- `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_results.md` — append "Dataset frozen" section with manifest excerpt + SHA-256.
- `docs/plans/goaljudge_stage5_goldset.plan.md` §13 — flip `assemble-goldset` and `alpha-gate-full` from `ready`/`pending` to `done ✓`.

**Acceptance:**
- `assemble_goaljudge_goldset.py` exits 0; manifest written; cell-coverage assertions hold; firewall holds; Langfuse dataset visible at `cloud.langfuse.com/datasets/goaljudge_goldset_v1`.
- Offline integration test green.
- Tier 3 = **CLEARED**; Stage 6 calibration unblocked.

---

### Phase 7 — Documentation flip (small)

Flip the three docs whose status banners need to change once Tier 3 closes:

1. `docs/reports/goaljudge_stage5_goldset_tier_review.md` — Tier 3 row READY → CLEARED with the manifest reference.
2. `docs/IAA/goalJudge/goldset/README.md` — status banner: full set α PASS, test split hashed and frozen.
3. `docs/plans/goaljudge_stage5_goldset.plan.md` — §3 mermaid (Tier 3 subgraph) and §13 checklist rows.

Append "Stage 6 calibration is now unblocked" with a pointer to the (separate, yet-to-be-written) Stage 6 plan.

---

## Critical files

| File | Phase | Change shape | Net new vs edit |
|---|---|---|---|
| `scripts/langfuse_dataset_client.py` | 1 | Real-SDK wrapper implementing `LangfuseDatasetClient` Protocol | new |
| `services/governance/goaljudge_goldset_dataset.py` | 2, 6 | Add `compute_test_split_hash`; extend with cell-coverage validators called from assemble | edit |
| `orchestration/react_loop.py` | 2.5 | Add D1/D3/D4/D6 keys to `gj_ai_input` (4 lines) | edit |
| `tests/orchestration/test_react_loop_goal_judge.py` | 2.5 | Extend Phase E.1 shape test | edit |
| `scripts/build_goaljudge_stage5_full_sheet.py` | 3 | Multi-batch join + cell-aware stratifier + extended FIELDS + coverage report | new |
| `tests/fixtures/goaljudge/fresh_test_tasks.py` | 4 | Authored 80–100 fresh tasks targeted at (D1, D5-cluster) cells | new |
| `tests/fixtures/goaljudge/test_fresh_task_authoring.py` | 4 | Drift-guards (router agreement, Jaccard, cell-coverage) | new |
| `docs/research/goaljudge_stage5_goldset/fresh_task_authoring_guide.md` | 4 | Authoring discipline doc | new |
| `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv` | 3, 5 | The labeled CSV (extended columns) | new |
| `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_results.md` | 5, 6 | Stub → filled results | edit |
| `scripts/apply_goaljudge_stage5_annotator{1,2}_full_grades.py` | 5 | Per-annotator regrade helpers | new |
| `scripts/assemble_goaljudge_goldset.py` | 6 | Assemble/freeze/load/manifest with cell-coverage assertions | new |
| `tests/services/test_goaljudge_goldset_dataset.py` | 1, 2, 6 | Protocol-shape + hash + e2e-shape + cell-coverage tests | edit |
| `docs/plans/goaljudge_stage5_goldset.plan.md` | 7 | §13 checklist + §3 mermaid Tier 3 → CLEARED | edit |
| `docs/reports/goaljudge_stage5_goldset_tier_review.md` | 7 | Tier 3 row CLEARED | edit |
| `docs/IAA/goalJudge/goldset/README.md` | 7 | Status banner | edit |

---

## Verification (end-to-end)

Run in order; only proceed past a step if it passes.

1. **Phase 1+2 unit-level:**
   ```bash
   .venv/bin/python -m pytest tests/services/test_goaljudge_goldset_dataset.py -q
   ```
   Green; Protocol-shape + hash tests pass.

2. **Phase 2.5 unit-level + smoke:**
   ```bash
   .venv/bin/python -m pytest tests/orchestration/test_react_loop_goal_judge.py -q
   ```
   Green. Then redeploy backend; run one Playwright smoke; confirm new keys in Langfuse `eval.goal_judge.input`.

3. **Phase 3 dry-run (read-only):**
   ```bash
   GOALJUDGE_BATCH_JSONLS="cache/goaljudge_eval/ui_batch_gcp_2026-06-09.jsonl,cache/goaljudge_eval/ui_batch_gcp_confirmation_2026-06-09_v7_full.jsonl" \
     .venv/bin/python scripts/build_goaljudge_stage5_full_sheet.py --dry-run
   ```
   Inspect `goldset_cell_coverage_report.md`; confirm the (D1, D5-cluster) gap matches Phase 4's authoring target.

4. **Phase 4 fixture lands:**
   ```bash
   .venv/bin/python -m pytest tests/fixtures/goaljudge/test_fresh_task_authoring.py -q
   ```
   Drift-guards pass (router-agreement check, Jaccard, cell coverage).

5. **Phase 3 real-run (after Phase 4):**
   ```bash
   GOALJUDGE_BATCH_JSONLS="..." .venv/bin/python scripts/build_goaljudge_stage5_full_sheet.py
   ```
   Sheet + coverage report emitted; firewall asserted at write time; cell coverage report green.

6. **Phase 5 α gate:**
   ```bash
   .venv/bin/python scripts/compute_goaljudge_stage5_alpha.py \
     docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv
   ```
   `gate=PASS (threshold α ≥ 0.8)`; results doc filled.

7. **Phase 5 post-adjudication cell-coverage check:**
   ```bash
   .venv/bin/python scripts/build_goaljudge_stage5_full_sheet.py --recheck-coverage \
     --against-column adjudicated_goal_met --filter false
   ```
   Every D1, D5-cluster, D7 cell required by spec has ≥ 5 `goal_met=false` items (or carve-out).

8. **Phase 6 offline integration:**
   ```bash
   .venv/bin/python -m pytest tests/services/test_goaljudge_goldset_dataset.py::TestGoldsetAssembly -q
   ```
   E2E-shape test green; cell-coverage assertions fire.

9. **Phase 6 live freeze + load** (gated on user approval — touches Langfuse cloud):
   ```bash
   .venv/bin/python scripts/assemble_goaljudge_goldset.py
   ```
   Manifest written; Langfuse dataset visible.

10. **No regressions in broader offline surface:**
    ```bash
    .venv/bin/python -m pytest tests/components/test_goal_judge.py \
      tests/components/test_goal_judge_redteam_offline.py \
      tests/components/test_goal_judge_shadow_offline.py \
      tests/components/test_goal_judge_stress_offline.py \
      tests/services/test_goaljudge_goldset_dataset.py \
      tests/orchestration/test_react_loop_goal_judge.py -q
    ```
    All green.

11. **Phase 7 final state:** `docs/plans/goaljudge_stage5_goldset.plan.md` §13 shows `assemble-goldset` and `alpha-gate-full` both `done ✓`. `docs/reports/goaljudge_stage5_goldset_tier_review.md` Tier 3 = CLEARED.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Cell-coverage targets too aggressive — no feasible authoring path** | Phase 3's `--dry-run` runs before any authoring; if any cell minimum exceeds the practical authoring budget, document a `CARVED_OUT_CELLS` carve-out with rationale before authors start writing |
| **Author's `expected_planning_depth` disagrees with `select_planning_depth`** | Drift-guard test fails the build; author rewrites the prompt until router agrees. Prevents gold set drifting from production behavior — and surfaces router-heuristic edge cases worth fixing |
| **`select_planning_depth` heuristic changes after Tier 3 freeze (router refactor)** | The frozen sheet records the D1 *value at freeze time*; Stage 6 reports as-of-freeze. A router change triggers a Stage 5 re-run (re-import test column, re-check cell coverage). Manifest carries `rubric_version=stage4_confirmed` + a `router_heuristic_version` (introduce in Phase 3) for traceability |
| **Production batches under-represent escalation (D3) or capable-tier (D4)** | These are emergent; the manifest reports observed distribution. If skewed (say, < 5 % `escalate-after-N-failures`), Phase 4 can author escalation-bait prompts (ambiguous, near-budget, repeated tool failures) to bias the production-rerun distribution |
| **`request_approval` cell is unfillable from natural prompts** | HITL is a rare tool. Floor at 10 items; if production batches yield 0, fresh-author 10 explicit HITL prompts (provenance=production but author-written) — they cover the test split for that cluster |
| **Fresh-task authoring is long-pole and slips** | Floor at 60 fresh items (vs 80 target); tilt dev/test to ~64/36 — still within spec §6 60/40 tolerance |
| **Annotator α < 0.8 despite pilot PASS** | Re-label only disagreement rows; refine guidelines (EvalGen co-construction). Prompt stays shipped — flag is default-off, no prod impact |
| **Synthetic items leak into test split** | Defense in depth: pydantic `model_validator` rejects at construction; `compute_test_split_hash` runs on the final validated list; assemble script asserts `test ∩ synthetic == ∅` explicitly |
| **Fresh task accidentally duplicates a registry prompt** | Phase 4 drift-guard (`test_fresh_task_authoring.py`) Jaccard < 0.5 against every `CASE_BY_ID` prompt — fails the test |
| **Langfuse SDK credentials missing in CI** | Real client only constructed inside `assemble_goaljudge_goldset.py` (manual run). All tests use `InMemoryLangfuseDatasetClient`. No live calls in CI |
| **Test-split hash silently changes (test split tuned on)** | Manifest carries `test_split_sha256`; Stage 6 must recompute and diff before every run (caller responsibility — flagged in Stage 6 plan) |
| **Class imbalance hides per-cell judge weakness** | Cell-coverage assertions at assemble time prevent under-sampled cells from freezing; Stage 6 reports per-cell metrics, not single average |
| **Member-code disagreement counted as α disagreement** | α script operates on `goal_met` alone (verified at pilot); failure_mode is metadata |
| **`goal_judge_downgrade_enabled` flipped after Tier 3 PASS** | Out of scope. §2.8 enable gates from Stage 6 calibration still required |

---

## What this plan does *not* do

- Does not run Stage 6 calibration (P/R/F1 per D7, ECE, flip-rate per cell). Separate plan once Tier 3 clears.
- Does not flip `goal_judge_downgrade_enabled`. Requires Stage 6 + §2.8 enable gates.
- Does not extend the rubric to A1/A3/A4/A5 categories. Schema supports them; v1 labels best-available.
- Does not change `CASE_BY_ID` `target_axes` — registry remains spec-anchored.
- Does not change `select_planning_depth` or `select_model` heuristics. Tier 3 reads them as truth; any heuristic change is a separate plan and triggers a Stage 5 re-run.
- Does not author a Stage 5 recipe (master plan's `stage5-recipe` is **optional**). A future `09_dimension_aware_gold_set.md` recipe could follow this plan's merge — bookkeeping, not a gate.

---

## Suggested PR sequence

1. **Phase 1 + 2 + 2.5** combined PR — small, foundational, no human work. (Real-SDK wrapper + test-split hash + 4-key `gj_ai_input` extension + tests.)
2. **Phase 3** — full sheet builder + cell-aware stratifier + dry-run coverage report. Reviewable even before Phase 4 lands.
3. **Phase 4** — fresh-task authoring fixture + guide + drift-guards (router-agreement, Jaccard, cell coverage). Largest single PR; held until ~80-item target met.
4. **Phase 5** — labeling round 1 (no PR until α ≥ 0.8); guideline-revision PRs in between iterations.
5. **Phase 6** — assemble + freeze + load + manifest + assertions. Gated on Phase 5 PASS. User-owned because it touches Langfuse cloud.
6. **Phase 7** — doc flip. Trivial; same PR as 6 or immediately after.

PRs 1–3 may land while Phase 4 authoring is in progress. PR 5 is the live human round. Hand off to Stage 6 calibration (separate plan).

---

## References

- [Stage 5 master plan §8 — Phase 4 assembly](goaljudge_stage5_goldset.plan.md#8-phase-4--dataset-assembly-and-contamination-firewall) — the runbook this plan operationalizes.
- [Gold-set spec §4 stratification, §6 size, §7 α, §9 field contract](../research/goaljudge_stage5_goldset_spec.md).
- [Stage 5 goldset README (live protocol)](../IAA/goalJudge/goldset/README.md).
- [Pilot α results — α=0.8846 PASS](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md).
- [Stage 4 G5 κ — κ=1.0 PASS](../IAA/goalJudge/goaljudge_stage4_a2_iaa_results.md).
- [Tier 2 unblock session report](../reports/goaljudge_stage5_tier2_unblock_session_report.md) — motivating evidence that dimension-specific regressions exist and a 1-D gold set misses them.
- [Tier review matrix](../reports/goaljudge_stage5_goldset_tier_review.md).
- [Foundation doc — gold-set + rubric research](../research/rubricgoldsetreseachforgoaljudge.md).
- **Source-of-truth code (each dimension):**
  - D1 — `components/router.py:select_planning_depth`
  - D2 — `components/plan_builder.py:build_plan_artifact` + `_extract_branches`
  - D3, D4 — `components/router.py:select_model` (5-branch MECE)
  - D5 — `services/tools/registry.py:ToolRegistry`
  - D6 — `services/base_config.py:AgentConfig.max_cost_usd` + `RoutingConfig.budget_downgrade_threshold`
  - D7 — `components/schemas.py:GOAL_FAILURE_MODES`
  - D8 — `tests/fixtures/goaljudge/case_registry.py`
