# T3 Supervisor / Parallel Fan-out — Implementation & Validation Plan

> **Status.** Build-ready, step-by-step execution plan for Phase 4 (T3). This is the *do-this-then-that* doc.
> It does **not** re-derive the *why* (plan §3.5a), the *protocol bindings* (design §A/§B.5), or the *component
> contract* (`t3_supervisor_plan.component.md`) — it **cites** them and turns them into ordered, testable steps
> against the **real current source** (every line ref below was read from the tree on 2026-06-15, not assumed).
>
> **Date:** 2026-06-15. **Owns:** the implementation order, the exact edits per file, the test-first sequencing,
> and the two-stage validation (offline CI + live GCP calibration). **Companions (read first):**
> - [`planning_pipeline_tiered_loops.plan.md`](planning_pipeline_tiered_loops.plan.md) §3.5a — decision + honest
>   acceptance bar (seam + layer-clean + observable + MAST-bounded, **NOT throughput**).
> - [`planning_pipeline_tiered_loops.design.md`](planning_pipeline_tiered_loops.design.md) §A (protocol registry),
>   §B.5 (T3 crosswalk + the 3 fan-out diagrams).
> - [`planning_pipeline_tiered_loops.impl.md`](planning_pipeline_tiered_loops.impl.md) §7 — the file-level sketch
>   this plan executes (§7.1–7.8).
> - [`t3_supervisor_plan.component.md`](t3_supervisor_plan.component.md) — `plan_delegations` / `validate_independence`
>   signatures + the decline-first decision table + `detect_sequential_dependence` (§3a).
> - [`t3_fanout_corpus.plan.md`](t3_fanout_corpus.plan.md) — the validation workload (✅ built: 29 `phase="fanout"`
>   rows) + the run-path (§8) + the open-coding pass (§9).
>
> **Layering authority:** [`AGENTS.md`](../../AGENTS.md) (invariants 1–8, AP-5, TAP-4), [`FOUR_LAYER`](../Architectures/FOUR_LAYER_ARCHITECTURE.md)
> (delegation lives in Services+Orchestration, L159; T3 is single-supervisor map-reduce, **not** the deferred
> peer-to-peer of L1078), [`tdd_agentic_systems_prompt.md`](../../research/tdd_agentic_systems_prompt.md)
> (Protocol C/D, P1/P6/P7/P11).

---

## 0. What already exists (so we build the thin delta, not a subsystem)

