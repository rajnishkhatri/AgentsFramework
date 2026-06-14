# Adding an eval probe for `plan_builder` — the full path

Short version: you are at **Phase 0**, and the single most important thing to know before you
write a line of probe code is that `components/plan_builder.py` is **not the LLM seam** and it
**emits no Recording write today**. That changes where you start. Below is the concrete, phased
path, with the exact repo files and commands at each step.

The governing rule for the whole effort: **write evaluators only for failures you have actually
observed in traces.** Open coding (Phase 2) strictly precedes the rubric (Phase 5). Budget reality:
**60–80% of your time goes into Phases 2–3 (reading traces, building the taxonomy)**, not code. If
most of your effort is going into checks, you are skipping the analysis that makes them worth
anything.

---

## A finding that reshapes the plan — read this first

I read `components/plan_builder.py`. It is **fully deterministic**: `build_plan_artifact`,
`derive_success_conditions`, `validate_plan_mece`, and `compute_plan_fingerprint` are pure
functions over `task_input` plus a `planning_depth` (`L0`/`L1`/`L2`) that is *handed to it*. There
is no `import` of any LLM client, and no `eval_capture.record(...)` call anywhere in the file.

Two consequences:

1. **The actual LLM decision lives upstream**, in `components/router.py` →
   `select_planning_depth(task_input, task_tool_results_count) -> (depth, reason)`. That is the
   call that decides whether the plan is L0/L1/L2. The *quality of the multi-step plan the agent
   executes* is the joint product of (depth choice) × (deterministic decomposition) × (how
   execution actually followed the plan). That joint nature is why this seam is **trace-altitude**,
   not span — exactly the planner case the skill calls out as the classic "span is wrong" seam
   ([reference.md §3](../../../../agentsframework-eval-probe/reference.md)).

2. **There is no Recording write to score against yet.** Phase 1 is therefore not "verify Recording
   works" — it is "*add* the Recording write." That is real Phase-1 work for this seam, not a
   checkbox. The model to copy is `services/tools/delegation_dispatcher.py:132`
   (`await eval_capture.record(...)`), and the publish step is
   `services/eval_telemetry.py` (`publish_*`).

So the honest framing: you are instrumenting the **planning seam** (depth-selection + plan
construction + adherence), with `plan_builder` as the artifact under test and `router` as the
upstream decision, scored at **trace** altitude.

---

## The shape of the journey

```
Phase 0  Decide IF a probe is worth it     → transition failure matrix picks the seam
Phase 1  Pick the seam + altitude          → TRACE altitude; ADD the eval_capture.record write
Phase 2  Open coding                        → read ≥100 planning traces, label first-failures
Phase 3  Axial coding → taxonomy            → 5–6 binary, testable plan-failure categories
Phase 4  Ship the Tier-A probe ★ MILESTONE  → L1 deterministic check (100%) + 1 CI regression row
──────────────────────────────────────────  many seams should stop here  ─────
Phase 5  Rubric + gold set + IAA            → only if Tier-A data shows it is worth it
Phase 6  Judge calibration + enable-gate    → TPR/TNR + θ̂; fail-closed
Phase 7  Tier-B probe + the self-improving loop
```

Phases 0–4 are the spine and your deliverable. Phases 5–7 are the on-demand judge track — earned
with Tier-A data, never front-loaded.

---

## Phase 0 — Confirm the planning seam earns a probe

Don't instrument by vibes; let `phases.jsonl` name the seam. The transition failure matrix
([reference.md §7](../../../../agentsframework-eval-probe/reference.md)) is built over the real
`WorkflowPhase` enum (`services/governance/phase_logger.py`):

```
INITIALIZATION → INPUT_VALIDATION → ROUTING → MODEL_INVOCATION → TOOL_EXECUTION
→ OUTPUT_VALIDATION → EVALUATION
```

- **Rows** = last phase that completed cleanly; **columns** = phase of first failure; **cell** =
  count. The highest-count cell is where a probe earns the most.
- Planning lands in the `ROUTING → MODEL_INVOCATION` band (depth chosen at routing, plan executed
  through the model/tool steps). If failures cluster downstream of a *bad plan* — e.g. the run
  fabricates progress on un-planned subtasks, or the judge marks subtasks unmet — that is the cell
  that justifies this probe.
- The `meta/analysis.py` aggregation function is a planned deliverable; until it lands, aggregate by
  hand. The logs already exist:

```bash
ls cache/phase_logs/*/phases.jsonl | head
# build the From-State × In-State count by hand or with a throwaway script
```

