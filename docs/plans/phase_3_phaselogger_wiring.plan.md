---
name: Phase 3 PhaseLogger Wiring
overview: "Wire the PhaseLogger (Reasoning pillar) into the ReAct loop. Detailed implementation doc for phase3a/3b/3c of the master plan (.cursor/plans/governance_pipeline_enhancements_3c04ef92.plan.md). Scope: (1) persist phase boundaries to a NEW phases.jsonl (decisions.jsonl untouched, so DecisionRecord consumers are unaffected); (2) per-step _phase_starts keying so repeated loop phases do not collide; (3) a PhaseTracker context manager so every node's early-return path is balanced; (4) decision_id (uuid4 + injectable factory, signed off) threaded into MODEL_SELECTED for cross-pillar joins; (5) fix the Langfuse relay to publish phase records + extend redaction; (6) add a phase_events[] bundle field + phase_log_schema_version. ReAct loop only; Pyramid loop parity deferred to Phase 3b."
todos:
  - id: b0-schema-gate
    content: "Schema gate (BLOCKS B1): split-file layout (NEW phases.jsonl, decisions.jsonl unchanged); export_workflow_log() stays decisions-only; add export_phase_events(); add bundle['phase_events'] separate from bundle['phase_decisions']; introduce phase_log_schema_version='1' (do NOT bump BUNDLE_SCHEMA_VERSION='2'). DoD: design note committed in this doc; DecisionRecord/Zod baseline untouched."
    status: completed
  - id: c0-failure-tests
    content: "TDD red phase (before B1): extend tests/services/test_governance.py::TestPhaseLogger with failure-path tests. Cases: end_phase without start_phase (warn, no crash), per-step key isolation, JSONL IO error, COMPLETION without start, mixed export ordering. Use freezegun for duration. DoD: tests written and failing for the un-implemented behavior."
    status: completed
  - id: b1-impl
    content: "B1 PhaseLogger persistence: start_phase/end_phase gain step_count; make end_phase 'details' optional (default None); _phase_starts keyed f'{workflow_id}:{step_count}:{phase.value}'; write phases.jsonl with duration_ms; add decision_id_factory ctor param; add export_phase_events(); add PhaseTracker async context manager (async with phase_logger.phase(...)) guaranteeing end_phase on exception (outcome='error'). export_workflow_log() unchanged. DoD: c0 + c1 green; stdlib+Pydantic only."
    status: completed
  - id: b2-decision-id
    content: "B2 (signed off): add decision_id: str | None = None (lazy) to Decision model + ensure_decision_id() that assigns from the instance-scoped decision_id_factory (NOT a Pydantic default_factory, which cannot reach instance state); thread decision.decision_id into MODEL_SELECTED event details at react_loop.py:763. Scope: MODEL_SELECTED only (ROUTING/EVALUATION cross-ref deferred; EVALUATION has no paired BlackBox event today). DoD: decision_id present + unique; appears in both decisions.jsonl row and MODEL_SELECTED event."
    status: completed
  - id: b3-wire
    content: "B3 wiring via PhaseTracker (1 line per node, AP-5 holds): INITIALIZATION+INPUT_VALIDATION (sequential) in guard_input_node with outcome='rejected' on agent-facts/guardrail rejection; ROUTING in route_node (handle budget-exceeded); OUTPUT_VALIDATION in call_llm_node via CM, MODEL_INVOCATION via manual start_phase/end_phase (LLM error is recorded + outcome='error' but NOT re-raised, so the node continues — a CM would re-raise and break recovery); TOOL_EXECUTION at execute_tool_node (pass phase_logger into _execute_tools_impl); EVALUATION in evaluate_node; COMPLETION from every TASK_COMPLETED site (guard_input reject, route budget, evaluate done) with single-flight guard; verify_authorize_log_node denial emits TOOL_EXECUTION outcome='denied'. DoD: c2 green."
    status: completed
  - id: b3-relay
    content: "Relay fix (signed off): update middleware/sidecars/black_box_to_telemetry.py:284 to build a PhaseLogger from the phase_logs dir and pass phase_logger=... into export_for_compliance(); extend redact_compliance_bundle (black_box_publisher.py:112-138) to walk bundle['phase_events'] (and any free-text in phase records). DoD: tests/middleware/sidecars/test_compliance_dataset.py asserts published bundle contains redacted phase_events[]."
    status: completed
  - id: c1-impl-tests
    content: "C1 green phase: implementation tests for B1 (start/end write phases.jsonl with step_count + duration_ms>=0; PhaseTracker records outcome='error' on exception and re-raises; same phase at step 0 and step 1 are independent; injected decision_id_factory yields deterministic ids). Extends tests/services/test_governance.py."
    status: completed
  - id: c2-integration
    content: "C2 integration: extend tests/services/test_explainability_service.py (or new tests/orchestration/test_phase_wiring.py). Mocked multi-step ReAct loop asserts: all wired phases at expected step_counts; COMPLETION on all 3 terminal paths (reject/budget/done) exactly once; decision_id matches between Decision row and MODEL_SELECTED event; bundle exposes phase_events[] + phase_log_schema_version='1' while phase_decisions[] keeps DecisionRecord shape; redaction does not leak in phase_events[]."
    status: completed
  - id: c3-property
    content: "Property-based (Hypothesis) test for decision_id uniqueness across many decisions in one workflow. Lives in tests/services/test_governance.py (TestDecisionIdUniqueness)."
    status: completed
  - id: c4-schema-version
    content: "Extend Recipe 13 TestBundleSchemaVersion: assert phase_log_schema_version='1' present + stable; assert BUNDLE_SCHEMA_VERSION still '2' (no consumer break)."
    status: completed
  - id: c5-regression
    content: "Full regression: pytest tests/architecture/ -q AND pytest tests/ -q (AGENTS.md mandate). All pass before merge."
    status: completed
  - id: d1-blackbox-doc
    content: "Update governanaceTriangle/05_black_box_explanation.md: note PhaseLogger phase boundaries now persisted + joined in the compliance bundle (phase_events[]); reference this plan. Add a short G/I/R/P label legend (labels are plan-internal, undefined in the triangle docs today)."
    status: completed
  - id: d2-phaselogger-doc
    content: "Update governanaceTriangle/06_phase_logger_deep_dive.md: add a 'Production Implementation Status' matrix mapping the doc's models/methods to the ~89-line production phase_logger.py; mark implemented (start_phase/end_phase/log_decision JSONL, decision_id, duration, PhaseTracker, export_phase_events) vs deferred (Artifact, PhaseOutcome, PhaseSummary, visualize_workflow). Replace fictional line refs."
    status: completed
  - id: d3-recording-doc
    content: "Update governanaceTriangle/02_black_box_recording_debugging.md: note phase boundary recording landed and that the relay now publishes redacted phase_events[]. Link R1/R3 (still open) to master plan todo ids phase2a-tool-called-enrich / phase2b-error-enrich."
    status: completed
  - id: e1-pyramid-followup
    content: "Phase 3b placeholder (deferred, out of scope): wire PhaseTracker into StructuredReasoning/orchestration/pyramid_loop.py for parity. Tracked here so it is not lost."
    status: pending
