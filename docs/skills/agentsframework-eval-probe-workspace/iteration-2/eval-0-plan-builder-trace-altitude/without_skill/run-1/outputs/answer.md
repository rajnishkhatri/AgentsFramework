# Adding an eval probe for `components/plan_builder.py`

Here's the full, concrete path — from "no monitoring" to a shipped probe — grounded in the infrastructure this repo already has. The canonical process is the repo handbook at `docs/handbooks/add_an_eval_probe.md`; everything below specializes it to the plan-builder seam.

## The one thing to internalize first

`components/plan_builder.py` is **deterministic**, not an LLM call. `build_plan_artifact` / `_extract_branches` split the task into ordered branches by regex and cap step count by depth (`L0=1, L1=3, L2=5`); `validate_plan_mece` already checks structure. It is invoked from the ReAct loop at:

- `orchestration/react_loop.py:781` — `build_plan_artifact(planning_depth, task_input=...)`
- `orchestration/react_loop.py:994` — `validate_plan_mece(plan_artifact)`

This drives two decisions that shape the whole probe:

1. **Altitude is trace-level, not span-level.** There is no isolated LLM call to score. Whether a plan was *good* only becomes visible across the trajectory — did the steps it produced actually let the agent satisfy the request? The handbook's altitude table explicitly names `plan_builder` as a trace-altitude seam. So a "trace" for this probe = one whole run, and you judge the plan against the run's outcome, not against the plan in a vacuum.
2. **Most of the work is error analysis, not code.** Expect 60–80% of effort in Phases 2–3 (reading traces, building the taxonomy). The L1 check itself is small and largely reuses `validate_plan_mece`.

The governing rule: **write evaluators for failures you have observed, never for failures you imagine.** Open coding (Phase 2) strictly precedes any rubric.

---

## Phase 0 — Confirm the seam is worth a probe

Don't instrument by vibes. Build a **transition-failure matrix** from the phase log (`phases.jsonl`, written by `services/governance/phase_logger.py`): rows = last clean state, columns = state of first failure, over the real `WorkflowPhase` order (`INITIALIZATION → INPUT_VALIDATION → ROUTING → MODEL_INVOCATION → TOOL_EXECUTION → OUTPUT_VALIDATION → EVALUATION`).

For plan_builder you're looking for runs that *plan, then fail downstream* — the planning step completes but the run derails in `TOOL_EXECUTION` / `EVALUATION` because the plan was wrong (missing a requested branch, wrong order, over/under-decomposed). First-failure attribution reuses checks that already exist (`synthesis_validator`, `goal_judge goal_met=false`, `validate_plan_mece` issues) — no new instrumentation needed; it's a pure offline aggregation. (The matrix helper `meta/analysis.py` is the planned home; until it lands, aggregate by hand — but still do it.)

**Done when:** you can point at the cell that justifies probing the planning seam over the others.

---

## Phase 1 — Pin the altitude and verify Recording works

Altitude = **trace**. The blocking prerequisite: the plan-builder seam **does not currently call `eval_capture.record`** — so there's nothing to score yet. You must add that capture first.

`services/eval_capture.py` `record(...)` is `async`, keys on `target=`, and lifts `task_id`/`user_id` from `config["configurable"]`; it flows into `services/eval_telemetry.py` under the same `trace_id` (the `eval.*` fields get the 8192-char exemption vs the 200-char BlackBox cap). Add a capture right after the plan is built in `react_loop.py` (~line 784, next to the existing `STEP_PLANNED` black-box record):

```python
from services import eval_capture
await eval_capture.record(
    target="plan_builder",                 # stable key — becomes the probe's name
    ai_input={"task_input": task_input, "planning_depth": planning_depth},
    ai_response={
        "ordered_steps": [s.model_dump() for s in plan_artifact.ordered_steps],
        "constraints": plan_artifact.constraints,
        "success_conditions": plan_artifact.success_conditions,
        "plan_fingerprint": compute_plan_fingerprint(planning_depth, plan_artifact),
    },
    config=config,
)
```

