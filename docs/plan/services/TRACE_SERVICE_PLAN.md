# TRACE_SERVICE_PLAN.md — `services/trace_service.py` Implementation Plan

> **Status**: design sub-plan for sprint S1 of [AGENT_UI_ADAPTER_SPRINTS.md](../adapter/sprints/AGENT_UI_ADAPTER_SPRINTS.md). One of three Phase 1 pre-work services per [AGENT_UI_ADAPTER_PLAN.md](../adapter/AGENT_UI_ADAPTER_PLAN.md) §11.
>
> **TDD Protocol**: B (Contract-driven) per [research/tdd_agentic_systems_prompt.md](../../../research/tdd_agentic_systems_prompt.md) §Protocol B. L2 reproducible, <30s test budget.
>
> **Boundary**: horizontal service per [AGENTS.md](../../../AGENTS.md). No domain logic. No imports from `components/`, `orchestration/`, or other `services/*`. Receives data as parameters.

---

## 1. Purpose & Boundaries

### 1.1 What it does

A horizontal **emit + route** service for `TrustTraceRecord` events. Accepts a record from any orchestration node, validates it, and routes it to one or more configured sinks (in-memory list, JSONL file, OpenTelemetry exporter, etc.).

### 1.2 What it does NOT do

- **Does not generate trace records** — that's the caller's job
- **Does not own correlation IDs** — `trace_id` arrives in the record
- **Does not query traces** — read-side is a separate concern (Langfuse/Phoenix UI)
- **Does not import from other services** ([AGENTS.md](../../../AGENTS.md) AP-2)
- **Does not import from `components/` or `orchestration/`** ([AGENTS.md](../../../AGENTS.md) invariants 6, 7)
- **Does not catch and swallow sink errors silently** — failure isolation per-sink, but the failure is logged

### 1.3 Why it exists

[docs/Architectures/FOUR_LAYER_ARCHITECTURE.md](../../Architectures/FOUR_LAYER_ARCHITECTURE.md) lines 471–478 mandate one trace sink for all layers. Without it, every layer would invent its own sink (`black_box.py`, `phase_logger.py`, `eval_capture.py` already do). This service unifies the dispatch.

---

## 2. Public Interface

```python
# services/trace_service.py

from typing import Protocol, runtime_checkable
from trust.models import TrustTraceRecord

@runtime_checkable
class TraceSink(Protocol):
    """Single-method sink. Implement for any backend (file, stdout, OTLP, Langfuse)."""
    def emit(self, record: TrustTraceRecord) -> None: ...


class TraceService:
    def __init__(self, sinks: list[TraceSink]) -> None:
        """Sinks are passed by the composition root, never imported by name."""
        ...

    def emit(self, record: TrustTraceRecord) -> None:
        """Validate the record, fan out to all sinks. Per-sink failures are isolated."""
        ...

    def add_sink(self, sink: TraceSink) -> None:
        """Late binding for tests; production wires sinks at construction."""
        ...
```

### 2.1 Built-in sinks (in same file)

- `InMemoryTraceSink` — `records: list[TrustTraceRecord]`. For tests.
- `JsonlFileTraceSink(path: Path)` — appends one JSON object per line.
- `LoggingTraceSink(logger_name: str = "trust.trace")` — emits via stdlib logging at INFO.

External sinks (Langfuse, OTLP, Phoenix) live in `services/observability/` or are wired in by the composition root via the `TraceSink` Protocol.

---

## 3. Test Plan (failure paths first)

Per Protocol B contract-driven TDD. Test file: `tests/services/test_trace_service.py`.

### 3.1 Failure path tests (write FIRST)