isProject: false
---

# Phase 3: PhaseLogger Wiring

> **Sprint board:** dependency-ordered stories and status trackers live in [phase_3_phaselogger_sprint_board.md](phase_3_phaselogger_sprint_board.md).
>
> **Master plan:** this doc is the detailed implementation spec for `phase3a-persist-phases` (P2), `phase3b-wire-phases` (P1), `phase3c-decision-id` (P4) in
> [.cursor/plans/governance_pipeline_enhancements_3c04ef92.plan.md](../../.cursor/plans/governance_pipeline_enhancements_3c04ef92.plan.md).
> Housekeeping (G-item status sync, stale-docstring fix) is **out of scope here** — it is the master plan's `ops-plan-update` todo, and the G-item statuses already live in `governance_pipeline_enhancements...` lines 60-78 and in [docs/plans/trace_gap_closure.plan.md](trace_gap_closure.plan.md) (G4/G5/G6/G7/G8/G9 = `completed`; G2 code todos + G3 still `pending`).

## Current State Assessment (verified against code 2026-06-01)

**[services/governance/phase_logger.py](../../services/governance/phase_logger.py)** — ~89 lines, NOT the rich API the deep-dive doc describes:

- `WorkflowPhase` enum (line 20) has **9** values including unused `CONTINUATION` (line 27).
- `start_phase(workflow_id, phase)` (line 44) — **log-only**; no `_phase_starts` tracker, no JSONL write.
- `end_phase(workflow_id, phase, outcome, details)` (line 66) — **log-only**; `details` is a **required** positional arg, currently unused; no duration, no JSONL write.
- `log_decision(workflow_id, decision)` (line 47) — the only method that persists; writes `cache/phase_logs/{workflow_id}/decisions.jsonl`.
- `Decision` model (lines 32-37): `phase, description, alternatives, rationale, confidence` — **no `decision_id`**.
- `export_workflow_log(workflow_id)` (line 80) — raw `json.loads` of `decisions.jsonl`, no filtering.