(`compute_plan_fingerprint` is already imported in `react_loop.py` and gives you stable plan identity for dedup across the trace's re-entrant route iterations.)

**Done when:** seam named (`plan_builder`), altitude chosen (trace), and you can see `target="plan_builder"` records landing in telemetry for a handful of real runs.

---

## Phase 2 — Open coding (the phase that actually matters)

No tooling, no rubric, no judge. Pull **≥ 100 traces** for `target="plan_builder"`, biasing toward real traffic. If volume is thin, synthesize inputs along the seam's natural dimensions — for plan_builder those are: number of explicit subtasks, presence of exclusion constraints (`"without ..."` — the builder special-cases this at line 185), enumeration style (`(1)/1./bullets/prose`), and depth (`L0/L1/L2`).

For each trace, find the **first** thing that goes wrong and write a free-text note. Read the plan against what the run was asked to do. Use the Three Gulfs as the *why* lens:
- **Comprehension** — `_extract_branches` mis-split the request (e.g. split a path or a noun phrase like "trade-offs and risks" into bogus steps, or merged two real subtasks).
- **Specification** — the depth cap dropped a requested branch (4 subtasks at `L1`'s cap of 3), or the success conditions don't cover what the user actually wanted.
- **Generalization** — works on clean enumerated input, breaks on messy prose / mixed delimiters.

**Stop rule:** keep going until ~20 consecutive traces produce no new failure category (saturation). **Sanity band:** if ~100% look fine your sample is too easy — a probe-worthy seam sits near ~70% pass under genuine stress-testing.

**Done when:** ~100+ traces read, every failure has a first-failure note, ~20 in a row with nothing new.

---

## Phase 3 — Axial coding → a testable taxonomy

Let an LLM propose clusters over your notes, then **you** rename/merge to **5–6 binary, mutually-distinguishable, trace-grounded categories**. Likely shape for plan_builder (yours will differ — let the data decide):

- `missing_requested_branch` — a subtask the user explicitly asked for has no step.
- `spurious_step` — a step that doesn't correspond to a real subtask (over-splitting).
- `wrong_order` — ordered_steps violate a dependency the request implies.
- `depth_truncation_lost_work` — a real branch fell outside the depth cap.
- `success_conditions_miss` — conditions don't cover a requested outcome / dropped the exclusion constraint.

Each must be **binary** (present/absent — no 1–5 Likert) and **decidable from the trace alone**. Avoid generic "quality"/"helpfulness" labels — the canon calls those worse than useless. Write the taxonomy down as the seam's source of truth; the offline harness expects a taxonomy file (`meta/judge.py` `load_taxonomy()` + `meta/judge_prompt.j2`).

**Done when:** 5–6 binary categories exist and your traces are re-labeled against them.

---

## Phase 4 — Ship the Tier-A probe ★ (this is the milestone)

Ship the **cheapest thing that catches the failures you found**: a deterministic L1 check on 100% of traffic + one offline CI regression row. Many seams should stop here.

### 4a. L1 deterministic check

A **pure function in `services/`** (L1/L2 horizontal layer — stdlib + pydantic only, **no framework imports**; the judge, if you ever build one, is L3 in `components/`). Model it on `services/governance/guardrail_validator.py` (regex/structural → `ValidationResult` with severity + fail-action).

The good news: `validate_plan_mece` in `plan_builder.py` already computes most of the deterministic surface — contiguous `step_id`s, no-overlap (MECE) goals, non-empty success conditions, non-empty goals. Your L1 check is the trace-aware wrapper around those predicates plus the deterministically-detectable subset of your Phase-3 taxonomy:

| Taxonomy category | Deterministic L1 test |
|---|---|
| structural validity | reuse `validate_plan_mece` (`is_valid`, `issues`) |
| `spurious_step` / over-split | step count vs branch count from `_extract_branches` |
| `depth_truncation_lost_work` | `len(branches) > depth_cap` ⟹ flag |
| `success_conditions_miss` (exclusion) | `"without"` in input but no exclusion condition present |
| plan non-empty / depth-in-range | per handbook's Planning/routing template row |

The categories that need *semantic* judgment (`missing_requested_branch`, `wrong_order`) are **not** L1 — they wait for Tier-B's judge. Pick only the deterministically-detectable subset for L1.

### 4b. Offline CI regression row

Freeze the Phase-2 failures into a curated JSONL benchmark, copying the exact precedent already in the repo:

- Fixture: `tests/fixtures/task_understanding/gate_benchmark_v1.json`
- Test that runs it: `tests/components/test_task_understanding_gate_benchmark.py`
- Builder pattern: `docs/research/goaljudge_tu_gate_longterm_plan/build_gate_benchmark_fixture.py`

Create `tests/fixtures/plan_builder/plan_builder_benchmark_v1.json` — input (`task_input` + `planning_depth`) → expected-verdict rows, with the must-pass cases your L1 now catches. Score it deterministically:

```bash
python -m meta.run_eval \
  --golden-set tests/fixtures/plan_builder/plan_builder_benchmark_v1.json \
  --output /tmp/plan_builder_report.json \
  --report-id plan_builder-tierA
# prints: scored=… failed=… mean=…
```

Then wire a pytest that asserts the L1 check passes every must-pass row (mirror `test_task_understanding_gate_benchmark.py`).

**Done when:**
- [ ] L1 check is a pure function in `services/`, no framework imports
- [ ] It runs on 100% of plan_builder traffic and writes via `eval_capture.record`
- [ ] `tests/fixtures/plan_builder/plan_builder_benchmark_v1.json` is frozen with the Phase-2 failures
- [ ] `python -m meta.run_eval` scores it green in CI
- [ ] You did **not** build a judge

**Stop here unless the Tier-A data proves you'll iterate on this seam repeatedly.** The judge track is on-demand — you earn it with Tier-A data, you don't front-load it.

---

## Phases 5–7 — Judge track + self-improving loop (only if earned)

Reach for these only when accumulated Tier-A data shows persistent failures that the deterministic check can't catch (your `missing_requested_branch` / `wrong_order` categories — semantic, trace-level). Briefly:

- **Phase 5 — Rubric + gold set + IAA.** Promote the taxonomy into a binary, evidence-grounded judge rubric. Build ≥ 100 labeled examples; split dev/test, tune the prompt on **dev only**, then **freeze and hash the test split**. Measure inter-annotator agreement via `services/governance/iaa.py` (**κ ≥ 0.6** is a measurement prerequisite, not the headline).
- **Phase 6 — Calibration + per-component enable-gate.** Generalize `services/governance/goaljudge_calibration.py`. Headline metrics are **TPR and TNR on the frozen test split** (TPR = recall; TNR = 1 − false-downgrade-rate). Report the bias-corrected production success rate `θ̂ = (p_obs + TNR − 1)/(TPR + TNR − 1)` with a bootstrap 95% CI. The gate is **fail-closed** (`GateDecision`) — a seam that doesn't clear stays shadow / L1-only.
- **Phase 7 — Tier-B probe + the loop.** Register an L2 sampled judge (score 5–10% of traffic via `meta/judge.py` `build_judge_prompt` / `parse_judge_response`) and L3 drift over the L1/L2 stream:

```bash
python -m meta.drift --baseline baseline_scores.jsonl --production prod_scores.jsonl \
  --level all --output /tmp/drift_report.json
# exit 0 = no drift, 1 = drift, 2 = error
```

**Loop trigger is cadence-first:** re-run open coding on 100+ fresh traces every 2–4 weeks, plus a change-event hook (any edit to `_extract_branches`/depth caps/`build_plan_artifact` ⟹ re-run the plan_builder offline probe). EWMA/CUSUM are early-warning only; a human re-analysis cycle is the authority. A new failure mode sends you back to Phase 2; a confirmed regression becomes a new offline CI row (the cheap default). Gold-set promotion is human-gated.

---

## Where to start tomorrow

1. Read `docs/handbooks/add_an_eval_probe.md` once end-to-end (it's the source of truth).
2. **Phase 0:** aggregate `phases.jsonl` into a transition-failure matrix; confirm the planning seam earns it.
3. **Phase 1:** add the `eval_capture.record(target="plan_builder", ...)` call at `react_loop.py` ~line 784 and confirm records land in telemetry. **This is the literal first code change.**
4. **Phase 2:** pull 100+ `plan_builder` traces and open-code first-failures. Budget the majority of your time here.

## Key repo files for this seam

- `components/plan_builder.py` — the seam (deterministic; `build_plan_artifact`, `_extract_branches`, `validate_plan_mece`, `compute_plan_fingerprint`)
- `orchestration/react_loop.py:781` / `:994` — where it's invoked; where Phase-1 capture goes
- `services/eval_capture.py` — `record(target=...)` (async; the capture you must add)
- `services/eval_telemetry.py` — Recording sink for `eval.*` fields
- `services/governance/phase_logger.py` + `phases.jsonl` — Phase-0 transition matrix source
- `services/governance/guardrail_validator.py` — L1 deterministic-check precedent to model on
- `tests/fixtures/task_understanding/gate_benchmark_v1.json` + `tests/components/test_task_understanding_gate_benchmark.py` — Phase-4 benchmark + CI-test precedent to copy
- `meta/run_eval.py` — offline CI scorer (`python -m meta.run_eval --golden-set …`)
- `meta/judge.py` / `meta/judge_prompt.j2` — taxonomy + judge (Phases 3, 7, on-demand)
- `services/governance/iaa.py`, `services/governance/goaljudge_calibration.py` — IAA + calibration gate (Phases 5–6, on-demand)
- `meta/drift.py` — drift check (Phase 7, on-demand)
