# Adding an eval probe for `plan_builder`

Short version: before you write a single check, you have to confront one fact about this seam — **`components/plan_builder.py` has no model in it.** It is pure deterministic decomposition (regex branch-splitting + depth-capped slicing). The LLM/heuristic decision that *actually* drives the plan lives **upstream** in `components/router.py::select_planning_depth`, and the thing worth scoring is the **whole trajectory** (was this the right plan, and did execution follow it?), not any single call. That changes where the probe goes, what altitude it runs at, and how far up the tiers it should climb. The walkthrough below is built around that reality.

The monitoring spine already exists (`eval_capture`, `eval_telemetry`, `meta/run_eval`, `meta/drift`, the `guardrail_validator` pattern). Your job is to **register this seam into it**, not build infrastructure. Expect **60–80% of your effort on Phases 2–3** (reading traces, building the taxonomy) — not on code.

---

## What I verified in the repo first

| Claim | Evidence |
|---|---|
| `plan_builder` is deterministic — no LLM | `components/plan_builder.py`: `_extract_branches` (regex), `build_plan_artifact` slices `branches[:max_steps]` where `max_steps = {"L0":1,"L1":3,"L2":5}`. No model client anywhere in the file. |
| The real decision is upstream | `components/router.py::select_planning_depth(task_input, task_tool_results_count) -> (depth, reason)` — a heuristic complexity scorer that emits `planning_depth` + a `depth_reason` like `"high-complexity-initial-task"`. |
| Both are wired in one orchestration node | `orchestration/react_loop.py:777-784` calls `select_planning_depth` then `build_plan_artifact`; `planning_depth`/`planning_depth_reason` are carried in state (`:1074-1087`) and into the `STEP_PLANNED` BlackBox event (`:958-992`). |
| A partial deterministic check already exists but isn't captured | `plan_builder.py::validate_plan_mece` → `PlanValidationResult` is called at `react_loop.py:994` but its result is **not** written to `eval_capture` or published as an `eval.*` observation. That's low-hanging fruit for Tier-A. |
| The capture + publish pattern to mirror | The `task_understanding` block at `react_loop.py:898-946`: `eval_capture.record(target="task_understanding", ...)` + `eval_telemetry.publish_task_understanding(...)`. Sink Protocol at `services/eval_telemetry.py:48-78`; Langfuse adapter at `middleware/adapters/observability/langfuse_eval_telemetry_sink.py`. |

So the seam you instrument is best named **`plan` (the planning trajectory)**, scoring the upstream `select_planning_depth` decision plus the resulting `PlanArtifact` and its execution — *not* the string-splitting helper in isolation.

---

## The full path at a glance

```
Phase 0  Is a plan probe even the highest-value seam?   → transition failure matrix over phases.jsonl
Phase 1  Name the real seam + altitude                  → "plan", TRACE altitude (defend it)
Phase 2  Open coding: read ≥100 planning trajectories    → first-failure notes, no pre-categorizing
Phase 3  Axial coding → 5–6 binary categories            → Plan Quality / Plan Adherence taxonomy
Phase 4  Ship the Tier-A probe  ★ MILESTONE              → L1 check in services/ + CI regression row
──────────────────────────────────────────────────────  a planner may well stop here  ─────
Phase 5  Rubric + gold set + IAA       (on-demand)       → only if Tier-A data proves it's worth it
Phase 6  Judge calibration + enable-gate (on-demand)     → TPR/TNR + θ̂, fail-closed
Phase 7  Tier-B probe + self-improving loop (on-demand)  → L2 sampled judge, L3 drift, cadence re-analysis
```

Phases 0–4 are the spine. **Start here, and plan to stop at Phase 4 unless the data forces you onward.** Phases 5–7 are the expensive judge track — earned with Tier-A data, never front-loaded.

---

## Phase 0 — Decide whether `plan` is even the seam to probe next

Don't instrument by vibes — and "the plan drives the whole run, so it's obviously high-harm" is a *hypothesis*, not a counted cell. Plausible harm ≠ the highest-count first-failure cell.