**[orchestration/react_loop.py](../../orchestration/react_loop.py)**:

- `PhaseLogger` instantiated (line 416). **Zero** `start_phase`/`end_phase` calls.
- `log_decision` called only in `route_node` (line 708) and `evaluate_node` (line 1101).
- Graph loops `evaluate → route → call_llm → ...` (lines 1342-1345) — ROUTING/MODEL_INVOCATION/EVALUATION repeat per step (motivates per-step keying).
- Terminal `TASK_COMPLETED` emits from **three** sites: guard_input rejection, route budget-exceeded, evaluate done (motivates the COMPLETION single-flight guard).

**Consumer plumbing (the breakage risk)**:

- [black_box.py](../../services/governance/black_box.py) `export_for_compliance(workflow_id, agent_facts_registry=None, phase_logger=None)` (line 184) assigns `bundle["phase_decisions"] = phase_logger.export_workflow_log(workflow_id)` (line 223).
- `ExplainabilityService.get_compliance_bundle` (explainability_service.py:924-938) constructs a `PhaseLogger` and **passes it**, then validates each `phase_decisions` row as a `DecisionRecord` — invalid rows are logged and **silently skipped**. → Mixing phase events into `export_workflow_log()` would drop them. **This is why phase events get a separate file + bundle field.**
- `BUNDLE_SCHEMA_VERSION = "2"` (black_box.py:25). `export()`/`replay()` are **implemented** (lines 86-158) despite the stale line-4 docstring (fixed by the master plan's `ops-plan-update`, not here).

**Relay (verified gap)**: [middleware/sidecars/black_box_to_telemetry.py](../../middleware/sidecars/black_box_to_telemetry.py) line 284 calls `recorder.export_for_compliance(workflow_id)` with **no** `phase_logger` and **no** `agent_facts_registry`. Published Langfuse dataset items therefore contain neither phase records nor identity cards today.

**Redaction (verified gap)**: `redact_compliance_bundle` (black_box_publisher.py:112-124) only walks `bundle["events"]`. It does not touch `phase_decisions`/`phase_events`. Fixing the relay without extending redaction would introduce a fresh leak.

**Existing tests**: `tests/services/test_governance.py` (`TestPhaseLogger`, `TestDecisionRationale`). **Extend this module — do not create `tests/services/governance/test_phase_logger.py`.**

---

## Part B: Code

### B0. Schema gate (BLOCKS B1)

- **Files:** phase boundaries → NEW `cache/phase_logs/{workflow_id}/phases.jsonl`. `decisions.jsonl` unchanged.
- **Methods:** `export_workflow_log()` stays decisions-only (preserves `phase_decisions` consumers). New `export_phase_events(workflow_id)` reads `phases.jsonl`.
- **Bundle:** `export_for_compliance` gains `bundle["phase_events"] = phase_logger.export_phase_events(workflow_id)` — separate from `bundle["phase_decisions"]`.
- **Versioning:** add `bundle["phase_log_schema_version"] = "1"`. Do **not** bump `BUNDLE_SCHEMA_VERSION` (DecisionRecord shape unchanged).
- **phases.jsonl record:** `{ "event": "phase_start"|"phase_end", "workflow_id", "step_count", "phase", "outcome"?, "duration_ms"?, "timestamp" }`.

### B1. PhaseLogger persistence + PhaseTracker

File: [services/governance/phase_logger.py](../../services/governance/phase_logger.py)

- `__init__` gains `_phase_starts: dict[str, datetime]` and `decision_id_factory: Callable[[], str] = lambda: str(uuid.uuid4())`.
- `start_phase(workflow_id, phase, step_count)`: record start time under key `f"{workflow_id}:{step_count}:{phase.value}"`; write `phases.jsonl` row.
- `end_phase(workflow_id, phase, outcome, step_count, details=None)`: **make `details` optional**; compute `duration_ms`; write `phases.jsonl`; pop the start key; warn (no crash) if no matching start.
- `phase(phase, workflow_id, step_count)` async context manager — guarantees `end_phase` even on exception (records `outcome="error"`, re-raises).
- `export_phase_events(workflow_id)` reads `phases.jsonl`.
- Stays stdlib + Pydantic + typing only.

### B2. `decision_id` (signed off — uuid4 + factory)

- Add `decision_id: str | None = None` to `Decision` (lazy, not a Pydantic `Field(default_factory=...)`). A `PhaseLogger.ensure_decision_id(decision)` method assigns the id from the **instance-scoped** `decision_id_factory` when unset. **Why not `default_factory`?** A class-level `default_factory` cannot reach the per-instance, injectable factory — making it instance-scoped is what keeps replay/goldens deterministic. `log_decision()` calls `ensure_decision_id()` so callers never see a null id in a persisted row.
- Thread `decision.decision_id` into the `MODEL_SELECTED` `TraceEvent.details` at `react_loop.py:763`.
- **Scope:** MODEL_SELECTED only. ROUTING/EVALUATION cross-ref deferred — EVALUATION has no paired BlackBox event today; adding one is scope creep tracked separately.

### B3. Wire PhaseTracker into ReAct loop nodes

File: [orchestration/react_loop.py](../../orchestration/react_loop.py) — one-line `async with phase_logger.phase(...)` per boundary; AP-5 holds; early returns auto-balanced.

| Node | Phase(s) | Notes |
|---|---|---|
| `guard_input_node` (446) | `INITIALIZATION` then `INPUT_VALIDATION` (sequential) | agent-facts/guardrail reject → `outcome="rejected"`; emit COMPLETION before terminal return |
| `route_node` (573) | `ROUTING` | budget-exceeded → `outcome="budget_exceeded"`; emit COMPLETION |
| `call_llm_node` (749) | `MODEL_INVOCATION` then `OUTPUT_VALIDATION` | MODEL_INVOCATION uses **manual** `start_phase`/`end_phase` (the node catches the LLM exception, records `ERROR_OCCURRED`, sets `outcome="error"`, and continues — it does **not** re-raise, so a CM would be wrong here). OUTPUT_VALIDATION uses the CM. |
| `execute_tool_node` (925) / `_execute_tools_impl` (128) | `TOOL_EXECUTION` | pass `phase_logger` into `_execute_tools_impl` |
| `verify_authorize_log_node` (~1007) | `TOOL_EXECUTION` (denied) | denial → `outcome="denied"`, no tool runs |
| `evaluate_node` (1022) | `EVALUATION` | `continuation=="done"` → emit COMPLETION |

**COMPLETION single-flight guard:** COMPLETION fires from 3 sites; guard per `workflow_id` so it emits exactly once. `step_count` read from existing graph state.

### B3-relay. Relay + redaction (signed off — in scope)

- `black_box_to_telemetry.py:284`: build a `PhaseLogger` from the phase-logs dir and pass `phase_logger=...` into `export_for_compliance(workflow_id)`.
- Extend `redact_compliance_bundle` (black_box_publisher.py:112-124) to walk `bundle["phase_events"]` (and redact any free-text in phase records) with the same rules as `events[].details`.

---

## Part C: Tests (TDD — failure paths first)

- **C0 (red):** failure-path tests in `tests/services/test_governance.py::TestPhaseLogger` — `end_phase` without start (warn/no-crash), per-step key isolation, JSONL IO error, COMPLETION without start, mixed export ordering. `freezegun` for duration (not `time.sleep`, per AGENTS.md L2).
- **C1 (green):** B1 implementation tests — phases.jsonl shape, `duration_ms>=0`, PhaseTracker `outcome="error"` on exception, step-0/step-1 independence, injected deterministic factory.
- **C2 (integration):** multi-step mocked loop — all wired phases at expected step_counts; COMPLETION once on reject/budget/done; `decision_id` match (Decision row ↔ MODEL_SELECTED); `phase_events[]` + `phase_log_schema_version="1"` present, `phase_decisions[]` shape unchanged; redaction clean. Extend `tests/middleware/sidecars/test_compliance_dataset.py` for relay-published phase_events[].
- **C3 (property):** Hypothesis `decision_id` uniqueness.
- **C4:** extend Recipe 13 `TestBundleSchemaVersion` for `phase_log_schema_version` + unchanged `BUNDLE_SCHEMA_VERSION`.
- **C5:** `pytest tests/architecture/ -q` AND `pytest tests/ -q`.

---

## Part D: Governance Triangle Doc Updates

- **D1** [05_black_box_explanation.md](../../governanaceTriangle/05_black_box_explanation.md) — phase boundaries now persisted + joined via `phase_events[]`; add G/I/R/P label legend.
- **D2** [06_phase_logger_deep_dive.md](../../governanaceTriangle/06_phase_logger_deep_dive.md) — Production Implementation Status matrix (production vs aspirational); replace fictional line refs; mark deferred features.
- **D3** [02_black_box_recording_debugging.md](../../governanaceTriangle/02_black_box_recording_debugging.md) — phase recording landed + relay publishes redacted `phase_events[]`; link R1/R3 to master plan `phase2a`/`phase2b`.

---

## Part E: Deferred

- **e1 Pyramid loop parity** — wire PhaseTracker into `StructuredReasoning/orchestration/pyramid_loop.py`. Out of scope for Phase 3.

---

## Open Risks & Trade-offs

- **Split files vs discriminated union:** split chosen to avoid touching `DecisionRecord`/Zod baseline/`phase_decisions` consumers (verified: ExplainabilityService validates each row). Cost: a second file + a second export method.
- **`phase_log_schema_version` separate** from `BUNDLE_SCHEMA_VERSION` so phase-event evolution doesn't force unrelated consumer bumps.
- **Per-step JSONL keying** is verbose (≤9 phases × N steps × M workflows) — flag log rotation as a follow-up; bounded by cache TTL today.
- **`uuid4` `decision_id`** is non-deterministic — replay/goldens must inject `decision_id_factory`. Documented limitation.
- **Hot-path cost:** `datetime.now()` + append per boundary — sub-ms, flagged.
- **COMPLETION from 3 sites** risks duplicates — mitigated by single-flight guard.
- **`_completion_emitted` is an unbounded in-memory `set[str]`** (one entry per `workflow_id`, closure-scoped to a `build_graph()` call). Harmless for the CLI (one workflow per process), but a long-lived server reusing one graph object accumulates entries indefinitely. Follow-up: evict on COMPLETION or bound with an LRU/TTL when the graph is shared across many workflows.
- **Relay now publishes phase records** — redaction MUST be extended in the same change (b3-relay) or PII leaks via `phase_events[]`.

---

## Validation Sequence

1. `pytest tests/services/test_governance.py -q` (C0/C1/C3)
2. `pytest tests/services/ tests/orchestration/ -q` (C2)
3. `pytest tests/middleware/ -q` (relay regression)
4. `pytest tests/architecture/ -q`
5. `pytest tests/ -q` (full regression — AGENTS.md mandate)
6. CLI positive: `python -m agent.cli "What is 2+2?"`; inspect `cache/phase_logs/{workflow_id}/phases.jsonl` for INITIALIZATION/INPUT_VALIDATION/ROUTING/MODEL_INVOCATION/OUTPUT_VALIDATION/EVALUATION/COMPLETION (+ TOOL_EXECUTION if a tool ran).
7. CLI negative (Recipe 13 scenarios): guardrail reject, agent-facts fail, tool error — COMPLETION fires once from the correct site with correct `outcome`.
8. Verify `export_for_compliance()` bundle has `phase_events[]` + `phase_log_schema_version="1"`; `phase_decisions[]` unchanged.
9. Verify Langfuse-published dataset item (relay) contains redacted `phase_events[]`.

---

## Architecture Constraints

- Dependencies flow downward only.
- Orchestration nodes use ONLY `async with phase_logger.phase(...)` — AP-5 holds, no domain logic.
- `PhaseLogger` stays stdlib + Pydantic + typing — `decision_id_factory: Callable[[], str]` introduces no framework import.
- `DecisionRecord` shape preserved (no Zod baseline change).
- `decision_id` on `Decision` is an AGENTS.md "Ask first" change — **signed off**.