First-failure attribution reuses checks that already exist — `synthesis_validator`,
`guardrail_validator`, `goal_judge goal_met=false`. Note `components/synthesis_validator.py`
already keys off `planning_depth` (open-todos for L1/L2, branch coverage for L2), so it is a natural
first-failure labeler for planning traces.

**Done when:** you can name the seam (planning) and point at the matrix cell that justifies it.

---

## Phase 1 — Seam, altitude, and the Recording write you must add

**Altitude: trace.** A plan can look fine in one call and still be the wrong plan for the
trajectory. A "trace" here is the whole `phases.jsonl` chain for one task.

**Add the Recording write — this is the real work of this phase for this seam.** Every probe scores
against `eval_capture.record(target=…)` → `eval_telemetry` on the same `trace_id`. The verified
signature (`services/eval_capture.py:20`) is:

```python
async def record(
    target: str, ai_input: dict, ai_response: Any, config: dict,
    step: int = 0, model: str | None = None,
    tokens_in=None, tokens_out=None, cost_usd=None, latency_ms=None,
) -> None
```

So in the **orchestration node that calls `router.select_planning_depth` then
`plan_builder.build_plan_artifact`** (not inside `plan_builder` itself — that file is L1-pure and
must stay framework-free), add a write modeled on `services/tools/delegation_dispatcher.py:132`:

```python
from services import eval_capture

await eval_capture.record(
    target="plan_builder",                 # stable name → becomes the probe key
    ai_input={"task_input": task_input,
              "planning_depth": depth,
              "depth_reason": reason},       # from select_planning_depth
    ai_response=plan_artifact.model_dump(),  # ordered_steps + constraints + success_conditions
    config=config,                           # carries task_id / user_id from configurable
    model=model_name,
)
```

`eval.*` fields get the 8192-char exemption vs the 200-char BlackBox cap, so the full plan artifact
survives capture. Then confirm the publish path (`eval_telemetry.publish_*`) lands the record on the
same `trace_id`.

**Done when:** seam named (planning), altitude chosen (trace), and you can see `target="plan_builder"`
records landing in telemetry.

---

## Phase 2 — Open coding (the phase that matters most)

No tooling, no rubric, no judge. Just read plans and write what is wrong, in your own words.

1. Pull **≥ 100 planning traces** (`target="plan_builder"` once Phase 1 is live, plus historical
   `phases.jsonl` runs). Bias toward real traffic; synthesize along the seam's natural dimensions
   (single-vs-multi-part tasks, exclusion constraints, post-tool-synthesis turns) only if volume is
   genuinely too low.
2. For each, find the **first** thing that goes wrong — usually upstream of downstream symptoms.
   Write a short free-text note. Don't pre-categorize.
3. Use the **Three Gulfs** as the *why* lens: **Comprehension** (depth heuristic misread the task —
   e.g. a long multi-part request scored L0), **Specification** (we asked for the wrong thing — the
   branch splitter over/under-segmented), **Generalization** (works on seen cases, breaks on the
   tail).
4. **Stop rule:** keep going until **~20 consecutive traces with no new category** (saturation).

**Sanity band:** ~100% passing ⇒ your sample is too easy; a planning seam worth probing sits around
**~70% pass** under genuine stress.

Concrete failure shapes to expect for *this* code (from reading `plan_builder` + `router`):
under-decomposition (multi-part task collapsed to one step because `task_tool_results_count > 0`
forced L0 post-tool-synthesis); over-decomposition / non-MECE overlapping goals; dropped exclusion
constraint (the `"without"` heuristic missed it); success-conditions that don't cover all branches.

**Done when:** ~100+ traces read, every failure has a first-failure note, ~20 in a row with nothing
new.

---

## Phase 3 — Axial coding → a testable taxonomy

1. Let an LLM **propose clusters** over your notes, then **you rename and merge** — the human owns
   the final names. Aim for **5–6 categories**, each **binary** (present/absent — never a 1–5
   Likert), **distinguishable**, **testable from the trace alone**.
2. Re-label your traces against the structured taxonomy (some notes will move — healthy).
3. Write the taxonomy down as the seam's source of truth (`meta/judge.py` `load_taxonomy()` +
   `meta/judge_prompt.j2` expect one).

Use the **Planning/routing template** from
[reference.md §2](../../../../agentsframework-eval-probe/reference.md) as a *starting prompt*, then
specialize it — never ship generic "plan quality" raw; per the canon, generic metrics manufacture
false confidence:

- **Plan Quality** — complete + realistic (steps cover the task, no fabricated/impossible steps).
- **Plan Adherence** — execution actually matched the plan (trace-altitude: did the agent do the
  planned steps?).