1. Build the **transition failure matrix**: rows = last `WorkflowPhase` that completed cleanly, columns = phase of first failure, cell = count. The highest-count cell is where a probe earns the most. Use graph execution order, not the enum declaration order: `guard_input → route → call_llm → execute_tool → evaluate`.
2. The inputs already exist — `phases.jsonl` (written by `services/governance/phase_logger.py`) plus the first-failure signals `synthesis_validator`, `guardrail_validator`, `goal_judge goal_met=false`. The aggregation fn is a planned `meta/analysis.py` deliverable; until it lands, **aggregate by hand** — a 2-hour pass over even ~72 workflows is directional and worth it.
3. **Re-attribute the sink first.** Failures pile into a terminal `EVALUATION`/`completion` bucket; push each back to its true origin (a bad plan surfaces as a `ROUTING`/planning first-failure) before you read the top cell, or the matrix points everywhere at once.

```bash
ls phases.jsonl 2>/dev/null || find . -name "phases.jsonl" | head
# Build From-State × In-State counts by hand or a throwaway script (reference.md §7).
```

**Done when:** you ran the aggregation (however thin), re-attributed the sink, and can point at the *counted cell* — e.g. "`ROUTING→TOOL_EXECUTION` is the top cell: wrong-depth plans cause the agent to execute the wrong/too-few subtasks" — that justifies the planning seam. If a different cell dominates, probe that seam instead.

---

## Phase 1 — Name the real seam and pin the altitude (write both down)

Two decisions a thoughtful engineer most often skips. Skipping them is what sends a probe to the wrong place.

**1. The real seam.** Don't probe the string-splitter. Name the seam **`plan`** and be explicit that the scored decision is the upstream `select_planning_depth` (`router.py`) plus the `PlanArtifact` it produces. Because there's a heuristic — not a free-text LLM generation — in this seam, the failure modes are **wrong-depth / wrong-decomposition / plan-not-followed**, not hallucination. That also means this seam very likely **stops at Tier-A**: there's no free-form generation for a judge to grade unless adherence turns out to need one.

**2. The altitude — and defend it in one sentence.** This is **TRACE**, not span. *A plan can look perfectly fine in isolation and still be the wrong plan for the trajectory* — and "did execution actually follow the plan?" is invisible from the planning call alone. A span check would silently miss the dominant failure mode. The planner is the textbook case where span is *wrong* (reference.md §3). For this seam a "trace" = the full `phases.jsonl` chain for one task. (Don't confuse the existing `phase_logger` Decision entry that logs *which depth we chose* with eval altitude — that's Reasoning-pillar logging, not trajectory evaluation.)

**3. Wire Recording with a scoring-complete payload.** Every probe scores against the Recording-pillar write. Add an `eval_capture.record(target="plan", ...)` call in `react_loop.py` right after the plan is built (after line ~994, where `validate_plan_mece` already runs, so the captured artifact matches what was actually used). **The payload is not boilerplate — capture what the scorer needs:**

- from the upstream decision: `planning_depth` **and** `planning_depth_reason` (both already in scope at `react_loop.py:777`, and in state at `:1074-1087`);
- the full `task_input` (the source material, so an offline re-score has everything — `eval.*` fields get the 8192-char exemption vs the 200-char BlackBox cap);
- the artifact shape: `ordered_steps` titles/goals, `constraints`, `success_conditions`, `plan_fingerprint`;
- the `validate_plan_mece` result (`PlanValidationResult.is_valid` + `issues`).

The `record(...)` signature you call (`services/eval_capture.py:20`): `target, ai_input, ai_response, config, step, model`. Pass `model=None` here — this seam is heuristic, and being honest about that matters.

**Done when:** the seam is named `plan` with TRACE altitude defended in a sentence, `eval_capture.record(target="plan", ...)` is wired with a scoring-complete payload (depth + reason + task_input + artifact + mece result), and you can see `plan` records landing in telemetry.

---

