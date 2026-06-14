# Adding an eval probe for `plan_builder`

Short version: **don't add the probe inside `components/plan_builder.py`.** The probe lives at the orchestration seam where the plan artifact is *produced*, not inside the component that computes it. The closest working template you already have is the **TaskUnderstanding probe** — copy its wiring, not the GoalJudge one. Below is the full path, phased, with exact files.

---

## Step 0 — Get the altitude right (the one decision that changes everything)

Before writing any code, classify what you're monitoring. `plan_builder.py` is special:

- It's **deterministic** — `build_plan_artifact()` (`components/plan_builder.py:171`) is pure string-splitting + slicing. There is **no LLM call** in it, unlike `components/goal_judge.py` (which injects `LLMService`) or `components/task_understanding.py` (fast-tier LLM).
- It's **framework-agnostic** (AGENTS.md invariant #3: `components/` must not import `langgraph`/`langchain`).

Two consequences:

1. **The probe does not belong inside `plan_builder.py`.** Telemetry/capture requires `config`, `trace_id`, sinks — all orchestration concerns. Putting them in the component would violate the layering. The component stays pure; it can grow a *pure validator* (more below), but never an emit call.
2. **What you actually want to monitor is the plan artifact's quality, captured at the moment it's built in the ReAct loop.** That's a record-and-score probe, not an LLM judge — at least to start. Treat `build_plan_artifact` output the way the codebase already treats the deterministic-floor `TaskUnderstanding`: capture it, ship it to Langfuse, score it offline.

The plan is already built at `orchestration/react_loop.py:781` (`plan_artifact = build_plan_artifact(...)`), and the TaskUnderstanding probe fires **right next to it** (lines 786–946). That adjacency is your insertion point — you are adding a sibling probe in the same node.

---

## The full path (5 phases)

### Phase 1 — Define what "good plan" means (the rubric), as a pure function

Add a deterministic quality signal to the component layer. You already have the skeleton: `validate_plan_mece()` (`components/plan_builder.py:235`) checks contiguous step IDs, MECE/non-overlapping goals, non-empty success conditions. Decide your probe's axes, e.g.:

- step count vs `planning_depth` cap (L0=1/L1=3/L2=5, see line 178),
- MECE pass/fail (reuse `validate_plan_mece`),
- coverage: do the extracted branches map onto the success conditions,
- duplicate/empty-goal flags.

Keep this a **pure function in `components/plan_builder.py`** returning a structured result (extend `PlanValidationResult` at line 27, or add a `PlanQualitySignal` model). This is the equivalent of `components/task_understanding.py:validate_conditions` — deterministic gates with no I/O. It's unit-testable at L1 with zero mocks (AGENTS.md TAP-2).

If later you want an *LLM* judge over plan quality (is the decomposition actually sensible?), that's a second component modeled on `components/goal_judge.py` — injected `LLMService` + `.j2` prompt + tolerant JSON parse. Don't start there; start deterministic.

### Phase 2 — Add the capture target (the telemetry seam)

This is the bulk of the wiring, and it's mechanical because two probes already do it.

1. **`services/eval_telemetry.py`** — add a `publish_plan_builder(...)` method to the `EvalTelemetrySink` Protocol (mirror `publish_task_understanding` at line 66) and a module-level `async def publish_plan_builder(...)` (mirror lines 138–173). It must **never raise** (contract O1) and goes through `_redact_mapping`. Note the 8192-char eval exemption (`_DEFAULT_EVAL_MAX_VALUE_LEN`, line 30) already applies via `clip_eval_text` — use it for the artifact payload.

2. **`middleware/adapters/observability/langfuse_eval_telemetry_sink.py`** — add `publish_plan_builder` to `LangfuseEvalTelemetrySink` (mirror `publish_task_understanding` at line 72). The observation name comes for free: `observation_name_for_target("plan_builder")` → `eval.plan_builder` (see `eval_telemetry.py:176`). No change needed to `composition.py` — `_wire_eval_telemetry` (line 134) already registers the sink; you're only adding a method to it.

3. **No `eval_capture` change needed.** `services/eval_capture.py:record(target=...)` is already target-agnostic — you just pass `target="plan_builder"`.

### Phase 3 — Fire the probe in the orchestration node (thin wrapper, AP-5)

In `orchestration/react_loop.py`, right after the plan is built (line 781) and alongside the existing TaskUnderstanding capture block (lines 898–946), add the plan_builder probe. Keep it to ~10–15 lines (AP-5, AGENTS.md:184). Pattern, copied from the TaskUnderstanding block:

```python
from services import eval_capture, eval_telemetry

quality = validate_plan_mece(plan_artifact)        # Phase-1 pure signal
pb_ai_input = {"task_input": eval_telemetry.clip_eval_text(state.get("task_input", ""))}
pb_ai_response = {
    "ordered_steps": [s.model_dump() for s in plan_artifact.ordered_steps],
    "planning_depth": planning_depth,
    "is_valid": quality.is_valid,
    "issues": quality.issues,
    "plan_fingerprint": plan_fingerprint,          # already computed at line 955
}
await eval_capture.record(
    target="plan_builder",
    ai_input=pb_ai_input,
    ai_response=pb_ai_response,
    config=config,
    step=state.get("step_count", 0),
)
await eval_telemetry.publish_plan_builder(
    trace_id=workflow_id or configurable.get("task_id", ""),
    user_id=configurable.get("user_id", "anonymous"),
    task_id=configurable.get("task_id", ""),
    ai_input=pb_ai_input, ai_response=pb_ai_response,
    step=state.get("step_count", 0), model=None,
)
```