- `test_emit_rejects_non_trace_record_payload` — passing a dict (not a `TrustTraceRecord`) raises `TypeError` BEFORE any sink is invoked
- `test_emit_isolates_sink_failures` — given two sinks where the first raises `RuntimeError`, the second still receives the record (failure isolation)
- `test_emit_logs_sink_failures` — sink failure produces a log line at ERROR with sink name + exception (use `caplog`)
- `test_emit_rejects_none` — `service.emit(None)` raises `TypeError`
- `test_jsonl_sink_handles_unwritable_path` — `JsonlFileTraceSink(Path("/no/such/dir/x.jsonl"))` raises `OSError` on first emit; service still calls other sinks

### 3.2 Acceptance path tests

- `test_emit_fans_out_to_all_sinks` — 3 sinks all receive the same record bytewise-identical
- `test_inmemory_sink_records_in_order` — emit 3 records, list contains them in order
- `test_jsonl_sink_writes_one_record_per_line` — emit 2, file has 2 lines, each parses back to a `TrustTraceRecord`
- `test_jsonl_sink_round_trips_unicode` — emit record with unicode `details`, file content round-trips
- `test_no_dedup_at_service_layer` — two emits with same `trace_id` and `event_id` both reach the sink (dedup is a downstream concern)
- `test_add_sink_late_binding` — service constructed empty, `add_sink()` called, subsequent emits reach the new sink

### 3.3 Property-based test (Hypothesis, marked `@pytest.mark.property`)

- `test_emit_preserves_record_bytewise` — Hypothesis generates valid `TrustTraceRecord` instances; for each, `InMemoryTraceSink` receives a record whose `model_dump_json()` equals the input's

### 3.4 Architecture-level test (in `tests/architecture/`)

- `test_trace_service_does_not_import_other_services` — AST scan of `services/trace_service.py`; assert no imports from `services.*` other than itself or `services.base_config` (AP-2 enforcement)

### 3.5 Test budget

L2 budget: full file <30s. Failure tests dominate (5 fail-first vs 6 acceptance vs 1 property), enforcing TDD §AP-4 (failure paths first).

---

## 4. Logging

Add to [logging.json](../../../logging.json):

```json
"trust.trace": {
  "handlers": ["console", "trace_file"],
  "level": "INFO",
  "propagate": false
},
"trace_file": {
  "class": "logging.handlers.RotatingFileHandler",
  "filename": "logs/trust_trace.log",
  "maxBytes": 10485760,
  "backupCount": 5,
  "formatter": "json"
}
```

Per H4 ([AGENTS.md](../../../AGENTS.md)): own log file, own logger name.

---

## 5. Dependencies

- **Internal**: `trust.models.TrustTraceRecord` only. NO imports from other `services/*`.
- **External**: stdlib only (`json`, `logging`, `pathlib`, `typing`). Pydantic comes via `trust/`.
- **Test deps**: `pytest`, `hypothesis` (already in `pyproject.toml [dev]`), `caplog` (pytest builtin).

NO new `pyproject.toml` dependencies.

---

## 6. Open Questions / Deferred

- **Q-T1**: OTLP exporter — defer to v1.5; in v1 the `LoggingTraceSink` covers stdout/file scenarios.
- **Q-T2**: Async emit — defer; sinks are sync. Async sinks can be added later via a new `AsyncTraceSink` Protocol; the existing `TraceService` keeps its sync API (composition root chooses).
- **Q-T3**: Sampling — out of scope for v1. If volume becomes a concern, add a `SamplingSink` decorator.
- **Q-T4**: Backpressure — if a sink is slow and synchronous, the caller will block. Acceptable for v1; revisit when async sinks land.

---

## 7. Acceptance Sign-Off

S1 sprint considers US-1.1 done when:

- All 12 tests in §3 are green
- Architecture test §3.4 is green
- `tests/services/test_trace_service.py` runs in <5s
- `logging.json` updated and validated by an existing logging-config test (or a new one)
- The traceability row in [AGENT_UI_ADAPTER_SPRINTS.md](../adapter/sprints/AGENT_UI_ADAPTER_SPRINTS.md) §5 for US-1.1 is updated with the commit SHA