- Plus seam-specific binaries surfaced in Phase 2: **depth-appropriate** (L0/L1/L2 matched task
  complexity), **MECE** (no overlapping goals), **constraint-preserving** (exclusions kept),
  **coverage** (success conditions span all branches).

**Done when:** 5–6 binary, evidence-grounded categories exist and traces are re-labeled.

---

## Phase 4 — Ship the Tier-A probe ★ (this is your milestone)

The cheapest thing that catches the failures you found: a deterministic **L1 check on 100% of
traffic** + **one offline CI regression row**.

**4a. The L1 check — and you already have most of it.** `plan_builder.py` ships
`validate_plan_mece(plan) -> PlanValidationResult` (contiguous step_ids, no overlapping goals,
non-empty success_conditions, non-empty goals). That is the L1-pure spine of your Tier-A check. The
*new* pure function adds the deterministically-detectable subset of your Phase-3 taxonomy:

- plan non-empty; `planning_depth ∈ {L0,L1,L2}` and step count ≤ the depth cap (`L0:1, L1:3, L2:5`);
- success conditions cover every extracted branch (coverage floor);
- exclusion-constraint presence when `"without"` appears in input.

Model the result shape on `guardrail_validator.py` (`ValidationResult`, severity + fail-action;
`pii_rules()`/`api_key_rules()`/`length_rule()` are the rule-factory pattern). Pick only the
*deterministically detectable* categories — Plan Adherence and "realistic" judgement wait for the
Tier-B judge.

**Layer discipline (load-bearing — [reference.md §4](../../../../agentsframework-eval-probe/reference.md)):**
the L1 check and any pure metric live in **`services/`** (stdlib + pydantic, **no framework
imports**). `plan_builder.py` is already L1-pure, so put the new metric in `services/` (e.g.
`services/governance/plan_metrics.py`) and have it consume the `PlanArtifact` — do **not** add eval
logic into `components/`. The eventual judge is L3 `components/`; live replay goes in
`scripts/`/`meta/`, **never CI**.

Verify no leak:

```bash
grep -nE "from components|import langgraph|import langchain" \
  services/governance/plan_metrics.py
# must print NOTHING
```

**4b. The offline CI regression row.** Freeze your Phase-2 failures as a benchmark JSONL. The exact
pattern to copy already exists in this repo for a sibling seam:

- fixture: `tests/fixtures/task_understanding/gate_benchmark_v1.json`
- builder: `docs/research/goaljudge_tu_gate_longterm_plan/build_gate_benchmark_fixture.py`
- replay test: `tests/components/test_task_understanding_gate_benchmark.py`

Create `tests/fixtures/plan_builder/plan_builder_benchmark_v1.json` the same way (each row = a
Phase-2 failing/passing case with the expected per-category verdict), then score it deterministically:

```bash
python -m meta.run_eval \
  --golden-set tests/fixtures/plan_builder/plan_builder_benchmark_v1.json \
  --output /tmp/plan_builder_report.json \
  --report-id plan_builder-tierA
```

Add a CI replay test mirroring `test_task_understanding_gate_benchmark.py` so the failure can't
silently return.

**Tier-A done checklist:**
- [ ] L1 check is a pure function in `services/`, no framework imports (grep is clean)
- [ ] Runs on 100% of the seam's traffic, scored against the `eval_capture.record(target="plan_builder")` write
- [ ] A frozen `plan_builder_benchmark_v1.json` holds the Phase-2 failures
- [ ] `python -m meta.run_eval` scores it green + a CI replay test asserts it
- [ ] You did **not** build a judge yet

**A large fraction of seams should stop here.** The Guardrails seam
([examples.md, Example A](../../../../agentsframework-eval-probe/examples.md)) shipped a 100%
deterministic check with a frozen benchmark and *never* built a gating judge. For `plan_builder`,
the deterministic MECE/coverage/depth checks may well catch most of what you found — if Tier-A
shadow data doesn't show persistent, iterate-worthy failures, **stop here.**

---

## Phases 5–7 — the judge track (only if Tier-A data earns it)

Graduate **only** when Tier-A shadow data shows persistent failures worth a *gating* judge — and
the categories you couldn't catch deterministically (Plan Quality "realistic", Plan Adherence) are
exactly the kind that need one. The GoalJudge worked path is the template
([examples.md, Example B](../../../../agentsframework-eval-probe/examples.md)).