The delegation substrate is **already shipped** — this was verified by reading source, and it changes the plan
materially (the impl sketch under-counted what's reusable). The T3 build is a *thin orchestration topology over
existing services*, exactly as FOUR_LAYER L159 prescribes.

| Concern | Already exists | File:line (verified 2026-06-15) | T3 reuses it how |
|---|---|---|---|
| Delegation envelope | `DelegationDispatchRequest` (`correlation_id`, `objective`, `subagent_type`, `constraints`, `expected_output_schema`, `task_id`, `user_id`) | [`delegation_dispatcher.py:24-33`](../../services/tools/delegation_dispatcher.py) | the `Delegation` component model maps 1:1 onto these fields (component spec §1) — worker hands it straight through |
| Worker execution | `LocalLLMDelegationDispatcher.dispatch()` → `_invoke_worker()` (already `async`), returns `{status, output, error, child_correlation_id}` | [`delegation_dispatcher.py:51-73, 91-105`](../../services/tools/delegation_dispatcher.py) | `worker_node` calls it; only change = add an `async def dispatch` (§3) |
| Policy / budget / allowlist gates | `_gate_policy` / `_gate_budget` / `_gate_subagent_allowlist` + budget keys (`delegation_max_cost_usd`, `delegation_call_count`, `delegation_max_calls_per_task`) | [`task_tool.py:66-115`](../../services/tools/task_tool.py) | the deny path already emits `delegation_denied` → reuse, do not re-invent |
| `delegation_*` trace carriers | `delegation_requested` / `delegation_completed` / `delegation_denied` / `delegation_dispatch_failed` / `delegation_reconciled` already emitted | [`task_tool.py:138-270`](../../services/tools/task_tool.py) | the GTP carriers T3 needs **already export**; the work is making them fire **per branch** with the branch `correlation_id` |
| Filesystem handoff | `.agent_handoff/{correlation_id}` convention | [`task_tool.py:127-128`](../../services/tools/task_tool.py) | OBP-M3 (handoff via filesystem/state, never a call-back) is already the shipped shape |
| State budget keys | `delegation_max_cost_usd` / `delegation_call_count` / `delegation_max_calls_per_task` read from state | [`task_tool.py:80-86`](../../services/tools/task_tool.py) | `max_concurrency` (plan §3.5a) bounds fan-out against these |

**Consequence:** T3 adds exactly **one new component**, **one new state key**, **one async method**, and
**three thin nodes + edge rewiring**. Everything else is reuse. The headline risk is *not* plumbing — it is the
**decline decision** (the GAIA guard) and the **superstep-cancellation** failure path.

**Two facts the impl sketch missed, now load-bearing for the steps below:**

1. **`Send` is NOT imported in `react_loop.py`.** [Line 20](../../orchestration/react_loop.py) imports only
   `END, START, StateGraph` from `langgraph.graph`. Step 5 adds `Send` to that import — a real, reviewable diff,
   and the *only* new langgraph surface T3 introduces.
2. **`route → call_llm` is a HARD edge, not conditional.** [Line 2135](../../orchestration/react_loop.py):
   `builder.add_edge("route", "call_llm")`. To fork to the supervisor off `route`, that hard edge must become an
   `add_conditional_edges("route", _route_to_supervisor, {"fan_out_candidate": "supervisor", "direct": "call_llm"})`.
   This is the single most invasive edit (it touches the existing spine) — it is **additive in behavior** (the
   `direct` branch is byte-identical to today) but it is *not* a pure append, so it carries the most regression
   risk and gets the most failure-first coverage (Step 7, the "decline → identical to today" topology test).

---

## 0.5 Required workspace skills (which one governs which step)

Four workspace skills are **load-bearing** for T3 — each owns a phase of validation and carries hard-won gotchas
this plan must obey, not paraphrase. Invoke the skill (read its `SKILL.md`) at the step it governs; the plan cites
the specific rule, the skill is the authority.

| Skill | Governs | When (step) | The non-negotiable it brings |
|---|---|---|---|
| [`deploy-gcp`](../../.cursor/skills/deploy-gcp/SKILL.md) "Tiered-Loops Stress Revision" | Standing up the loops+T3-on backend **and frontend** stress revisions | Stage B step 1 | A loops-on e2e run needs **TWO** zero-traffic revisions (backend tag + a frontend tag whose `MIDDLEWARE_URL` points at the backend tag), `fill_stress_profile_url.py` to read the real hash, and **teardown of both tags** after. Never flip flags on the prod-traffic revision. |
| [`playwright-agentic-e2e`](../skills/playwright-agentic-e2e/SKILL.md) | Writing/running the fan-out e2e against the live backend | Stage B steps 2–4 | The fan-out run is a **T3 full-stack cut** (nothing mocked, live model) → on-demand / release-gate **only**, never per-commit CI. Assert **structure + provenance, not exact LLM prose**; wait by **settle-poll, not `finished()`**; scope to `article div[aria-live="polite"]` (not the Next.js route announcer). Cross-check the backend via `scripts/verify_run.py`. |
| [`governance-trace-audit`](../skills/governance-trace-audit/SKILL.md) | Auditing the fan-out trace's instrumentation | Stage C | **Corrupt-success check FIRST** (`outcome:success` + `goal_met:false`). A `delegation_*` fact with **zero carriers on any branch = NON-COMPLIANT** (the token-seam class — "reuses a name ≠ has a carrier", verify the substitute). Quote the trace, never audit from memory. Save the report to `docs/reviews/governance_audit_<wf8>_<date>.md`. |
| [`llm-eval-grounded-theory`](../skills/llm-eval-grounded-theory/SKILL.md) | Qualitative coding of the hard decline rows | Stage D (optional) | **Trace is ground truth; narration is a suspect claim** (cardinal rule 1) — code what the `Send` carriers + join actually did, not the supervisor's `reason` text. **Human first pass, no LLM** (AP-10 / rule 2). First-failure discipline. *(Scope: open-coding only — the precision gate stays plain calibration, not the full enable-policy machinery.)* |

> **Two not-required-here (named so the boundary is explicit):** the full `llm-eval-grounded-theory` Stage 5/6
> gold-set + judge-calibration machinery is **out of scope** — T3 validates a *mechanism* (the fan-out seam), not
> an LLM judge; the GoalJudge it relies on is already calibrated (v0.9). And `deploy-gcp`'s phased OpenTofu apply
> (`foundations`→`smoke`) is **not** used — the stress revision is a deliberate out-of-band bypass (mutates no
> managed infra: zero-traffic, throwaway).

---

## 1. Pre-flight gate (AGENTS.md — do this before any code)

- [ ] **Ask-first sign-off.** AGENTS.md "⚠️ Ask first" L28 = *adding new graph nodes to `react_loop.py`*. T3 adds
      **three** (`supervisor`, `worker`, `join`) **and** rewires the `route → call_llm` edge. Get explicit
      approval on the topology change before Step 5.
- [ ] **Confirm scope boundary.** T3 is single-supervisor map-reduce (FOUR_LAYER L159). No worker↔worker, no IATP,
      no blackboard (L1078 deferred). If a step starts reaching for peer-to-peer, stop — that's out of scope.
- [ ] **Branch.** Work on a feature branch off `main` (do not commit to the current docs branch); Phase 4 is a
      code change, separable from the doc work.

---

## 2. Implementation order (strict — each step is independently testable; tests land before code)

The order is forced by the dependency graph: the **architecture test** binds the component before it exists; the
**component** is pure and testable with zero graph; the **state key** and **async dispatch** are independent leaf
changes; the **nodes** need all three; the **edges** need the nodes; the **analyzer** needs the carriers; the
**live run** needs everything.

```
Step 3  architecture P7 test (RED)  ─┐
Step 4  supervisor_plan.py component │  (pure, no graph) ── unit-testable in isolation
Step 5  state key + async dispatch   │  (two independent leaf edits)
Step 6  the 3 nodes + edge rewire    │  needs 4+5; AGENTS.md sign-off (Step 1)
Step 7  Protocol-D topology sims     │  needs 6
Step 8  analyzer fanout branch       │  needs the carrier shape from 6
Step 9  offline validation (CI)      │  needs 3-8 green
Step 10 live GCP calibration         ┘  needs a stress backend + the corpus (built)
```

### Step 3 — Architecture test FIRST (P7, the binding is the test) · `tests/architecture/test_dependency_rules.py`

Per design §C and AGENTS.md inv. 1/3/6, the layer rule is executable. Write these **before** `supervisor_plan.py`
exists (they go RED on import-not-found, which is the correct first failure):

- [ ] `supervisor_plan.py` imports no `langgraph`, no `orchestration.*`, no `AgentState` (LP-1).
- [ ] `supervisor_plan.py` imports no other `components/*` module (LP-2 / inv. 5 — no V→V).
- [ ] `delegation_dispatcher.py` (after Step 5) still imports no `langgraph`/`orchestration` (LP-1 preserved).
- [ ] Run P7 against the **test tree** too (AP7) — `tests/components/test_supervisor_plan.py` must not import
      `orchestration`.

**Gate:** these fail now (module absent). That RED is the spec. (Reuse the existing AST-import-scan helper in that
file — do not write a new scanner.)

### Step 4 — The component · `components/supervisor_plan.py` (Protocol C, decline-first) · impl §7.1

Pure module. Two functions per [component spec §1](t3_supervisor_plan.component.md):

```python
def plan_delegations(*, task_input: str, plan_artifact: dict,
                     planning_depth: Literal["L0","L1","L2"],
                     generate: Callable[[str], dict] | None = None) -> SupervisorPlan: ...
def validate_independence(plan: SupervisorPlan) -> bool: ...
def detect_sequential_dependence(plan_artifact: dict) -> bool: ...   # component spec §3a
```

Decline-first decision table (component spec §2; **first match wins, default = decline**):

| # | Condition | Decision | reason tag |
|---|---|---|---|
| 1 | `planning_depth == "L0"` OR plan `< 2` steps | decline | `single-step` |
| 2 | `detect_sequential_dependence(plan_artifact)` True | decline | `sequential-dependent` (the GAIA guard) |
| 3 | `generate is None` | decline | `no-generator` |
| 4 | LLM proposed branches but `validate_independence` False | decline | `not-independent` |
| 5 | ≥2 validated independent branches | **fan_out** | `independent-branches` |

**`detect_sequential_dependence`** (§3a) is the precision-bearing gate — reuse T1's sequencing markers INVERTED
(the markers `select_planning_depth` uses to *promote* depth — `and then` / `, then` / back-references — are
exactly "these steps are dependent → decline"), OR'd with the structural shared-write signal (two steps write the
same path). Runs over the **T1 plan steps**, not the raw prompt (component spec §3a "why lexical-on-the-plan").

