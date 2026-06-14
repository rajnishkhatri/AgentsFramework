# Adding an eval probe to the summarizer (`services/summarizer.py`)

## What we're monitoring and why it's "unmonitored"

`services/summarizer.py` is the deterministic trajectory-compaction seam. It exposes two pure functions:

- `should_compact_trajectory(*, current_token_count, token_threshold) -> bool`
- `build_compaction_summary(*, task_input, reasoning_trace, tool_results, latest_output) -> str`

It is called from exactly one place: `orchestration/react_loop.py:1491-1505`. When token pressure crosses `agent_config.trajectory_compaction_token_threshold` (default `3000`, defined at `services/base_config.py:37`), the loop builds a compaction summary, writes it to `.agent_offload/trajectory_summary_<wf>.md`, and **replaces** `reasoning_trace` with that single summary (`result["reasoning_trace"] = [summary_text]`, `truncation_applied = True`).

That replacement is exactly why this seam is risky and worth a probe: a bad summary silently drops context the agent needs for the rest of the run, and today **nothing scores it**. Unit tests (`tests/services/test_reasoning_tools.py`) only assert the summary string contains its section headers — they do not assess whether the summary actually preserves the task's critical context. There is no `eval_capture.record(target="summarizer", ...)` call, so summarizer outputs never reach the offline judge (`meta/run_eval.py`) or Langfuse (`services/eval_telemetry.py`), and the drift detector (`meta/drift.py`) has no score stream to watch.

The probe has to bolt onto the seam the same way `goal_judge` already does — capture → telemetry → judge → drift — not reinvent any of it.

## The four pieces of the existing probe pattern (reuse, don't rebuild)

The `goal_judge` probe is the reference implementation. Trace it to copy its shape:

1. **Capture at the call site** — `orchestration/react_loop.py:1673` calls `await eval_capture.record(target="goal_judge", ai_input=..., ai_response=..., config=config, step=..., model=...)`. `services/eval_capture.py` builds an `EvalRecord`-shaped dict (`components/schemas.py:44`) and logs it with `target` tags. Note its contract: it never imports `components/`, and it's fire-and-forget.
2. **Telemetry publish** — immediately after capture, `react_loop.py:1683` calls `await eval_telemetry.publish_goal_judge(...)`. `services/eval_telemetry.py` forwards to a registered sink, redacts PII, and **must not raise** (the `try/except` swallows everything). When no sink is registered (unit tests, bare CLI) it's a no-op.
3. **Sink registration (composition root)** — `middleware/composition.py:134-136` (`_wire_eval_telemetry`) calls `set_sink(LangfuseEvalTelemetrySink(exporter))`. The sink (`middleware/adapters/observability/langfuse_eval_telemetry_sink.py`) maps the eval row to an `eval.<target>` Langfuse observation on the same `trace_id`.
4. **Offline judge + drift** — `meta/judge.py` scores an `EvalRecord` against `meta/discovery/failure_taxonomy.json` (1–5 score + failure categories). `meta/run_eval.py` runs a golden set through the judge and aggregates `mean_score`. `meta/drift.py` then watches that score stream (Level 1 = 2-sigma perf drift; Level 2 = judge-vs-human Cohen's kappa).

Our job: wire `target="summarizer"` into pieces 1–2 at the summarizer call site, give the judge a summarizer-specific rubric for piece 4, and seed a golden set. **Start deterministic** (shadow capture only) so the probe can never change runtime behavior.

---

## Phase 0 — Define what "good" means before writing any code

A probe is worthless without a rubric grounded in real failures. The summarizer's job is *lossless-enough compaction*, so the failure modes are about what the summary drops or distorts.

1. Pull 15–30 real compaction events to look at. The summarizer fires only when `truncation_applied` is set, and it writes to `.agent_offload/trajectory_summary_*.md`, so grep production logs / Langfuse for `truncation_applied` traces, or run a handful of long tasks locally and inspect the offload files.
2. Hand-label each: did the summary preserve the task, the recent tool calls, and the latest output well enough that an agent reading *only the summary* could continue correctly? Write down the recurring failure patterns. Candidates, by analogy to `meta/discovery/failure_taxonomy.json`:
   - **context_loss** — a success-critical fact present in `reasoning_trace`/`tool_results` is absent from the summary (the `[-3:]` windows in `build_compaction_summary` are the prime suspect).
   - **task_drift** — the `- task:` line no longer reflects the original `task_input`.
   - **tool_result_distortion** — a tool outcome is misstated vs the actual `tool_results` entry.
   - **truncation_mangle** — the `[:120]`/`[:280]`/`[:200]` slices cut mid-token and corrupt meaning.
3. Decide the metric and bar. Match the repo convention: a 1–5 judge score, plus per-category failure counts. Pick a launch floor (e.g. mean ≥ 4.0 on the golden set) the same way the `goal_judge` work used a v0.9 floor gate.

Deliverable: a short rubric doc + a candidate category list. No code yet.

---

## Phase 1 — Add the offline judge rubric + a golden set

Make the seam scorable offline first; this is cheap, deterministic, and de-risks everything downstream.

1. **Extend the taxonomy.** Add the summarizer categories from Phase 0 to `meta/discovery/failure_taxonomy.json` (MECE, with `id`/`label`/`description`/`severity`). The judge (`meta/judge.py:45 load_taxonomy`) reads this file directly, so new categories flow through automatically.
2. **Give the judge a summarizer-aware prompt.** `meta/judge.py:24` renders `meta/judge_prompt.j2`. The current prompt is trajectory-generic. Either teach it to grade summarizer rows (the rubric: "given the original task/trace/tools, does this summary preserve the critical context?") gated on `eval_record.target == "summarizer"`, or add a sibling template — keep the existing `goal_judge`/default path untouched.
3. **Seed a golden set.** Convert the Phase 0 labeled events into a JSONL of `EvalRecord` rows (`components/schemas.py:44`) with `target: "summarizer"`. Each row's `ai_input` = `{task_input, reasoning_trace, tool_results, latest_output, current_token_count, token_threshold}`; `ai_response` = the produced `summary_text`. Store under `tests/services/fixtures/` next to `guardrail_evalset.jsonl`, or under `cache/` alongside the existing `cache/goaljudge_eval/*.jsonl` golden sets.
4. **Score it.**
   ```bash
   python -m meta.run_eval \
     --golden-set tests/services/fixtures/summarizer_evalset.jsonl \
     --output /tmp/summarizer_eval_report.json \
     --report-id summarizer-v0.9
   ```
   (Judge model from `META_JUDGE_MODEL`, default `gpt-4o-mini` — see `meta/run_eval.py:177`.) This validates the rubric on hand-labeled rows where you already know the right answer. If the judge disagrees with your labels, fix the prompt/categories before going further — do **not** wire it into runtime yet.

---

## Phase 2 — Capture summarizer events at the call site (shadow, behavior-preserving)

Now emit live summarizer events without changing what the agent does.

1. **Record at the seam.** In `orchestration/react_loop.py`, right after the compaction block (`react_loop.py:1495-1505`, where `summary_text` is built and `truncation_applied` is set), add a fire-and-forget capture mirroring the `goal_judge` block at `react_loop.py:1673-1680`:
   ```python
   await eval_capture.record(
       target="summarizer",
       ai_input={
           "task_input": state.get("task_input", ""),
           "reasoning_trace": state.get("reasoning_trace", []),
           "tool_results": state.get("tool_results", []),
           "latest_output": content,
           "current_token_count": token_count,
           "token_threshold": agent_config.trajectory_compaction_token_threshold,
       },
       ai_response={"summary_text": summary_text, "offload_ref": offload_ref},
       config=config,
       step=updated_step_count,  # available a few lines below at react_loop.py:1507
   )
   ```
   `eval_capture.record` is already imported and async-safe here. Keep it best-effort — wrap it like the other call sites if you want belt-and-suspenders, but `record` itself only logs.
2. **Publish to telemetry (optional in this phase, recommended).** Add a `publish_summarizer(...)` to the `EvalTelemetrySink` Protocol in `services/eval_telemetry.py` (mirror `publish_task_understanding` at `eval_telemetry.py:138` — it's the newer, cleaner template that uses `getattr(_sink, "publish_summarizer", None)` so older sinks degrade gracefully). It must redact via `_redact_mapping` and never raise. Implement the method on `LangfuseEvalTelemetrySink` (`middleware/adapters/observability/langfuse_eval_telemetry_sink.py`) so the row lands as an `eval.summarizer` observation. The composition root at `middleware/composition.py:134` needs no change — it already wires the sink. Then call `await eval_telemetry.publish_summarizer(...)` right after the `record` call, passing `trace_id = state.get("workflow_id")` like the goal_judge block at `react_loop.py:1681-1691`.
3. **Behavior-preservation guarantee.** Capture/publish are downstream of the existing summary write and don't touch `result`, so runtime output is byte-identical whether or not the probe is present. This is the summarizer equivalent of the `goal_judge` "shadow" stage — observe before you gate.

Tests to add (match the existing suites):
- `tests/services/test_eval_capture.py` style: a `target="summarizer"` row serializes to a valid `EvalRecord`.
- `tests/services/test_eval_telemetry.py` style: `publish_summarizer` is a no-op with no sink and never raises when the sink throws.
- `tests/middleware/adapters/observability/test_langfuse_eval_telemetry_sink.py` style: the row maps to an `eval.summarizer` observation.
- An `orchestration/` loop test asserting that when `should_compact_trajectory` returns True, exactly one summarizer eval row is captured and `result["reasoning_trace"]`/`truncation_applied` are unchanged.

Run: `pytest tests/services/test_eval_capture.py tests/services/test_eval_telemetry.py tests/services/test_reasoning_tools.py tests/middleware/adapters/observability/ -q`

---

## Phase 3 — Wire the captured stream into drift monitoring (continuous)

Capture alone gives you data; drift gives you alerts.

1. **Periodic scoring.** Schedule `meta/run_eval.py` against a rolling golden/sampled set of `target="summarizer"` rows (the goal_judge corpus is harvested via `scripts/export_goaljudge_corpus.py` — add an analogous filter on `target == "summarizer"`, or sample captured rows from logs/Langfuse). This runs on the same cadence the eval pipeline already uses (Cloud Run Job / `python -m meta.run_eval`). Persist each run's `mean_score`.
2. **Feed `meta/drift.py`.** Append each run's per-row scores to a JSONL and run the existing CLI:
   ```bash
   python -m meta.drift \
     --baseline summarizer_baseline_scores.jsonl \
     --production summarizer_latest_scores.jsonl \
     --level 1 \
     --alert-log-dir <phase_logger_dir> \
     --workflow-id summarizer-drift
   ```
   Level 1 (`detect_performance_drift`, `meta/drift.py:48`) flags a 2-sigma drop vs the Phase 1 baseline. The `--alert-log-dir` path emits each triggered alert as a governance `Decision` via `emit_drift_alerts` (`meta/drift.py:213`), so summarizer drift shows up in the same governance trail as everything else. Exit code 1 = drift detected — wire that to your alerting.
3. **Level 2 (calibration), later.** Once you have human re-labels of a sample of judged summarizer rows, feed `(human_labels, judge_labels)` to `detect_calibration_drift` (`meta/drift.py:129`) to confirm the judge still agrees with humans (Cohen's kappa ≥ 0.75). This guards against the judge itself drifting — the same κ-vs-α discipline the goal_judge gold-set work used.

---

## Phase 4 — Promote from shadow to gate (only after the data earns it)

1. Watch the `eval.summarizer` stream in Langfuse and the drift report for 1–2 weeks. Confirm the score distribution and that real `context_loss` cases are caught.
2. If you want a runtime gate (e.g. "if a summary is judged low-quality, don't replace `reasoning_trace` / re-summarize / keep the raw tail"), put it behind a runtime-config flag rather than hard-wiring it — the same `enabled` / `downgrade_enabled` two-flag, TTL-cached, stale-on-error pattern as `services/goal_judge_runtime_config.py` (`GoalJudgeRuntimeConfigReader`). That lets you flip the gate without redeploying and roll back instantly. Default it **off**; only enable after the floor gate (Phase 0 bar, e.g. mean ≥ 4.0) holds in production.
3. Keep capture/publish on permanently regardless of whether the gate is enabled — observability should outlive any one gating decision.

---

## Summary of files touched

| Phase | File | Change |
|---|---|---|
| 1 | `meta/discovery/failure_taxonomy.json` | add summarizer failure categories |
| 1 | `meta/judge_prompt.j2` (or sibling template) | summarizer-aware grading rubric, gated on `target` |
| 1 | `tests/services/fixtures/summarizer_evalset.jsonl` (new) | hand-labeled golden set |
| 2 | `orchestration/react_loop.py` (~line 1505) | `eval_capture.record(target="summarizer", ...)` + `publish_summarizer(...)` |
| 2 | `services/eval_telemetry.py` | add `publish_summarizer` to Protocol + module fn (mirror `publish_task_understanding`) |
| 2 | `middleware/adapters/observability/langfuse_eval_telemetry_sink.py` | implement `publish_summarizer` → `eval.summarizer` observation |
| 2 | `tests/services/`, `tests/middleware/adapters/observability/`, `orchestration/` tests | capture/publish/behavior-preservation coverage |
| 3 | scoring job (cron / Cloud Run Job) + drift CLI | periodic `meta/run_eval.py` → `meta/drift.py --level 1` |
| 4 | new `services/summarizer_runtime_config.py` (only if gating) | flag-gated promotion, mirroring `goal_judge_runtime_config.py` |

The discipline that matters: **shadow-capture first (no behavior change), validate the rubric on hand-labels before trusting the judge live, and gate only behind a runtime flag once the score stream earns it.** Reuse the `eval_capture → eval_telemetry → sink → judge → drift` spine the `goal_judge` probe already established rather than building a parallel path.
