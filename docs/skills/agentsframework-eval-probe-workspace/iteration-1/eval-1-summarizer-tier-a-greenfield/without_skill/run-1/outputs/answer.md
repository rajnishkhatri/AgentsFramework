# Adding an eval probe to `services/summarizer.py`

## What "unmonitored" means here, concretely

`services/summarizer.py` is the deterministic trajectory-compaction helper. It exposes two pure functions:

- `should_compact_trajectory(current_token_count, token_threshold) -> bool`
- `build_compaction_summary(task_input, reasoning_trace, tool_results, latest_output) -> str`

Its only runtime caller is `orchestration/react_loop.py` (around lines 1490-1505): when token pressure crosses `agent_config.trajectory_compaction_token_threshold`, it builds the summary, offloads it to `.agent_offload/trajectory_summary_<wf>.md`, and replaces `reasoning_trace` with `[summary_text]`.

Here is the gap. Every other LLM/tool/guardrail seam in this repo records itself through `services.eval_capture.record(target=..., ...)`. That emits an `EvalRecord`-shaped dict (the `AI Response` log line) that gets harvested into golden sets, scored by `meta/judge.py`, aggregated by `meta/run_eval.py`, and watched by `meta/drift.py`. The summarizer calls **none** of this. So:

- There is **no `EvalRecord` with `target="summarizer"`** anywhere — confirmed by grepping `target=` call sites (`code_reviewer.frontend`, `code_review`, `optimizer_benchmark`, `pyramid_guardrail`, etc., but no summarizer).
- The compaction step is invisible to the nightly meta-eval Cloud Run Job (`infra/gcp/meta.tf` → `python -m meta.run_eval`) and to the drift CLI (`python -m meta.drift`).
- A summary that silently drops the task intent, the recent tool names, or the latest output — the four things `build_compaction_summary` is supposed to preserve — would never trip an alert. That is the actual risk: compaction corrupts the agent's working memory mid-run and nobody finds out.

So "add an eval probe" = wire this seam into the same recording → judging → drift loop everything else uses, and add a deterministic quality check tailored to what compaction is supposed to preserve.

## Design decision: deterministic probe first, LLM judge in shadow

