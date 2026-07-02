# agentsframework-eval-probe — Command Cookbook

Copy-paste invocations, **CI-safe first, live runs clearly fenced.** Every command here was
verified against the repo's actual CLI signatures. Use `.venv/bin/python` if the repo venv is the
convention in your shell; plain `python -m …` works when the venv is active.

---

## Offline / CI-safe

### The Tier-A merge gate: a pytest replay over a frozen fixture

The deterministic Tier-A regression gate is a **pytest replay**, not `meta.run_eval`. Freeze the
Phase-2 failures as a must-accept / must-reject fixture and assert your pure L1 check lands every
case correctly — mirror `tests/components/test_task_understanding_gate_benchmark.py`:

```bash
# The merge-blocking Tier-A gate (deterministic, no LLM, no keys):
.venv/bin/python -m pytest tests/services/test_<seam>_eval.py -q
# fixture lives at e.g. tests/fixtures/<seam>/<seam>_benchmark_v1.json (must_accept / must_reject)
```

### Score with the LLM judge (Phase 7 / judge-track only — NOT the Tier-A gate)

```bash
# meta.run_eval expects EvalRecord JSONL and runs an LLM judge. Use it once a seam HAS a judge,
# not as the deterministic Tier-A merge gate. Prints: "Eval complete: scored=… failed=… mean=…"
python -m meta.run_eval \
  --golden-set path/to/<seam>_goldset.jsonl \
  --output /tmp/<seam>_report.json \
  --report-id <seam>-judge
# --golden-set accepts a local path OR a gs:// URI; --output likewise.
```

### Run the L1 / regression test sweep

```bash
# The existing eval-pipeline regression set (model on this for a new seam):
.venv/bin/python -m pytest \
  tests/services/test_goaljudge_calibration.py \
  tests/services/test_goaljudge_goldset_dataset.py \
  tests/components/test_goal_judge*.py \
  tests/architecture/test_goal_judge_runtime_config_layer.py -q
```

### Dependency-leak audit (an L1 pure check must import nothing framework-ish)

```bash
# Must print NOTHING. A hit means your "pure" metric leaked a framework import.
grep -nE "from components|import langgraph|import langchain" \
  services/governance/<your_new_metric>.py
```

---

## Drift (Tier-B, scheduled — not in CI)

```bash
# 3-level drift check. Exit code: 0 = no drift, 1 = drift detected, 2 = error.
python -m meta.drift \
  --baseline baseline_scores.jsonl \
  --production prod_scores.jsonl \
  --level all \
  --output /tmp/drift_report.json
# --level ∈ {1,2,3,all}: 1=performance(2σ), 2=calibration(κ), 3=governance(registry).
# Level 3 also needs --registry-dir <AgentFacts dir>.

# Optionally log triggered alerts as governance Decisions into a PhaseLogger:
python -m meta.drift --baseline … --production … --level all \
  --alert-log-dir /tmp/<seam>_drift_alerts --workflow-id <seam>-drift
```

The drift CLI reads JSONL score files. Produce them from your captured `EvalRecord`s via the
offline harness (`meta/analysis.py` `load_eval_records` → `compute_metrics`), or via
`services/observability.py` `save_telemetry`/`load_telemetry`.

---

## Inspect the seam prioritizer (transition failure matrix)

The aggregation function is a planned `meta/analysis.py` deliverable. Until it lands, the inputs
already exist — aggregate by hand from the phase log:

```bash
# Where the WorkflowPhase transitions are logged (one JSON object per line):
ls phases.jsonl 2>/dev/null || find . -name "phases.jsonl" | head
# Each line carries the phase + outcome; build the From-State × In-State count by hand
# (or with a short throwaway script) — see reference.md §7 for the matrix definition.
```

---

## What this skill deliberately does NOT run

- **The runtime flag flip** (`goal_judge_downgrade_enabled`, `success_conditions_source`). That is a
  runtime-config write a human owns. The probe workflow produces the *decision*; it never flips the
  flag. (GoalJudge-specific flip path: defer to the `agentsframework-eval` skill.)
- **A live judge in CI.** The L2 sampled judge and any live replay run in `scripts/` / `meta/` on a
  schedule, never as a CI test — CI uses the frozen offline benchmark only.

---

## Capture a trace from your seam (Phase 1 wiring)

```python
# Inside your component, after the LLM call — this is the Recording-pillar write
# every probe scores against.
from services import eval_capture

await eval_capture.record(
    target="my_seam",        # stable name → becomes the probe's key
    ai_input={...},          # what went in
    ai_response=result,      # dict or str
    config=config,           # carries task_id / user_id from configurable
    model=model_name,        # optional but recommended
    # tokens_in / tokens_out / cost_usd / latency_ms are optional kwargs
)
```