## Phase 2 — Open coding (read ≥100 planning trajectories)

The phase people skip and the one that matters most. No rubric, no judge — just you reading trajectories and writing what's wrong in your own words.

1. Pull **≥100 traces** for the seam, biased toward real traffic. If volume is genuinely low, synthesize inputs along the seam's natural dimensions — and `tests/fixtures/goaljudge/fresh_test_tasks.py` already has dozens of tasks with a verified `expected_planning_depth`, a reference-grade (not gospel) starting corpus.
2. For each, find the **first** thing that goes wrong. Downstream errors are usually consequences — a fabricated final answer often traces back to a too-shallow plan (`L0` where `L1`/`L2` was right). Write a short free-text note.
3. Use the **Three Gulfs** as the *why* lens: **Comprehension** (misread the task's complexity), **Specification** (the depth heuristic asked for the wrong granularity), **Generalization** (works on seen prompts, breaks on the tail — e.g. the `task_tool_results_count` short-circuit to `L0` on long-lived threads, see the `select_planning_depth` docstring).
4. **Keep it pure — don't pre-write the taxonomy.** If you have a hunch (e.g. "I bet comma-joined imperatives get under-decomposed"), write it as a one-line falsifiable hypothesis in a sidebar and let the traces confirm or kill it. The taxonomy is an *output* of Phase 3.
5. **Stop rule:** keep going until **~20 consecutive traces with no new category** (saturation).

**Sanity band:** ~100% passing ⇒ your sample is too easy; a seam worth probing sits around **~70% pass** under genuine stress.

**Done when:** ~100+ trajectories read, every failure has a first-failure note, ~20 in a row with nothing new.

---

## Phase 3 — Axial coding → a testable taxonomy

1. Let an LLM **propose clusters** over your notes, then **you rename and merge** — the human owns the final names. Aim for **5–6 categories**, each **binary** (present/absent, never a 1–5 Likert), distinguishable, and testable from the trace alone.
2. For a planner the two anchor families (reference.md §2) are **Plan Quality** (plan is complete + realistic for the task) and **Plan Adherence** (execution actually matched the plan). Specialize into binary sub-categories your traces support, e.g.: *depth-too-shallow*, *depth-too-deep*, *missing-subtask* (a branch in `task_input` never made it into `ordered_steps`), *non-MECE/overlapping-steps*, *plan-not-followed* (executed steps diverge from the plan). **Avoid generic "plan quality"/"helpfulness" with no seam-specific definition — per the canon they're worse than useless because they manufacture false confidence.**
3. Re-label your traces against the structured taxonomy (some notes will move — healthy criteria drift). Write the taxonomy down as the seam's source of truth (`meta/judge.py::load_taxonomy()` + `meta/judge_prompt.j2` expect one *if* you ever reach the judge track).

**Done when:** 5–6 binary, evidence-grounded categories exist and traces are re-labeled against them.

---

## Phase 4 — Ship the Tier-A probe ★ (the milestone — most planners stop here)

The cheapest thing that catches the failures you found: a **deterministic L1 check on 100% of traffic** + **one offline CI regression row**.

**4a. The L1 check.** A pure function `trace → per-category pass/fail`, modeled on `services/governance/guardrail_validator.py` (`ValidationResult` shape). Pick the **deterministically detectable** subset of your taxonomy — for a planner that's a lot, because the seam is heuristic:

- `planning_depth ∈ {L0, L1, L2}` and consistent with `planning_depth_reason`;
- plan non-empty; `ordered_steps` count within the depth cap (`L0≤1`, `L1≤3`, `L2≤5`);
- MECE structure (you can lift `validate_plan_mece`'s logic — contiguous `step_id`s, no overlapping goals, non-empty goals, ≥1 success condition);
- **subtask coverage**: every branch `_extract_branches` finds is represented (the *depth-too-shallow* / *missing-subtask* signal — the one that drives fabricated downstream answers).

Emit **per-category binary results, not a single 0–1 score** — a scalar tells you something regressed but not *what*, and drift on a named category is the signal you actually act on. Anything genuinely subjective (was this the *right* plan for an ambiguous task?) waits for a Tier-B judge.

**Layer discipline (reference.md §4 — this trips the dependency-leak audit if you get it wrong):**

- The L1 check lives in **`services/`** — stdlib + pydantic, **no `components` / `langgraph` / `langchain` imports**. Verify:
  ```bash
  grep -nE "from components|import langgraph|import langchain" services/governance/<your_new_check>.py
  # must print NOTHING
  ```
- A judge, *if you ever build one*, is L3 in `components/`. Live replay goes in `scripts/`/`meta/`, **never CI**.

**Wire it and publish it (a pure check nothing calls is dead code):**

1. Invoke the check in `react_loop.py` right after the plan is built (after `validate_plan_mece` at ~`:994`, so the captured artifact matches what was processed), and embed the `ValidationResult`s in the `ai_response` you record via `eval_capture.record(target="plan", ...)`.
2. **Publish to the Langfuse sink too** — `eval_capture.record` alone is necessary but not sufficient. Mirror the `task_understanding` path exactly:
   - add `publish_plan(...)` to `services/eval_telemetry.py` alongside `publish_task_understanding` (`:138`) — it **must never raise** (contract O1; the existing one swallows exceptions);
   - add a `publish_plan` method to the sink Protocol (`eval_telemetry.py:48-78`) and to the Langfuse adapter (`middleware/adapters/observability/langfuse_eval_telemetry_sink.py`, mirroring `publish_task_understanding` at `:72`);
   - call `await eval_telemetry.publish_plan(...)` right after the `record` call, like `react_loop.py:938-946`.
   This makes the `eval.plan` observation appear on the trace so `governance-trace-audit` can see it.

**4b. The offline CI regression row.** Freeze your Phase-2 failures as a benchmark JSONL (the `gate_benchmark_v1.json` pattern — must-accept / must-reject planning cases; `fresh_test_tasks.py` with its verified `expected_planning_depth` is a ready seed), then score it deterministically:

```bash
python -m meta.run_eval \
  --golden-set tests/.../plan_benchmark_v1.json \
  --output /tmp/plan_report.json \
  --report-id plan-tierA
# prints: "Eval complete: scored=… failed=… mean=…"
```

Add a replay test asserting it stays green (model it on the existing eval-pipeline regression sweep):

```bash
.venv/bin/python -m pytest tests/services/ tests/components/test_plan_builder.py -q
```

**Done when:**
- [ ] L1 check is a pure function in `services/`, no framework imports, returns **per-category** results
- [ ] Invoked in `react_loop.py` on 100% of planning turns; results recorded via `eval_capture.record(target="plan")` **and** published through `publish_plan` so the `eval.plan` observation lands on the trace
- [ ] A frozen `plan_benchmark_v1.json` (must-accept / must-reject) holds the Phase-2 failures
- [ ] `python -m meta.run_eval` scores it green in CI, with a replay test asserting it
- [ ] You did **not** build a judge yet

> "100% of traffic" here = 100% of *planning turns*. Note `select_planning_depth` returns `L0, "post-tool-synthesis"` on post-tool turns (`router.py`), so most of the interesting decomposition happens on the **initial** turn of a task — say that explicitly so you don't overstate monitoring breadth.

**A planner can legitimately stop here.** This seam is heuristic; a deterministic check covers most of its real failure modes. Reach for the judge track only if Tier-A shadow data shows a *persistent, subjective* failure (e.g. "the plan was structurally valid but strategically wrong") that no deterministic rule catches.

---

## Phases 5–7 — The judge track + self-improving loop (on-demand only)

You graduate **only** when Tier-A data proves a persistent failure worth a gating judge. For this seam that's the *adherence/right-plan judgment* a deterministic rule can't make. Formulas live in reference.md §5–6; the worked GoalJudge path is in examples.md.

- **Phase 5 — rubric + gold set + IAA.** Promote the taxonomy to a binary judge rubric (`meta/judge.py` `load_taxonomy` / `meta/judge_prompt.j2`). Build a **≥100-example** labeled gold set, **split dev/test**, tune on **dev only**, then **freeze + hash** the test split (κ ≥ 0.6 is a measurement *prerequisite*, not the headline; IAA via `services/governance/iaa.py`).
- **Phase 6 — calibration + enable-gate.** Generalize the §2.8 evaluator (`services/governance/goaljudge_calibration.py`: `confusion_counts` → `precision_recall_fd` → `evaluate_section_2_8_gates` → `GateDecision`). **Headline = TPR/TNR on the frozen test split** (TPR = recall; TNR = 1 − false-downgrade-rate; positive class = "judge says *bad plan*", so a false positive is a *false downgrade* of a good plan). Report the bias-corrected production rate `θ̂ = (p_obs + TNR − 1)/(TPR + TNR − 1)` with a bootstrap 95% CI. §2.8 thresholds: precision ≥ 0.90, recall ≥ 0.70, false-downgrade ≤ 0.02, flip ≤ 0.05, κ ≥ 0.6. The gate is **fail-closed** — a seam that doesn't clear stays shadow/L1-only (the GoalJudge gold set is v0.9 provisional today, so its evaluator *cannot* emit ENABLE by design; mirror that floor gate).
- **Phase 7 — Tier-B probe + the loop.** Register an **L2 sampled judge** (5–10%, `meta/judge.py`) and **L3 drift** (`meta/drift.py`):
  ```bash
  python -m meta.drift --baseline baseline_scores.jsonl --production prod_scores.jsonl \
    --level all --output /tmp/plan_drift.json   # exit 0=no drift, 1=drift, 2=error
  ```
  **The loop trigger is cadence-first:** re-run open coding on **100+ fresh traces every 2–4 weeks**, plus a **change-event hook** (any edit to `select_planning_depth`'s heuristics, the `_extract_branches` regexes, or the depth caps → re-run the offline probe immediately — these are exactly the kind of change that silently shifts the depth distribution). EWMA/CUSUM only *surface candidates between cycles*; a human re-analysis cycle is the authority, and you threshold on **θ̂ + CI**, never a raw judge count. A new failure mode → back to **Phase 2**; a confirmed regression → a new offline CI row (gold-set promotion is human-gated).

The terminal *acting* decision (e.g. flipping a runtime flag) is a **runtime-config write a human owns** — this skill produces the decision and stops.

---

## Numbers to keep in view

≥100 traces to start · ~20-no-new saturation · ≥100 labeled to validate a judge · 100+ fresh traces every 2–4 weeks · 10–20 weekly spot-checks · ~70% pass = stress-testing (100% = too easy) · 60–80% of effort on analysis · κ ≥ 0.6 prerequisite.

## The one rule that governs everything

**Write evaluators for failures you have observed, never for failures you imagine.** Open coding (Phase 2) strictly precedes the rubric (Phase 3). If you catch yourself writing a plan check before you've read planning trajectories, stop — you're building the wrong thing.

## Where to start, concretely

1. Read `components/plan_builder.py` and `components/router.py::select_planning_depth` so the deterministic-seam reality is in your head.
2. Hand-aggregate the transition failure matrix from `phases.jsonl` (Phase 0) to confirm the planning seam is actually your top cell.
3. Wire `eval_capture.record(target="plan", ...)` in `orchestration/react_loop.py` (after ~`:994`) capturing depth + reason + task_input + artifact + mece result (Phase 1).
4. Open-code ≥100 planning trajectories, seeding from `tests/fixtures/goaljudge/fresh_test_tasks.py` if real volume is thin (Phase 2).
5. Build the 5–6 binary Plan-Quality/Plan-Adherence categories (Phase 3), then ship the L1 check in `services/` + `publish_plan` sink + `plan_benchmark_v1.json` scored by `python -m meta.run_eval` (Phase 4). Then stop, unless the data earns the judge track.
