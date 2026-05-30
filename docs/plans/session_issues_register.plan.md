# Session Issues Register: Austin-Weather Trace Review

Issues found while reviewing the trace from `python scripts/_dbg_d9c823_send.py` (`trace_id 674cbac3…`). Each entry has a grounded root cause and a proposed fix. Nothing here is implemented yet.

## Behavioral correctness

### I1 (High) Agent loops on a stubbed tool with no no-progress detection
- Symptom: 10 near-duplicate `web_search` calls returning the same stub, then a self-terminated "I can't get the weather" answer at step 10.
- Root cause: the stub returns a success-shaped payload (`ok=True`) in [services/tools/web_search.py](services/tools/web_search.py), and the loop terminator only stops on `max_steps` (20), budget, `terminal` error, or a clean success with no pending tool result — see `check_continuation` in [components/evaluator.py](components/evaluator.py):120. There is no detection of repeated identical tool calls or non-progressing tool outputs, so the model is free to thrash until it gives up on its own.
- Proposed fix: add a no-progress guard in `check_continuation` (or a small helper it calls) that returns `done` (or routes to escalate) when the last N tool calls repeat the same `tool+args` or yield identical outputs. Optionally have stub/unavailable tools signal `ok=False` / a clear "unavailable" marker so the agent treats them as terminal rather than retryable.

### I2 (High) `outcome: success` reported for an unaccomplished task
- Symptom: `task.completed` shows `outcome: "success"` even though no weather was returned.
- Root cause: outcome reflects clean termination (no exception), not goal satisfaction. The plan emitted `success_conditions: 2` on every `step.planned`, but those conditions are never evaluated against the final answer.
- Proposed fix: evaluate the final answer against the plan `success_conditions` in the evaluate node ([orchestration/react_loop.py](orchestration/react_loop.py)) and set `outcome` to `partial`/`failed` when unmet; emit a quality/eval score so dashboards and evals can distinguish "ran cleanly" from "actually solved it".

### I3 (Medium) Identical tool queries re-dispatch (no caching)
- Symptom: identical query `"Austin Texas weather today"` at step 1 and step 5, both `cached: false`.
- Root cause: `web_search` is registered `cacheable=False` in [StructuredReasoning/cli_pyramid.py](StructuredReasoning/cli_pyramid.py):52; the cache path in `_execute_tool` only engages when `is_cacheable` is true ([orchestration/react_loop.py](orchestration/react_loop.py):166,186).
- Proposed fix: mark `web_search` `cacheable=True` (it is an idempotent read). Note this only de-dupes exact-match queries; the broader thrash is addressed by I1.

## Telemetry / observability

### I4 (Medium) False-positive PII redaction corrupts numeric telemetry
- Symptom: `latency_ms: "1317.[REDACTED]"`, `total_cost_usd: "0.[REDACTED]"` in `metadata.details`, while the parallel `output` keeps full precision (inconsistent and unusable for aggregation).
- Root cause: `redact_details` in [services/governance/black_box_publisher.py](services/governance/black_box_publisher.py):57 applies every PII/API-key regex to every stringified detail value. The credit-card rule `\b(?:\d[ -]*?){13,19}\b` ([services/governance/guardrail_validator.py](services/governance/guardrail_validator.py):177) matches the 13–19 fractional digits of `latency_ms` and `total_cost_usd` floats.
- Proposed fix: exclude known-numeric/safe keys (`latency_ms`, `cost_usd`, `total_cost_usd`, `tokens_in`, `tokens_out`, `step_count`) from regex redaction, and/or round floats before recording. Tightening the credit-card pattern (e.g. disallow a digit immediately following a `.`) is a secondary mitigation.

### I5 (Medium) GENERATION observations carry no native usage/model/cost
- Symptom: `llm.*` and `model.selected` are typed GENERATION but Langfuse cost/latency/token dashboards stay empty; usage lives only inside `step.executed.details`.
- Root cause: `to_export_kwargs` ([services/governance/black_box_publisher.py](services/governance/black_box_publisher.py):82) puts all data into `attributes.details` and promotes no native generation fields (`model`, `usage`, `cost`, `input`, `output`).
- Proposed fix: for MODEL_SELECTED (and the `llm.*` relay events) promote `model`, token usage, and cost to native Langfuse generation fields so built-in cost/latency views populate.

### I6 (Medium) Flat trace: every observation at depth 0
- Symptom: no tree; run, steps, generations, tools, guardrails are all siblings.
- Root cause: `to_export_kwargs` sets no `parent_observation_id`; there is no run/step span nesting.
- Proposed fix: introduce a parent hierarchy (task span as root, a per-step span as parent of that step's generation/tool/guardrail events) and thread `parent_observation_id` through the export kwargs.

### I7 (Low) `model.selected` has `step: null`
- Symptom: every `model.selected` event reports `step: null`, breaking step-keyed joins for routing analysis.
- Root cause: the MODEL_SELECTED `TraceEvent` is recorded without a `step` (attributes copy `event.step` verbatim in [services/governance/black_box_publisher.py](services/governance/black_box_publisher.py):100).
- Proposed fix: pass `step=state.get("step_count", 0)` when recording MODEL_SELECTED in [orchestration/react_loop.py](orchestration/react_loop.py).

### I8 (Low) Zero-duration point spans, out-of-order emission
- Symptom: `startTime ≈ endTime` on all spans; `step.executed` events occasionally arrive out of order (step 9 before step 8) near the end.
- Root cause: events are emitted as instantaneous markers (true latency only in `details.latency_ms`) and flushed asynchronously.
- Proposed fix (optional / defer): emit real start/end around the wrapped operation so spans carry duration; out-of-order emission is cosmetic given timestamps and can be left as-is.

## Notes
- Healthy and intentionally unchanged: `trace_id` propagates verbatim end-to-end, `subject` propagation, `integrity_hash` on governance events, guardrails (`agent_facts`, `prompt_injection`), and routing policy (gpt-4o planning step 0 then gpt-4o-mini steady state).
- Deliverable of this plan is the register above. Fixes I1–I8 can be implemented in follow-up changes. I1 and I3 are also covered by the SearXNG plan ([docs/plans/searxng_real_web_search.plan.md](docs/plans/searxng_real_web_search.plan.md)).