Two gotchas you can reuse from the existing code:

- **Memoize per run.** `route_node` re-enters every evaluate→continue→route iteration (see the comment at line 787). The plan already has `compute_plan_fingerprint` (line 955) + `plan_changed` (line 956) for exactly this — only capture when `plan_changed`, or gate on a `state` key like TaskUnderstanding does with `task_understanding_task_id` (line 798). Otherwise you'll emit a duplicate `eval.plan_builder` every loop.
- **Record-only, never gating.** Like the TaskUnderstanding/GoalJudge probes (and the `criteria_met_derived` / `partial_fraction` telemetry-only fields, schemas.py:163), the plan-builder signal must NOT change `outcome`. The deterministic process floor owns gating.

If you want a Reasoning-pillar trace entry too, log a `Decision` via `phase_logger.log_decision` (mirror lines 885–895) so the trace explains the plan's altitude.

### Phase 4 — Stage it behind a runtime flag (don't flip straight to consume)

The GoalJudge/TaskUnderstanding rollout staged through `deterministic → shadow → generated` via `services/goal_judge_runtime_config.py` (`ConditionsSource`, line 42). For a record-only plan probe you likely just need a simple on/off, but the safe path mirrors theirs:

- **shadow first**: capture + publish + log, change nothing else. Run it in prod, read the `eval.plan_builder` observations, confirm the signal is sane before anyone depends on it.
- Add a flag if you want a kill switch — either an env var read in the node, or a field on the runtime config doc (extend `GoalJudgeRuntimeConfig`, line 53) if you want hot-reload without a deploy.

### Phase 5 — Score and watch for drift (close the loop)

1. **Offline scoring.** The `eval.plan_builder` rows are `EvalRecord`-shaped JSONL. Feed them through `meta/run_eval.py` (`run_eval_cli`, line 188; `load_golden_set` reads `EvalRecord` JSONL). If you added an LLM plan-judge in Phase 1, score with `meta/judge.py:score_eval_record`; for the deterministic signal you can aggregate directly.
2. **Drift monitoring.** `meta/drift.py` is the continuous-monitoring spine. `detect_performance_drift` (line 48, 2-sigma vs a baseline) over your plan-quality score per week gives you a Level-1 probe; `run_drift_cli` (line 397) takes `--baseline`/`--production` JSONL and exits non-zero on drift. Wire a baseline from your shadow run, then point production at the live stream.

---

## Verify it end-to-end

1. **L1 unit** — pure Phase-1 validator on hand-built `PlanArtifact`s (good/MECE-violating/empty-goal). No mocks.
2. **Orchestration contract** — assert that running the node with a sink registered produces exactly one `eval.plan_builder` capture per run (memoization holds across loop re-entry), and that `outcome` is unchanged (record-only).
3. **Sink no-raise** — Protocol method swallows exceptions (O1).
4. **Prod trace** — deploy, run a multi-step task, then confirm the `eval.plan_builder` observation is on the same `trace_id` as the run. Use the `governance-trace-audit` skill on the resulting Langfuse trace to check the four pillars still pass.

---

## Where you start, in one line

Add a pure quality signal to `components/plan_builder.py` (Phase 1), then **copy the TaskUnderstanding probe wiring** — `services/eval_telemetry.py` + the Langfuse sink adapter (Phase 2) and the capture block at `orchestration/react_loop.py:~898` (Phase 3) — running in **shadow** first (Phase 4) and scored/drift-watched through `meta/run_eval.py` + `meta/drift.py` (Phase 5). The component stays pure; everything observable happens at the orchestration seam.

### Key files
- `components/plan_builder.py` — pure artifact + validator (`build_plan_artifact:171`, `validate_plan_mece:235`, `PlanValidationResult:27`)
- `components/task_understanding.py` — the probe template to copy (deterministic-floor sibling)
- `orchestration/react_loop.py:781-974` — insertion point (plan built at 781; TU capture block 898-946; fingerprint/`plan_changed` at 955-956)
- `services/eval_telemetry.py` — add `publish_plan_builder` (mirror `publish_task_understanding:66,138`)
- `middleware/adapters/observability/langfuse_eval_telemetry_sink.py` — add sink method (mirror `:72`)
- `services/eval_capture.py` — already target-agnostic, pass `target="plan_builder"`
- `services/goal_judge_runtime_config.py` — staging-flag template (`ConditionsSource:42`)
- `meta/run_eval.py`, `meta/judge.py`, `meta/drift.py` — offline scoring + drift spine
- `middleware/composition.py:134` (`_wire_eval_telemetry`) — sink already registered, no change needed
- `AGENTS.md` — invariant #3 (components framework-agnostic) and AP-5 (thin orchestration nodes)