The summarizer is **deterministic**, so the primary probe should be deterministic too — a quality function that checks the summary actually contains what it promised. That gives a cheap, CI-safe signal (no API key, follows the repo's "L2-pure CI" convention). The LLM judge (`meta/judge.py`) is layered on top in **shadow mode** behind a config flag, mirroring how `goal_judge_enabled` / `goal_judge_downgrade_enabled` are split in `services/base_config.py` (judge runs, gathers verdicts, changes nothing until a gold-set gate is met).

---

## Phase 0 — Reproduce the gap (10 min)

Confirm there is no summarizer signal today before touching anything.

```bash
# No summarizer EvalRecords are produced anywhere:
grep -rn 'target="summarizer"' --include="*.py" . | grep -v test    # expect: nothing

# The only caller, for reference:
grep -n "build_compaction_summary\|should_compact_trajectory" orchestration/react_loop.py

# Existing tests that pin current behaviour (don't break these):
.venv/bin/python -m pytest tests/services/test_reasoning_tools.py -q
```

## Phase 1 — Deterministic quality probe (the core deliverable)

Add a pure scoring function next to the summarizer. It encodes the contract `build_compaction_summary` already promises (task / recent_tools / recent_reflection / latest_output sections) so the probe and the producer stay co-located and can't drift apart.

**File: `services/summarizer.py`** — add alongside the existing helpers:

```python
class CompactionProbe(BaseModel):
    """Deterministic quality signal for a compaction summary."""
    score: float                      # 0.0-1.0, fraction of preserved signals
    preserved: list[str]              # which critical sections survived
    dropped: list[str]                # which were lost (the alertable ones)
    char_len: int

def probe_compaction_summary(
    *,
    summary_text: str,
    task_input: str,
    reasoning_trace: list[str],
    tool_results: list[dict],
    latest_output: str,
) -> CompactionProbe:
    """Score a summary on whether it preserved the signals it claims to.

    Pure + deterministic: no LLM, no I/O. Safe to run in L2-pure CI.
    Checks the four sections build_compaction_summary() promises:
      - task intent present
      - recent tool names present (when any tools ran)
      - recent reflection present (when a trace exists)
      - latest output present (when non-empty)
    """
    checks: dict[str, bool] = {}
    s = summary_text or ""
    task_line = (task_input or "").strip()[:60]
    if task_line:
        checks["task"] = task_line in s
    recent_tools = [str(t.get("tool_name", "")) for t in tool_results[-3:]]
    recent_tools = [t for t in recent_tools if t]
    if recent_tools:
        checks["recent_tools"] = any(t in s for t in recent_tools)
    if reasoning_trace:
        checks["recent_reflection"] = any(e[:40] in s for e in reasoning_trace[-3:])
    latest = (latest_output or "").strip()[:60]
    if latest:
        checks["latest_output"] = latest in s
    preserved = [k for k, ok in checks.items() if ok]
    dropped = [k for k, ok in checks.items() if not ok]
    score = len(preserved) / len(checks) if checks else 1.0
    return CompactionProbe(
        score=score, preserved=preserved, dropped=dropped, char_len=len(s),
    )
```

Why this shape: `score` is a 0-1 float, which is exactly what `meta/drift.py::detect_performance_drift` consumes (it loads JSONL lines with a `score` field). `dropped` is the human-readable failure reason. Keeping it pure means it runs in CI with no keys.

**Tests: `tests/services/test_reasoning_tools.py`** (extend the existing file):

```python
def test_probe_full_preservation():
    summary = build_compaction_summary(
        task_input="Refactor the auth module",
        reasoning_trace=["decided to start with token validation"],
        tool_results=[{"tool_name": "read_file"}, {"tool_name": "grep"}],
        latest_output="Found three call sites",
    )
    probe = probe_compaction_summary(
        summary_text=summary,
        task_input="Refactor the auth module",
        reasoning_trace=["decided to start with token validation"],
        tool_results=[{"tool_name": "read_file"}, {"tool_name": "grep"}],
        latest_output="Found three call sites",
    )
    assert probe.score == 1.0 and probe.dropped == []

def test_probe_detects_dropped_signal():
    # A summary that lost the task line must score < 1.0 and name it.
    probe = probe_compaction_summary(
        summary_text="recent_tools: grep",
        task_input="Refactor the auth module",
        reasoning_trace=[], tool_results=[{"tool_name": "grep"}], latest_output="",
    )
    assert probe.score < 1.0 and "task" in probe.dropped
```

```bash
.venv/bin/python -m pytest tests/services/test_reasoning_tools.py -q
```

## Phase 2 — Wire the probe into the runtime (the recording seam)

Make the seam emit an `EvalRecord` every time compaction fires, exactly like every other monitored seam. This is the piece that ends "not monitored at all."

**File: `orchestration/react_loop.py`** — inside the `if should_compact_trajectory(...)` block (after `summary_text` is built, ~line 1503):

```python
from services.summarizer import probe_compaction_summary
from services import eval_capture

probe = probe_compaction_summary(
    summary_text=summary_text,
    task_input=state.get("task_input", ""),
    reasoning_trace=state.get("reasoning_trace", []),
    tool_results=state.get("tool_results", []),
    latest_output=content,
)
await eval_capture.record(
    target="summarizer",
    ai_input={
        "token_count": token_count,
        "threshold": agent_config.trajectory_compaction_token_threshold,
        "trace_len": len(state.get("reasoning_trace", []) or []),
        "tool_count": len(state.get("tool_results", []) or []),
    },
    ai_response={
        "summary": summary_text,
        "probe_score": probe.score,
        "dropped": probe.dropped,
    },
    config=config,           # carries configurable.task_id / user_id
    step=updated_step_count,
)
```

Notes:
- `services.eval_capture.record` is `async`; the surrounding node is already async, so `await` it. It must **not** raise into the loop — it only logs; if you want belt-and-suspenders, wrap in try/except and log a warning (matches the non-blocking posture in `meta/drift.py::emit_drift_alerts`).
- Use `target="summarizer"` consistently — that string is the key the golden-set extraction and the judge filter on.
- The repo enforces "services must not import components," which is why `eval_capture.record` builds a plain dict, not an `EvalRecord`. Keep that boundary: emit the dict here; the `EvalRecord` model is only used downstream when reading.

Verify the record actually emits:

```bash
grep -rn "target=\"summarizer\"" orchestration/react_loop.py
# Run any react-loop test that triggers compaction (or a small repro) and confirm
# an "AI Response" log line with target=summarizer appears.
.venv/bin/python -m pytest tests/orchestration -q -k compact
```

## Phase 3 — Shadow LLM judge (optional, behind a flag)

For semantic quality beyond the deterministic checks (e.g. "is this summary faithful / not hallucinated"), layer the existing judge in shadow mode. Follow the `goal_judge_enabled` precedent exactly.

1. **`services/base_config.py`** — add, defaulting **off** so CI stays L2-pure:
   ```python
   summarizer_probe_judge_enabled: bool = False   # shadow: judge scores, changes nothing
   ```
2. **`meta/discovery/failure_taxonomy.json`** — the current categories are tool/argument/loop/termination/hallucination/guardrail/cost. Add a compaction-specific one, e.g. `lossy_compaction` (summary dropped a critical signal), so judge labels are meaningful for this seam.
3. In `react_loop.py`, when `summarizer_probe_judge_enabled` is true, build an `EvalRecord`-shaped object from the captured dict and call `meta.judge.score_eval_record(...)` with the fast judge profile. Log the `JudgeScore` alongside the deterministic probe — **do not** let it change `summary_text`, the offload, or the trajectory. Shadow only.

Keep the flag off until you have a gold set and a calibration gate (Phase 4/5), mirroring the goal-judge rollout discipline in this repo.

## Phase 4 — Golden set + baseline

The probe is only as good as a frozen reference to compare against.

1. Run the agent (or a representative batch) with Phase 2 in place; collect the emitted `target="summarizer"` records into a JSONL golden set. The capture format is already `EvalRecord`-loadable via `EvalRecord.model_validate_json` (see `meta/run_eval.py::load_golden_set`).
2. Hand-check a sample: every row's `ai_response.probe_score` and `dropped` should match what you'd judge by eye. Fix any probe false-positives/negatives in `probe_compaction_summary` before freezing.
3. Save it where the eval job expects it. The terraform default is:
   ```
   gs://<trust-traces-bucket>/golden/eval.jsonl
   ```
   Either contribute summarizer rows to that set or stand up a seam-scoped `golden/summarizer.jsonl` and point a dedicated run at it.
4. Produce the baseline score file (one `{"score": ...}` JSON per line) that drift will diff against:
   ```bash
   .venv/bin/python -m meta.run_eval \
       --golden-set golden/summarizer.jsonl \
       --output reports/summarizer_baseline.json \
       --report-id summarizer-baseline
   ```

## Phase 5 — Drift gate (continuous monitoring)

This closes the loop — the seam now actually gets *monitored*, not just recorded.

`meta/drift.py` Level 1 (`detect_performance_drift`) compares a baseline score list to a production score list with a 2-sigma threshold. Feed it the `probe_score` stream:

```bash
.venv/bin/python -m meta.drift \
    --baseline reports/summarizer_baseline_scores.jsonl \
    --production reports/summarizer_prod_scores.jsonl \
    --level 1 \
    --alert-log-dir .agent_offload/drift_alerts \
    --workflow-id summarizer-probe
# exit 0 = no drift, 1 = drift detected, 2 = error
```

When drift fires with `--alert-log-dir` set, `emit_drift_alerts` logs a governance `Decision` (phase=EVALUATION) per alert — so a lossy-compaction regression shows up in the same governance trail as everything else.

**Wiring it to run on a schedule** (so it is genuinely monitored, not run by hand): the nightly meta ring already exists in `infra/gcp/meta.tf` (Cloud Scheduler → Cloud Run Job → `python -m meta.run_eval`, default 06:00 UTC, gated by `enable_meta_ring`). Two options:
- Add a drift step to that job's command after the eval runs, or
- Extend the job to also invoke `python -m meta.drift` against the fresh report vs the frozen baseline.
Enable `enable_meta_ring = true` in `terraform.tfvars` once the golden set is uploaded (it is intentionally off / ~$0 until then).

## Phase 6 — Optional human-validation probe script

For ad-hoc inspection, mirror `scripts/probe_guardrail.py` (the repo's existing interactive-probe pattern): a small `scripts/probe_summarizer.py` with a table of frozen example trajectories and `expect_score` assertions, so a human can eyeball compaction quality offline with no keys:

```bash
.venv/bin/python scripts/probe_summarizer.py --list
.venv/bin/python scripts/probe_summarizer.py --example lossy-drops-task
```

This is purely for human review/debugging; the CI signal is Phase 1's pytest and the automated signal is Phase 5's drift gate.

---

## Summary of files touched

| Phase | File | Change |
|------|------|--------|
| 1 | `services/summarizer.py` | add `CompactionProbe` + `probe_compaction_summary()` (pure) |
| 1 | `tests/services/test_reasoning_tools.py` | full-preservation + dropped-signal tests |
| 2 | `orchestration/react_loop.py` (~L1503) | call probe + `eval_capture.record(target="summarizer")` |
| 3 | `services/base_config.py` | `summarizer_probe_judge_enabled: bool = False` (shadow) |
| 3 | `meta/discovery/failure_taxonomy.json` | add `lossy_compaction` category |
| 4 | `golden/summarizer.jsonl` (GCS) | frozen golden set + baseline scores |
| 5 | `infra/gcp/meta.tf` | add drift step / enable meta ring |
| 6 | `scripts/probe_summarizer.py` | optional human-validation script |

## Order of operations (smallest shippable first)

1. **Phase 1** alone is a complete, mergeable unit: a tested deterministic probe with zero runtime risk.
2. **Phase 2** turns on recording — this is the line that literally fixes "not monitored at all."
3. **Phases 4-5** give you the baseline + automated drift gate (the part that makes it *continuous* monitoring).
4. **Phases 3 and 6** are optional enhancements (semantic shadow scoring, human inspection) — defer until the deterministic loop is green and you have a gold set.

Keep the LLM judge **off by default** the whole time so CI stays L2-pure (no live LLM calls), consistent with the `goal_judge_enabled` convention already in `services/base_config.py`.