**Test order (TAP-4 / failure-first — write top-to-bottom):** `tests/components/test_supervisor_plan.py`

1. `L0 → decline` (C1, no LLM)
2. `single-step L1 → decline` (C1, condition-1 boundary)
3. **`dependent multi-step → decline`** — the GAIA-guard headline; the 7 near-miss corpus prompts are the
   fixtures (component spec §3a crosswalk maps each to its tripped signal)
4. `no generator → decline` (C1)
5. `LLM emits depends_on → decline` (C1 + mocked LLM, P6 — `validate_independence` overrides model optimism)
6. **last:** `≥2 independent branches → fan_out` (the one acceptance)
7. `validate_independence` property test (P1): any non-empty `depends_on` in a fanned set ⇒ False; empty ⇒ True
8. `detect_sequential_dependence` matrix (P1/parametrized): each marker class fires; clean plan does not

**Gate:** Step 3 architecture tests now GREEN (module exists, layer-clean); component tests green with mocked LLM;
zero live LLM (AP5). Tag `@pytest.mark.slow` for any C3 rubric, none on the C1 decline tests (they're deterministic).

### Step 5 — Two independent leaf edits (do in either order)

**5a · State key · `orchestration/state.py`** (impl §7.3)
- [ ] Add `worker_results: Annotated[list[dict], operator.add]` next to `reflections`
      ([state.py:134](../../orchestration/state.py) uses `_append_list`; **use `operator.add` here**, not
      `_append_list` — concurrent branch writes need the additive reducer or LangGraph raises
      `INVALID_CONCURRENT_GRAPH_UPDATE`; `_append_list` dedups and would silently drop a same-id branch result).
- [ ] **Failure-first test** (`tests/orchestration/` or `tests/architecture/` per where state tests live): the
      reducer **P1 property test** — N concurrent appends merge, **none lost** (the canary; write the "all N
      present" assertion as the property, not a happy single-append). A-style L1 purity, <10s, zero flake.

**5b · Async dispatch · `services/tools/delegation_dispatcher.py`** (impl §7.4)
- [ ] Add `async def dispatch(self, request: dict) -> dict` that `await self._invoke_worker(validated)` **directly**
      (the body of the current sync `dispatch` minus the `_run_async` thread shim at
      [L75-89](../../services/tools/delegation_dispatcher.py); the eval-capture call becomes a plain `await`).
- [ ] **Keep the sync `dispatch()`** — `task_tool.execute_task_tool` is a non-graph caller and still needs it.
- [ ] **LP-1 check:** still no `langgraph`/`orchestration` import (Step 3 architecture test covers this).
- [ ] Contract test (Protocol B, P6 mocked LLM): `async dispatch` returns the same `{status, output, error,
      child_correlation_id}` shape as sync; an LLM exception **propagates** (re-raise, not swallow — the worker
      node, not the dispatcher, owns the sentinel; see Step 6).

### Step 6 — The three nodes + edge rewiring · `orchestration/react_loop.py` (OBP-3, thin) · impl §7.2

> **AGENTS.md sign-off required (Step 1) before this lands.** Nodes are nested `async def` closures inside
> `build_graph` (mirror `reflect_node` at [L1987](../../orchestration/react_loop.py)); the builder section is
> [L2101-2169](../../orchestration/react_loop.py).

- [ ] **Import `Send`** — extend [L20](../../orchestration/react_loop.py) to
      `from langgraph.graph import END, START, StateGraph` **+** `from langgraph.types import Send`. (This is the
      one new langgraph surface.)
- [ ] **`supervisor_node`** (OBP-3): reads `task_input` / `plan_artifact` / `planning_depth` from state, calls
      `plan_delegations(...)`, runs result through `validate_independence`. On `fan_out` → returns
      `list[Send("worker", {small payload per branch})]` (the `Send` payload is a plain dict mapping onto
      `DelegationDispatchRequest`, **never `AgentState`** — OBP-M1). On `decline` → returns a no-op delta; the
      conditional edge routes to `call_llm`. **Holds NO decompose logic** (it's all in the component). ≤15 lines.
- [ ] **`worker_node`** (OBP-3 + OBP-M1): builds a `DelegationDispatchRequest` from the `Send` payload,
      `await dispatcher.dispatch(...)`. **MANDATORY `try/except`→sentinel + per-branch timeout** (`asyncio.wait_for`):
      *one uncaught raise cancels the entire superstep* (the dispatcher re-raises at
      [L87-88](../../services/tools/delegation_dispatcher.py)). On success → append the result to `worker_results`;
      on exception/timeout → append a **sentinel** `{branch_id, status:"failed", error:..., output:""}` to
      `worker_results` (the survivors must not be erased). Carries the **env-gated fault hook**
      (`FANOUT_FAULT_INJECT=1` + magic objective token `__FAULT_TIMEOUT__`/`__FAULT_SLOW__`, off in prod — corpus
      §4.3a) for the timing-fault rows.
- [ ] **`join_node`** (OBP-3 + GTP-3): reads merged `worker_results`, synthesizes one answer (a small LLM call or
      deterministic concat per design — keep it thin; the synthesis prompt is a `.j2`, H1/AP3). **Edges to the
      existing `evaluate`** so GoalJudge scores the **joined** answer, never a fragment (corrupt-success guard).
- [ ] **Per-branch carriers (GTP-1):** ensure each worker dispatch emits `delegation_requested` /
      `delegation_completed` (or `delegation_denied` on budget) **with the branch `correlation_id`** — reuse the
      existing `task_tool` emission helpers (`_build_trace_event`); do **not** invent new event names. The
      supervisor emits one decision carrier (fan_out|decline + reason tag, joinable by `decision_id`).

**Edge rewiring** (the invasive part — [L2135, L2156-2169](../../orchestration/react_loop.py)):
- [ ] Replace the hard `builder.add_edge("route", "call_llm")` (L2135) with
      `add_conditional_edges("route", _route_to_supervisor, {"supervisor": "supervisor", "direct": "call_llm"})`.
      `_route_to_supervisor` is a **pure routing fn** (OBP-4): returns `"supervisor"` only when the planning_depth
      ≥ L1 AND plan has ≥2 steps (the cheap pre-filter; the *real* decline happens in the component). Else `"direct"`
      — **byte-identical behavior to today** for every non-fan-out task.
- [ ] `add_conditional_edges("supervisor", _route_fanout, {"fan_out": "worker", "decline": "call_llm"})`.
- [ ] `builder.add_edge("worker", "join")`; `builder.add_edge("join", "evaluate")`.
- [ ] **Leave the `evaluate → {continue|reflect|done}` fork (L2157-2165) UNCHANGED** — a failed joined answer
      re-enters reflexion (T2) exactly like any terminal turn; `supervisor` re-runs on re-entry and can decline the
      2nd attempt. One budget ceiling (`max_reflexion_attempts`) — no new knob.
- [ ] **Feature-flag the whole fork** behind a `T3_FANOUT_ENABLED` env/config gate (default OFF), so the topology
      change is a no-op in prod until promoted (mirrors the Step-0 flags / shadow→consume discipline). When OFF,
      `_route_to_supervisor` always returns `"direct"` → today's graph exactly.

### Step 7 — Protocol-D topology simulations · `tests/orchestration/test_tier_topology_sim.py` (extend, P11)

The failure-mode matrix is the **headline** (AP6 — these are the tests that prove the fan-out is safe). Failure
rows before the happy row:

- [ ] **decline → identical-to-today** — a non-fan-out task produces the exact same node sequence as the pre-T3
      graph (guards the invasive edge rewrite; this is the regression canary for Step 6's edge change).
- [ ] **one worker raises → join survives** (survivors synthesized, sentinel recorded).
- [ ] **one worker times out → no superstep hang** (`asyncio.wait_for` fires; other branches complete).
- [ ] **all workers fail → degraded answer + judge still runs** (GTP-3 — `evaluate` sees a non-empty joined answer,
      corrupt-success guard holds).
- [ ] **fan_out → join → fail → reflect re-entry → supervisor declines 2nd attempt** (the T2∘T3 composition test —
      proves the budget ceiling bounds the combined loop).
- [ ] **last:** happy `fan_out → all succeed → join → evaluate done`.

Tag `@pytest.mark.simulation` (L4, on-demand, never CI). Mock the dispatcher (P6) — no live LLM.

### Step 8 — Analyzer fanout branch · `scripts/analyze_planning_traces.py` (REQUIRED, not optional) · impl §7.6

Without this the corpus is **unscoreable** (a fanout row falls through `score_run`'s `if/elif` and silently reports
`rate=0.0`). Mirror the **escalation** confusion-matrix pattern, which is the closest analog:

- [ ] Add `elif phase == "fanout":` to the dispatch chain at
      [analyze_planning_traces.py:256-327](../../scripts/analyze_planning_traces.py) (`score_run` at L237), **after**
      the `escalation` branch (L295-327).
- [ ] Decision read: `got_fanout = ` did the supervisor emit ≥2 `delegation_requested` carriers (i.e. ≥2 `Send`)?
      `want = row["want_fanout"]`. Build the confusion matrix exactly like escalation
      ([L314-327](../../scripts/analyze_planning_traces.py)): tp/fp/tn/fn, with the **`fp` cell = the GAIA-failure
      detector** (a near-miss ⚠ decline row that got fanned out anyway).
- [ ] **partial-survival:** for `FANOUT-fault` rows (`want_survives_partial`), check the joined answer is non-empty
      AND a sentinel was observed AND no hang → contributes to a `partial_survival_rate`.
- [ ] Add `summary["fanout_confusion"]` (precision/recall) next to `escalation_confusion`
      ([L343-348](../../scripts/analyze_planning_traces.py)); report `partial_survival_rate` in the phase summary.
- [ ] **Analyzer unit test** (`tests/scripts/test_analyze_planning_traces.py`, extend; **failure-first**): a
      synthetic fanout run where a fanned-out decline row scores `fp` (assert the GAIA-failure cell **first**),
      then a survived fault row counts toward partial-survival, then a correct fan-out scores `tp`.

**Gate:** `pytest tests/scripts/` green; running the analyzer over the built corpus with **no live trace** no
longer silently zeros — it reports the empty-trace path honestly (`missing_trace`, not a fake `rate=0.0`).

---

## 3. Validation plan (four stages — A offline/CI, B live e2e, C governance audit, D open-coding)

The acceptance bar is **plan §3.5a**: seam + layer-clean + observable + MAST-bounded — **NOT throughput/goal-met**.
Validation is split: everything deterministic runs in CI (Stage A); the live run (B), the trace audit (C), and the
qualitative pass (D) are **on-demand only** (a T3 full-stack cut hits the live model — never per-commit, AP5).
**Each of B/C/D is owned by a workspace skill (§0.5) — invoke it, don't paraphrase it.**

### Stage A — Offline (CI / local, every commit; deterministic)

| Check | How | Pass condition | Maps to |
|---|---|---|---|
| Layer-clean seam | Step 3 P7 tests | `supervisor_plan`/worker import no `langgraph`/`orch`/`AgentState`; no V→V | §3.5a (a); AGENTS inv. 1/3/5/6 |
| Decline-first component | Step 4 C1 tests | all 5 decline conditions reject; the 7 near-miss prompts decline; 1 fan_out accepts | component spec §5; TAP-4 |
| Reducer integrity | Step 5a P1 property | N concurrent appends, none lost | impl §7.5; P1 |
| Failure-mode matrix | Step 7 P11 sims | raise/timeout/all-fail/decline-identical/T2∘T3 all green | §3.5a (c); P11 |
| Analyzer correctness | Step 8 unit test | `fp` (GAIA-failure) cell scores; partial-survival counts | impl §7.6 |
| **Failure:success ratio** | count tests | failure tests ≥ success tests at every gate | AP6 (>2:1 success is a defect) |

**Stage A gate:** `pytest tests/ -q` + `pytest tests/architecture/ -q` green; the decline/failure tests
**outnumber** the acceptance tests at every decision point. No live LLM anywhere (AP5).

### Stage B — Live e2e calibration (on-demand; probabilistic) · skills: `deploy-gcp` + `playwright-agentic-e2e`

> **Cut point: T3 full-stack** (playwright skill table) — nothing mocked, the live model runs. On-demand /
> release-gate only, never per-commit (it costs money + a live model is inherently a bit flaky).
> **Prereq:** Steps 6 + 8 built (nodes emit carriers, analyzer can score). Corpus (29 rows) already built.

**B1 · Stand up the stress backend + frontend (deploy-gcp skill "Tiered-Loops Stress Revision").** A loops-on run
needs **TWO** zero-traffic revisions — the Playwright spec hits the *frontend*, which reaches the backend via
`MIDDLEWARE_URL`. The OpenTofu/policy workflow is **intentionally bypassed** (mutates no managed infra). The new
T3 flags fold into the backend `--update-env-vars`:

```bash
# 1. Backend stress tag — reuse the live image digest; loops-on + T3-on + fault-inject (off in prod).
IMG=$(gcloud run revisions describe \
  "$(gcloud run services describe agent-backend-combined --region us-central1 \
     --format='value(status.latestReadyRevisionName)')" \
  --region us-central1 --format='value(spec.containers[0].image)')
gcloud run services update agent-backend-combined --region us-central1 \
  --image "$IMG" --tag stress --no-traffic \
  --update-env-vars REFLEXION_ENABLED=1,PLANNING_PLAN_SOURCE=generated,MAX_REFLEXION_ATTEMPTS=2,T3_FANOUT_ENABLED=1,FANOUT_FAULT_INJECT=1

# 2. Frontend stress tag — MIDDLEWARE_URL points at the backend stress tag URL.
FE_IMG=$(gcloud run revisions describe \
  "$(gcloud run services describe agent-frontend --region us-central1 \
     --format='value(status.latestReadyRevisionName)')" \
  --region us-central1 --format='value(spec.containers[0].image)')
gcloud run services update agent-frontend --region us-central1 \
  --image "$FE_IMG" --tag stress --no-traffic \
  --update-env-vars MIDDLEWARE_URL=https://stress---agent-backend-combined-<hash>-uc.a.run.app

# 3. Auto-fill the tagged frontend URL into the stress profile (reads the real hash off the traffic map).
python scripts/fill_stress_profile_url.py
```

**B2 · Smoke first** (Langfuse quota has 429'd — [[goaljudge-gcp-playwright-gotchas]]; a 4-row smoke protects the
batch): `TEST_PROFILE=stress STRESS_PHASE=fanout STRESS_SMOKE=1 pnpm test:e2e:stress` — one row/family,
chromium-only. **Confirm the fan-out carriers (`delegation_requested` per branch + `join`) actually emit on a live
trace before the full batch.**

**B3 · Full batch:** `TEST_PROFILE=stress STRESS_PHASE=fanout pnpm test:e2e:stress`. (The spec is chromium-only +
600s, verified; `filterCases` filters dynamically on `phase`, so `STRESS_PHASE=fanout` works even though the
spec's doc-comment phase list isn't updated — update that comment as a tidy-up.) **Playwright-skill non-negotiables
apply:** assert **structure + provenance, not exact LLM prose**; **settle-poll** the rendered text (`waitForResponse`),
never `finished()`; scope the message selector to `article div[aria-live="polite"]`, not the Next.js route announcer.

**B4 · Server-side verification** (playwright skill step 5 — a green DOM assertion only proves the *frontend*
rendered). Cross-check the backend did the fan-out: `scripts/verify_run.py` (or Cloud Logging
`thread=<thread_id>`, bridge line in `jsonPayload.message`) — confirm N `delegation_requested` events landed for a
fan-out row, and **zero** for a decline row. This is the seam-observability check that the DOM can't show.

**B5 · Analyze + gate:** `analyze_planning_traces.py --source langfuse --calibration` (Cloud Run tmpfs is
ephemeral → read from Langfuse). Read fan-out precision + partial-survival + the §6 coverage matrix. Calibrate
toward **precision ≥ 0.9** (the `fp` cell is the headline) and **partial-survival = 1.0**; recall reported, **not
gated** (a missed fan-out is the cheap error — it runs sequentially). Re-run `--gate` once bars are locked.

**B6 · Teardown (mandatory — these are live tags).** Remove BOTH stress tags after the run:
```bash
gcloud run services update-traffic agent-backend-combined --region us-central1 --remove-tags stress
gcloud run services update-traffic agent-frontend          --region us-central1 --remove-tags stress
```

### Stage C — Governance trace audit (on-demand; the one CI cannot do) · skill: `governance-trace-audit`

Run a from-step-0 fan-out trace through the [`governance-trace-audit`](../skills/governance-trace-audit/SKILL.md)
skill's **4-step workflow** (do not improvise — the skill encodes incidents CI was green during):

- [ ] **Step 0 — shape.** From-step-0 (has `task.started`) or resumed? Identity is UNVERIFIABLE on a resumed run,
      not FAIL. Build the per-step observation count.
- [ ] **Step 1 — corrupt-success FIRST** (the headline, before anything else). On a fan-out row: `outcome:"success"`
      with `goal_met:false` on the **joined** answer = corrupt success. Governance-caught (judge flagged it) =
      run-level finding; governance-missed (no `eval.goal_judge` on the joined answer, or judge contradicts the
      digest) = NON-COMPLIANT on Reasoning.
- [ ] **Step 2 — pillars.** Recording: `step.executed` present with tokens per branch. **The T3-specific check:
      every `delegation_*` carrier actually exports PER BRANCH with the branch `correlation_id`** — a `delegation_*`
      fact with **zero carriers on any branch = NON-COMPLIANT** (the token-seam / zero-carrier class; "reuses a
      name ≠ has a carrier" — verify the substitute, don't assume). Validation: a budget **deny** surfaces as
      `delegation_denied` / `error.occurred`, never a silent drop; a worker sentinel must leave an `error.occurred`,
      not vanish. Reasoning: the supervisor's fan_out|decline decision carrier has a `rationale` + `decision_id`.
- [ ] **Step 3 — mechanics.** Honest time (near-zero relay durations on the concurrent branches are CORRECT, not a
      defect — the workers run in one superstep); real nulls; join keys present.
- [ ] **Step 4 — verdict + report.** Verdict scale: COMPLIANT / COMPLIANT-WITH-FINDINGS / NON-COMPLIANT. **Save to
      `docs/reviews/governance_audit_<workflow_id8>_<YYYY-MM-DD>.md`**; reply with verdict + one-liner + scorecard
      (reply strictly shorter than the file).
- [ ] **GTP-5: one contradictory trace blocks promotion — green CI is not sufficient.** Quote the trace; every
      scorecard cell needs verbatim evidence or it's UNVERIFIABLE.

### Stage D — Qualitative open-coding (optional, after a batch) · skill: `llm-eval-grounded-theory` (Stage 1 only)

> **Scope (decided):** invoke `llm-eval-grounded-theory` for **open-coding only** — *why* did the supervisor
> (mis)decide on the hard rows. The full Stage 5/6 gold-set + judge-calibration machinery is **NOT** in scope:
> T3 validates a mechanism, not a judge (the GoalJudge is already calibrated). The precision gate (Stage B5) stays
> plain calibration, not the skill's enable-policy.

Hand-code the near-miss ⚠ declines with the operational coder
([`agentsframework-open-coding`](../skills/agentsframework-open-coding/SKILL.md)), under the grounded-theory
**cardinal rules**:

- [ ] **Trace is ground truth; narration is a suspect claim** (rule 1) — code what the `Send` carriers + join
      *actually did* (from the trace / `verify_run.py` output), **not** the supervisor's `reason` text.
- [ ] **Human first pass, no LLM** (rule 2 / AP-10) — the first coding pass is human; an LLM may *assist* codebook
      generation after (R21), never lead it.
- [ ] **First-failure discipline** (R2) — code the *first* deviation as primary (e.g. fanned-out-a-dependent-chain,
      not the downstream join symptom).
- [ ] Tags: `near-miss-fanned-out` (a GAIA failure — the `fp` cell made concrete), `decline-correct`,
      `branch-objective-vague`, `join-dropped-survivor`. Export to a Langfuse dataset (`fanout-open-coding`).
- [ ] **Roll-up:** the codes feed back into whether condition-2's `detect_sequential_dependence` signal needs
      sharpening (corpus-plan §9) — a re-open-code loop (Stage 7 → Stage 1), not a judge re-calibration.

---

## 4. Definition of Done (the §3.5a bar, as a checklist)

T3 is **done** when **all** hold — and not before:

- [ ] **Seam exists & layer-clean** (Stage A P7) — `supervisor_plan`/worker import no framework; no V→V.
- [ ] **Observable** (Stage C, `governance-trace-audit`) — per-branch `delegation_*` carriers export on a live
      trace; the saved `docs/reviews/governance_audit_*.md` verdict is COMPLIANT (or COMPLIANT-WITH-FINDINGS).
- [ ] **MAST-bounded** (Stage A Step 7 + Stage B fault rows) — one branch failing never erases survivors, never
      hangs, never corrupts the join; the judge always runs on a non-empty joined answer.
- [ ] **Decline is correct** (Stage B precision ≥ 0.9) — the near-miss ⚠ rows decline; the `fp` cell is small.
- [ ] **Composes under T2** (Step 7) — a failed join re-enters reflexion and the budget ceiling bounds it.
- [ ] **No prod impact** — `T3_FANOUT_ENABLED` default OFF; the decline path is byte-identical to today's graph.
- [ ] **NOT claimed:** any throughput / latency / goal-met-rate win. The honest metric is the bar above (§3.5a).

---

## 5. Risks & guards (T3-specific, beyond the plan §9 list)

| Risk | Why it bites | Guard |
|---|---|---|
| The `route→call_llm` edge rewrite regresses the spine | it's the one non-additive edit | Step 7 "decline → identical-to-today" topology test; `T3_FANOUT_ENABLED` OFF by default |
| `_append_list` used instead of `operator.add` for `worker_results` | dedup silently drops a same-id branch | Step 5a P1 "none lost" property; explicit note in §2 Step 5a |
| Worker sentinel omitted / re-raises | one branch cancels the whole superstep (dispatcher re-raises @ L87-88) | mandatory `try/except` is in the OBP-M1 obligation (design §B.5); Step 7 raise+timeout sims |
| Carrier reuses a name but doesn't export per branch | the GTP zero-carrier / token-seam class | Stage C GTP-1 per-branch verification; "reuses a name ≠ has a carrier" |
| Over-investing in T3 (waves, nested supervisors) | §2.3 says ~0 parallel workload; GAIA says single-agent wins | the §3.5a bar forbids feature growth without new parallel-workload evidence; DoD §4 "NOT claimed" |
| Fault-injection hook leaks to prod | `FANOUT_FAULT_INJECT` left on | flag set **only** on the `--tag stress` revision; default OFF; assert off-in-prod in a config test |
| Stress tags left live after a run | a zero-traffic tag still consumes a revision slot + can be hit by URL | **Stage B6 teardown is mandatory** — `--remove-tags stress` on BOTH `agent-backend-combined` and `agent-frontend` (deploy-gcp skill) |

---

## 6. Traceability — every step maps to an authority

| Step | impl §7 | design | plan | component | research/AGENTS | skill (§0.5) |
|---|---|---|---|---|---|---|
| 3 architecture test | §7.5 | §A.4 P7, §B.5 | — | — | AGENTS inv.1/3/5/6; P7 | — |
| 4 component | §7.1 | §A.2 OBP-1, §B.5 | §3.5a | §1/§2/§3a/§5 | Protocol C; TAP-4; AP5 | — |
| 5a state key | §7.3 | §A.3 L1-purity, §B.5 | — | — | P1 | — |
| 5b async dispatch | §7.4 | §B.5 (LP-1) | §3.5a | — | Protocol B; P6 | — |
| 6 nodes + edges | §7.2 | §A.2 OBP-3/M1, §B.5 diagrams | §3.5a | §1 (Delegation map) | AGENTS L28 ask-first, AP-5 | — |
| 7 topology sims | §7.5 | §A.4 P11 | §3.5a | — | Protocol D; P11; AP6 | — |
| 8 analyzer | §7.6 | — | §8.2 | — | impl §7.6 table | — |
| 9 / Stage A offline | §7.7 | §C gates | §8 | §5 | AP5/AP6 | — |
| 10 / Stage B live | §7.8 | §A.5 GTP | §8.2, §3.5a | — | GTP-1/3/5 | **`deploy-gcp`** (revisions) + **`playwright-agentic-e2e`** (T3 cut, verify_run) |
| Stage C audit | — | §A.5 GTP | §3.7 | — | GTP-1/3/5 | **`governance-trace-audit`** (4-step, report saved) |
| Stage D open-coding | — | — | §8.2 | §3a | rule 1/2, AP-10 | **`llm-eval-grounded-theory`** (Stage 1 only) |