- **Phase 5 — rubric + gold set + IAA.** Promote the taxonomy to a binary judge rubric; build a
  **≥ 100-example** labeled gold set, **split dev/test**, tune on dev only, **freeze + hash the test
  split** (κ ≥ 0.6 is a measurement *prerequisite*, not the headline; IAA via
  `services/governance/iaa.py`). Reuse what exists: `services/governance/goaljudge_goldset_dataset.py`
  already carries an `expected_planning_depth` gold-label and a router-agreement check against
  `components.router.select_planning_depth` — that is a ready-made labeled signal for the
  depth-appropriate category.
- **Phase 6 — calibration + enable-gate.** Generalize the §2.8 evaluator
  (`services/governance/goaljudge_calibration.py`: `confusion_counts` → `precision_recall_fd` →
  `evaluate_section_2_8_gates` → a fail-closed `GateDecision`). **Headline = TPR/TNR on the frozen
  test split** (positive class = "judge says *not-met*", so a false positive is a **false
  downgrade**). Report the bias-corrected production rate
  `θ̂ = (p_obs + TNR − 1)/(TPR + TNR − 1)` with a bootstrap 95% CI. Thresholds: precision ≥ 0.90,
  recall(=TPR) ≥ 0.70, false-downgrade(=1−TNR) ≤ 0.02, flip ≤ 0.05, κ ≥ 0.6. Keep a golden-number
  fixture (mirror GoalJudge's TP=69 FP=8 FN=8 TN=12 ⇒ α=0.4987) so the math can't drift silently.
  The gate is **fail-closed**: a provisional gold set ⇒ `REFUSE` before any metric is read.
- **Phase 7 — Tier-B probe + the loop.** Register an **L2 sampled judge** (5–10%, `meta/judge.py`)
  and **L3 drift** (`meta/drift.py`). The loop trigger is **cadence-first**: re-run open coding on
  100+ fresh planning traces **every 2–4 weeks**, plus a **change-event hook** (any edit to
  `select_planning_depth` heuristics or `plan_builder` splitter → re-run the offline probe). EWMA/
  CUSUM only surface candidates between cycles; threshold **θ̂ + CI**, never a raw judge count.

```bash
# Tier-B drift (scheduled, NOT CI):
python -m meta.drift --baseline baseline_scores.jsonl \
  --production prod_scores.jsonl --level all --output /tmp/plan_drift.json
```

**The terminal acting decision is a runtime-config write a human owns** — this skill produces the
decision and stops. The probe never flips a flag.

---

## Where to start, in one line

**Phase 0–1 is your starting point**, and the first concrete edit is **adding
`eval_capture.record(target="plan_builder")` in the orchestration node that calls
`router.select_planning_depth` + `plan_builder.build_plan_artifact`** — because that write does not
exist yet and every later phase scores against it. Then read ≥100 planning traces (Phase 2) before
writing a single check. Most of your value will be a Phase-4 Tier-A probe: a `services/` pure check
built on the existing `validate_plan_mece`, plus a frozen `plan_builder_benchmark_v1.json` scored in
CI — copied from the `task_understanding` gate-benchmark pattern. Reach for the judge track only if
that Tier-A data proves you need it.

### Key repo files

- `components/plan_builder.py` — the deterministic artifact under test (already L1-pure; `validate_plan_mece` is your L1 spine)
- `components/router.py` (`select_planning_depth`) — the upstream LLM/heuristic decision that makes this a **trace**-altitude seam
- `components/synthesis_validator.py` — depth-aware first-failure labeler for Phase 0/2
- `services/eval_capture.py` (`record`, line 20) + `services/eval_telemetry.py` — the Recording write you must add in Phase 1
- `services/tools/delegation_dispatcher.py:132` — the working `eval_capture.record(...)` call to model on
- `services/governance/guardrail_validator.py` — `ValidationResult`/rule-factory shape for the Phase-4 L1 check
- `services/governance/phase_logger.py` + `cache/phase_logs/*/phases.jsonl` — `WorkflowPhase` enum + logs for the Phase-0 matrix
- `tests/fixtures/task_understanding/gate_benchmark_v1.json` + `tests/components/test_task_understanding_gate_benchmark.py` + `docs/research/goaljudge_tu_gate_longterm_plan/build_gate_benchmark_fixture.py` — the Phase-4 benchmark + CI-regression pattern to copy
- `meta/run_eval.py` — the Phase-4 CI scorer (`--golden-set/--output/--report-id`)
- `services/governance/iaa.py` — Phase-5 κ/α
- `services/governance/goaljudge_calibration.py` + `services/governance/goaljudge_goldset_dataset.py` (`expected_planning_depth`) — Phase-6 enable-gate template + a ready-made depth gold label
- `meta/judge.py` / `meta/judge_prompt.j2` / `meta/drift.py` — Phase-7 judge + drift
