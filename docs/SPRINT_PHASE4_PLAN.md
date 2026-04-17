# Phase 4 Sprint Plan: Meta-Optimization and Fallback Evaluation

**Sprint ID:** `SPRINT-P4`
**Plan Reference:** `PLAN_v2`
**Generated:** 2026-04-17
**Method:** Pyramid Principle MECE decomposition per `research/pyramid_react_system_prompt.md`, story format per `prompts/SprintPlanning/sprint_story_agent_system.md`

---

## Governing Thought

Phase 4 delivers **automated self-improvement and architecture validation** by completing four MECE workstreams: (1) a meta-optimizer that tunes routing thresholds from logged data, (2) production drift detection across three levels, (3) a CodeReviewer agent that produces structured `ReviewReport` output, and (4) a LangGraph feasibility gate that decides whether to keep or replace the framework. All four share a common dependency on the existing `meta/analysis.py` analytics engine and operate under the constraint that meta-layer code must never import from orchestration.

---

## MECE Issue Tree

```
Root: What must Phase 4 deliver?
│
├── WS-1: Meta-Optimizer (automated threshold tuning)
│   ├── 1a: Benchmark runner (execute tasks with proposed configs)
│   ├── 1b: Config mutation engine (propose RoutingConfig candidates)
│   └── 1c: Comparison & selection (baseline vs candidate scoring)
│
├── WS-2: Drift Detection (three-level monitoring)
│   ├── 2a: Level 1 — Performance drift (weekly, 2-sigma)  [EXISTS]
│   ├── 2b: Level 2 — Judge calibration drift (monthly, kappa)  [EXISTS]
│   ├── 2c: Level 3 — Governance artifact drift (AgentFacts)  [EXISTS]
│   └── 2d: CLI / scheduling entrypoint + alerting integration
│
├── WS-3: CodeReviewer Agent (structured architecture validation)
│   ├── 3a: Agent class + LLM integration (produces ReviewReport)
│   ├── 3b: Prompt wiring (system + rules + submission templates)
│   └── 3c: CLI entrypoint + eval_capture recording
│
└── WS-4: LangGraph Feasibility Gate (keep-or-replace decision)
    ├── 4a: Instrumentation (checkpointing usage counters, rollback tracking)
    ├── 4b: Decision criteria collector + report generator
    └── 4c: Pydantic AI fallback prototype (if gate fails)
```

### MECE Validation

| Test | Result | Details |
|------|--------|---------|
| Completeness | Pass | All 4.1–4.5 PLAN_v2 goals covered |
| Non-overlap | Pass | Optimizer (tunes thresholds) ≠ Drift (monitors) ≠ CodeReviewer (validates code) ≠ Feasibility (framework decision) |
| Item placement | Pass | `meta/optimizer.py` → WS-1 only; `meta/drift.py` → WS-2 only; CodeReviewer prompts → WS-3 only |
| Boundary | Pass | Analytics engine (`meta/analysis.py`) is a shared dependency consumed by WS-1 and WS-2, not owned by either |

---

## Dependency Graph

```
                    ┌──────────────┐
                    │   WS-4       │  (Feasibility Gate)
                    │ Instrumentation│
                    └──────┬───────┘
                           │ reads metrics from
                           ▼
    ┌──────────┐    ┌──────────────┐    ┌──────────────┐
    │  WS-3    │    │   WS-1       │    │   WS-2       │
    │CodeReview│    │Meta-Optimizer │    │Drift Detection│
    └──────────┘    └──────┬───────┘    └──────┬───────┘
                           │                    │
                           ▼                    ▼
                    ┌──────────────────────────────────┐
                    │  meta/analysis.py (EXISTS)        │
                    │  AgentMetrics, load_eval_records   │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────┴───────────────────┐
                    │  components/routing_config.py     │
                    │  components/schemas.py (EvalRecord)│
                    │  services/ (eval_capture, etc.)   │
                    │  trust/review_schema.py           │
                    └──────────────────────────────────┘
```

**Key interaction points:**
- WS-1 reads metrics from `meta/analysis.py`, writes tuned values to `components/routing_config.py`
- WS-2 reads metrics from `meta/analysis.py`, reads agent facts from `services/governance/agent_facts_registry.py`
- WS-3 reads file ASTs/diffs, produces `trust/review_schema.ReviewReport`
- WS-4 reads instrumentation counters collected by WS-1 and orchestration-layer telemetry

---

## Sprint Themes

### Theme 1: Automated Self-Tuning — `THEME-P4-OPTIMIZE`
**Phase:** 4 | **Stories:** STORY-401, STORY-402, STORY-403, STORY-404
**Summary:** Build the meta-optimizer that reads logged metrics, proposes RoutingConfig candidates, runs benchmark tasks, and selects the best config. Closes the feedback loop between production execution and routing thresholds.

### Theme 2: Production Drift Monitoring — `THEME-P4-DRIFT`
**Phase:** 4 | **Stories:** STORY-405, STORY-406, STORY-407
**Summary:** Extend the existing three-level drift detection with a CLI entrypoint, alerting integration, and scheduled execution. The core algorithms exist; this theme wires them into an operable pipeline.

### Theme 3: Architecture Validation Agent — `THEME-P4-CODEREVIEW`
**Phase:** 4 | **Stories:** STORY-408, STORY-409, STORY-410, STORY-411
**Summary:** Build the CodeReviewer agent that consumes file diffs, runs them against architecture rules via LLM, and produces a structured `ReviewReport` with dimension-by-dimension findings and certificates.

### Theme 4: Framework Feasibility Gate — `THEME-P4-FEASIBILITY`
**Phase:** 4 | **Stories:** STORY-412, STORY-413, STORY-414
**Summary:** Instrument checkpointing and rollback usage, collect feasibility metrics, produce a go/no-go decision report, and prototype the Pydantic AI fallback path.

---

## Stories

---

### STORY-401: Analytics Engine Enhancement for Optimizer Input

| Field | Value |
|-------|-------|
| **id** | `STORY-401` |
| **title** | Extend `meta/analysis.py` to compute optimizer-grade metrics |
| **phase** | 4 |
| **layers** | `meta` |
| **modules_touched** | `meta/analysis.py`, `components/schemas.py` |
| **dependencies** | — (existing module; enhancement) |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | `eval_capture` target: `meta_analysis` |
| **style_violations_to_avoid** | `AP8` (meta must not import orchestration), `DEP.no_upward_to_orch` |

**Acceptance Criteria:**
- `compute_metrics()` returns `failure_rate_before_escalation` computed as (tasks that failed at fast tier before escalation to capable tier) / (total tasks routed to fast tier)
- `compute_metrics()` returns per-config-field sensitivity data: for each `RoutingConfig` field, the marginal impact on success_rate when the value changes by ±1 unit
- New `OptimizerInput` Pydantic model wraps `AgentMetrics` + config snapshot + golden-set scores
- All new fields have L2 tests with fixture JSONL data
- Zero imports from `orchestration/`

**Test Obligations:**
- Failure path: empty JSONL → returns zero-value `OptimizerInput`
- Failure path: corrupted JSONL lines → skipped with warning logged
- Contract test: `OptimizerInput` serialization roundtrip
- Marker: none (L2, runs in CI)

---

### STORY-402: Meta-Optimizer Core — Config Mutation and Candidate Proposal

| Field | Value |
|-------|-------|
| **id** | `STORY-402` |
| **title** | Build `meta/optimizer.py` — propose RoutingConfig candidates |
| **phase** | 4 |
| **layers** | `meta`, `vertical` |
| **modules_touched** | `meta/optimizer.py` (new), `components/routing_config.py` |
| **dependencies** | `STORY-401` |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | `eval_capture` target: `optimizer_proposal`, `PhaseLogger` for config change decisions |
| **style_violations_to_avoid** | `AP8`, `M2`, `DEP.no_upward_to_orch`, `AP5` |

**Acceptance Criteria:**
- `ConfigMutator.propose(current_config: RoutingConfig, metrics: OptimizerInput) -> list[RoutingConfig]` generates 3-5 candidate configs by perturbing one field at a time
- Perturbation bounds are configurable via `OptimizationSettings` Pydantic model (e.g., `escalate_after_failures` range 1-5, `budget_downgrade_threshold` range 0.5-1.0)
- Each candidate is a valid `RoutingConfig` instance (Pydantic validation enforced)
- `meta/optimizer.py` imports only from `components/routing_config` (vertical, allowed) and `meta/analysis` (same package). Zero imports from `orchestration/`, `services/`, or `trust/`
- Config mutation is deterministic given a seed (for reproducible benchmarks)

**Test Obligations:**
- Property-based test (Hypothesis): all proposed configs pass `RoutingConfig` validation
- Failure path: metrics with zero tasks → returns current config unchanged
- Determinism test: same seed → same candidates
- Marker: `@pytest.mark.property` for Hypothesis tests

---

### STORY-403: Benchmark Runner — Execute Tasks with Candidate Configs

| Field | Value |
|-------|-------|
| **id** | `STORY-403` |
| **title** | Build benchmark runner for optimizer evaluation |
| **phase** | 4 |
| **layers** | `meta` |
| **modules_touched** | `meta/optimizer.py`, `meta/run_eval.py` |
| **dependencies** | `STORY-402`, `EXTERNAL: LangSmith evaluation datasets` |
| **tdd_tier** | `L3` |
| **governance_touchpoints** | `eval_capture` target: `optimizer_benchmark`, `BlackBox` recording for benchmark runs |
| **style_violations_to_avoid** | `AP8`, `M2`, `DEP.no_upward_to_orch` |

**Acceptance Criteria:**
- `BenchmarkRunner.run(candidates: list[RoutingConfig], golden_set: list[EvalRecord]) -> list[BenchmarkResult]` executes each candidate against the golden set
- `BenchmarkResult` captures: config used, `AgentMetrics`, `EvalReport` (from judge), cost_usd, latency_ms
- Comparison logic: `select_best(results: list[BenchmarkResult], baseline: BenchmarkResult) -> RoutingConfig` picks the candidate that improves success_rate without exceeding baseline cost by >10%
- If no candidate beats baseline, returns baseline config (conservative default)
- Benchmark execution records all LLM calls via `eval_capture` with target `optimizer_benchmark`

**Test Obligations:**
- L2: Comparison logic with mock `BenchmarkResult` data (no real LLM calls)
- L3: End-to-end benchmark with recorded fixtures (marker: `@pytest.mark.slow`)
- Failure path: all candidates worse than baseline → returns baseline
- Failure path: golden set empty → raises `ValueError` with clear message

---

### STORY-404: Optimizer CLI and Config Persistence

| Field | Value |
|-------|-------|
| **id** | `STORY-404` |
| **title** | CLI entrypoint for meta-optimizer with safe config writes |
| **phase** | 4 |
| **layers** | `meta` |
| **modules_touched** | `meta/optimizer.py`, `meta/__init__.py` |
| **dependencies** | `STORY-403` |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | `PhaseLogger` for config change audit trail, `BlackBox` for recording |
| **style_violations_to_avoid** | `AP8`, `M2` |

**Acceptance Criteria:**
- `python -m meta.optimizer --eval-data <path> --golden-set <path> [--dry-run]` runs the full pipeline
- `--dry-run` prints proposed config diff without writing
- Config writes create a backup of the current `routing_config.py` before modification
- Config write uses AST-safe modification (updates field defaults in the Pydantic model, does not rewrite the whole file)
- All config changes logged via `PhaseLogger` with before/after values
- Exit code 0 if config improved, 1 if baseline kept, 2 on error

**Test Obligations:**
- L2: dry-run produces diff output without file mutation
- L2: config backup is created before write
- Failure path: read-only filesystem → graceful error with exit code 2
- Failure path: invalid eval data path → clear error message

---

### STORY-405: Drift Detection CLI and Scheduling

| Field | Value |
|-------|-------|
| **id** | `STORY-405` |
| **title** | Wire drift detection into CLI with scheduling support |
| **phase** | 4 |
| **layers** | `meta` |
| **modules_touched** | `meta/drift.py`, `meta/__init__.py` |
| **dependencies** | — (drift algorithms exist) |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | `eval_capture` target: `drift_check`, `PhaseLogger` for alert decisions |
| **style_violations_to_avoid** | `AP8`, `M2` |

**Acceptance Criteria:**
- `python -m meta.drift --baseline <path> --production <path> [--registry-dir <path>]` runs all three levels
- Output: JSON `DriftReport` to stdout or file
- Exit code 0 if no drift, 1 if drift detected, 2 on error
- Level selection flags: `--level 1`, `--level 2`, `--level 3`, `--level all` (default: all)
- Structured log output to `logs/drift.log` via per-concern routing

**Test Obligations:**
- L2: CLI invocation with mock data produces valid `DriftReport` JSON
- Failure path: missing baseline file → exit code 2 with error message
- Failure path: empty registry dir → Level 3 returns empty alerts (not an error)

---

### STORY-406: Drift Alerting Integration

| Field | Value |
|-------|-------|
| **id** | `STORY-406` |
| **title** | Alert routing from drift reports to governance pipeline |
| **phase** | 4 |
| **layers** | `meta`, `horizontal` |
| **modules_touched** | `meta/drift.py`, `services/governance/phase_logger.py` |
| **dependencies** | `STORY-405` |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | `PhaseLogger` decision: `drift_alert_emitted`, `workflow_id` correlation |
| **style_violations_to_avoid** | `AP8`, `M2`, `DEP.no_upward_to_orch` |

**Acceptance Criteria:**
- When `DriftReport.has_drift == True`, emit a `PhaseLogger` decision record with alert details
- Alert records include: `workflow_id` (for correlation), drift level, metric name, current vs baseline values
- For Level 3 (governance drift), additionally call `agent_facts_registry.verify(agent_id)` for each failing agent and log the results
- Alert routing is configurable: log-only (default) or webhook (deferred to STORY-406b)

**Test Obligations:**
- L2: drift report with alerts → PhaseLogger receives decision record
- L2: drift report without alerts → no PhaseLogger call
- Failure path: PhaseLogger unavailable → alert logged to stderr, does not crash

---

### STORY-407: Drift Detection Test Hardening

| Field | Value |
|-------|-------|
| **id** | `STORY-407` |
| **title** | Complete L1/L2 test coverage for all drift detection levels |
| **phase** | 4 |
| **layers** | `meta` |
| **modules_touched** | `tests/meta/test_drift.py` |
| **dependencies** | `STORY-405` |
| **tdd_tier** | `L1`, `L2` |
| **governance_touchpoints** | — |
| **style_violations_to_avoid** | `TAP-1` (no tautological tests), `TAP-4` (gap blindness) |

**Acceptance Criteria:**
- Level 1 tests: zero-variance baseline, negative drift, positive drift, single-element lists, empty lists
- Level 2 tests: perfect agreement (kappa=1.0), chance agreement (kappa≈0), below threshold, above threshold, mismatched list lengths
- Level 3 tests: empty registry, all valid agents, one tampered agent, registry with audit files mixed in
- `DriftReport` property tests: `has_drift` True/False correctness
- All tests deterministic, no I/O beyond `tmp_path`

**Test Obligations:**
- Failure paths first: every drift function has a "no drift detected" test AND a "drift detected" test
- Property-based: `DriftAlert.triggered` is always `True` when created by detection functions
- Marker: none (L1/L2, runs in CI)

---

### STORY-408: CodeReviewer Agent Class

| Field | Value |
|-------|-------|
| **id** | `STORY-408` |
| **title** | Build `meta/code_reviewer.py` — agent that produces `ReviewReport` |
| **phase** | 4 |
| **layers** | `meta` |
| **modules_touched** | `meta/code_reviewer.py` (new) |
| **dependencies** | `EXTERNAL: trust/review_schema.py` (exists), `EXTERNAL: prompts/codeReviewer/` (exists) |
| **tdd_tier** | `L3` |
| **governance_touchpoints** | `eval_capture` target: `code_review`, `BlackBox` recording |
| **style_violations_to_avoid** | `AP8`, `M2`, `AP3` (no hardcoded prompts), `H1` (use PromptService) |

**Acceptance Criteria:**
- `CodeReviewerAgent.review(files: list[str], diff: str | None) -> ReviewReport` produces a structured review
- Uses `PromptService.render_prompt("CodeReviewer_system_prompt")` for system prompt
- Uses `PromptService.render_prompt("CodeReviewer_architecture_rules")` for rules injection
- Uses `PromptService.render_prompt("CodeReviewer_review_submission", ...)` for file/diff submission
- LLM output is parsed into `ReviewReport` with retry on schema validation failure (max 2 retries)
- Every LLM call recorded via `eval_capture.record()` with target `code_review` and `task_id`
- Agent uses `llm_config` tier references (no hardcoded model names)

**Test Obligations:**
- L2: mock LLM returns valid ReviewReport JSON → parsed correctly
- L2: mock LLM returns malformed JSON → retry logic triggered, parse_error handling
- L3: end-to-end with recorded LLM fixture (marker: `@pytest.mark.slow`)
- Failure path: all retries fail → returns ReviewReport with verdict=`reject`, empty dimensions, error in gaps

---

### STORY-409: CodeReviewer Dimension Validation Logic

| Field | Value |
|-------|-------|
| **id** | `STORY-409` |
| **title** | Deterministic dimension validators for CodeReviewer |
| **phase** | 4 |
| **layers** | `meta`, `vertical` |
| **modules_touched** | `meta/code_reviewer.py`, `components/schemas.py` (if needed) |
| **dependencies** | `STORY-408` |
| **tdd_tier** | `L1`, `L2` |
| **governance_touchpoints** | — |
| **style_violations_to_avoid** | `AP5` (no domain logic in orchestration), `DEP.v_no_v` |

**Acceptance Criteria:**
- Deterministic validators for AST-checkable rules: `DEP.trust_no_upward`, `DEP.h_no_vertical`, `DEP.v_no_v`, `DEP.no_upward_to_orch`
- Each validator: `check_import_rule(file_path: str, file_ast: ast.Module) -> list[ReviewFinding]`
- Validators produce `ReviewFinding` with `rule_id`, `file`, `line`, `severity`, and `Certificate` with premises from AST inspection
- These complement (not replace) the LLM-based review — they handle the rules that are mechanically verifiable
- Validators are pure functions (no I/O beyond reading the already-parsed AST)

**Test Obligations:**
- L1: each validator tested with synthetic AST that violates the rule → produces finding
- L1: each validator tested with clean AST → produces no findings
- Failure path: unparseable Python file → returns finding with severity=warning, description explaining parse failure
- Tests use `ast.parse()` on string literals, no file I/O

---

### STORY-410: CodeReviewer CLI Entrypoint

| Field | Value |
|-------|-------|
| **id** | `STORY-410` |
| **title** | CLI for running code reviews on files or git diffs |
| **phase** | 4 |
| **layers** | `meta` |
| **modules_touched** | `meta/code_reviewer.py`, `meta/__init__.py` |
| **dependencies** | `STORY-408`, `STORY-409` |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | `BlackBox` recording, `PhaseLogger` for review decisions |
| **style_violations_to_avoid** | `AP8`, `M2` |

**Acceptance Criteria:**
- `python -m meta.code_reviewer --files <path1> <path2> [--diff <diff_file>] [--output <report.json>]`
- Runs both deterministic validators (STORY-409) and LLM-based review (STORY-408)
- Merges findings from both sources into a single `ReviewReport`
- Output: JSON `ReviewReport` to file or stdout
- Exit code: 0 for approve, 1 for request_changes, 2 for reject, 3 on error
- `--deterministic-only` flag skips LLM review (useful for CI without API keys)

**Test Obligations:**
- L2: `--deterministic-only` with clean files → exit 0, verdict approve
- L2: `--deterministic-only` with violating file → exit 1 or 2, findings present
- Failure path: nonexistent file path → exit 3 with error message
- Failure path: `--output` to read-only path → exit 3

---

### STORY-411: CodeReviewer Integration with Existing Architecture Tests

| Field | Value |
|-------|-------|
| **id** | `STORY-411` |
| **title** | Align CodeReviewer validators with `tests/architecture/` enforcement |
| **phase** | 4 |
| **layers** | `meta`, `horizontal` |
| **modules_touched** | `meta/code_reviewer.py`, `tests/architecture/` |
| **dependencies** | `STORY-409` |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | — |
| **style_violations_to_avoid** | `TAP-1`, `TAP-2` |

**Acceptance Criteria:**
- CodeReviewer's deterministic validators use the same import-checking logic as `tests/architecture/test_dependency_rules.py` (shared utility, not copy-paste)
- Extract shared logic into `utils/code_analysis.py` (if not already there) or confirm existing `utils/code_analysis.py` is sufficient
- Both `tests/architecture/` and `meta/code_reviewer.py` import from the shared utility
- Existing architecture tests continue to pass unchanged

**Test Obligations:**
- L2: shared utility produces identical results when called from test harness vs CodeReviewer
- Regression: all existing `tests/architecture/` tests pass after refactor

---

### STORY-412: LangGraph Usage Instrumentation

| Field | Value |
|-------|-------|
| **id** | `STORY-412` |
| **title** | Add checkpointing and rollback usage counters to orchestration |
| **phase** | 4 |
| **layers** | `orchestration`, `horizontal` |
| **modules_touched** | `orchestration/react_loop.py`, `services/observability.py` |
| **dependencies** | — |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | `eval_capture` target: `framework_telemetry`, `workflow_id` correlation |
| **style_violations_to_avoid** | `AP5` (no domain logic in orchestration — counters are infrastructure, not domain), `O1` |

**Acceptance Criteria:**
- Counter: `checkpoint_invocations` — incremented each time `SqliteSaver` writes a checkpoint
- Counter: `rollback_invocations` — incremented each time state is restored from a checkpoint
- Counter: `rollback_time_saved_ms` — estimated time saved by rollback (difference between re-execution estimate and actual rollback time)
- Counter: `auto_trace_insights` — manual tally field for debugging insights surfaced by LangSmith auto-tracing (updated by developers during Phase 4)
- Counters stored in a `FrameworkTelemetry` Pydantic model in `services/observability.py`
- Counters persisted to `logs/framework_telemetry.jsonl`

**Test Obligations:**
- L2: checkpoint write → counter incremented
- L2: rollback → counter incremented
- L2: `FrameworkTelemetry` serialization roundtrip
- Failure path: telemetry write fails → logged warning, does not crash the agent

---

### STORY-413: Feasibility Decision Report Generator

| Field | Value |
|-------|-------|
| **id** | `STORY-413` |
| **title** | Generate LangGraph keep-or-replace decision report |
| **phase** | 4 |
| **layers** | `meta` |
| **modules_touched** | `meta/feasibility.py` (new) |
| **dependencies** | `STORY-412` |
| **tdd_tier** | `L2` |
| **governance_touchpoints** | `PhaseLogger` decision: `framework_feasibility_verdict` |
| **style_violations_to_avoid** | `AP8`, `M2`, `DEP.no_upward_to_orch` |

**Acceptance Criteria:**
- `FeasibilityGate.evaluate(telemetry: FrameworkTelemetry, total_tasks: int) -> FeasibilityReport`
- `FeasibilityReport` includes:
  - `keep_langgraph: bool` — the verdict
  - `checkpoint_usage_rate: float` — checkpoints / total tasks (threshold: >10%)
  - `rollback_time_saved_minutes: float` — total rollback time saved (threshold: >5 min per 100 tasks)
  - `auto_trace_insights: int` — count of debugging insights (threshold: >3)
  - `criteria_met: dict[str, bool]` — per-criterion pass/fail
  - `recommendation: str` — human-readable recommendation paragraph
- All three criteria must be met to recommend keeping LangGraph
- `FeasibilityReport` is a Pydantic model in `meta/feasibility.py`
- `meta/feasibility.py` has zero imports from `orchestration/`

**Test Obligations:**
- L2: all criteria met → `keep_langgraph=True`
- L2: one criterion fails → `keep_langgraph=False`
- L2: all criteria fail → `keep_langgraph=False`
- L2: zero total tasks → raises `ValueError`
- Boundary test: exactly at threshold values (10%, 5 min, 3 insights)

---

### STORY-414: Pydantic AI Fallback Prototype

| Field | Value |
|-------|-------|
| **id** | `STORY-414` |
| **title** | Prototype Pydantic AI replacement for LangGraph loop |
| **phase** | 4 |
| **layers** | `orchestration`, `meta` |
| **modules_touched** | `meta/fallback_prototype.py` (new), `meta/feasibility.py` |
| **dependencies** | `STORY-413` |
| **tdd_tier** | `L4` |
| **governance_touchpoints** | `BlackBox` recording, `eval_capture` target: `fallback_prototype` |
| **style_violations_to_avoid** | `AP5`, `DEP.no_upward_to_orch` (prototype is a separate module, not modifying orchestration) |

**Acceptance Criteria:**
- `FallbackReactLoop.run(task: str) -> TaskResult` implements the same ReAct cycle as `orchestration/react_loop.py` using a plain `while` loop
- Uses the same `components/` functions (router, evaluator) and `services/` (prompt_service, llm_config, eval_capture)
- Uses raw `litellm.completion()` instead of `ChatLiteLLM`
- State management via Pydantic `BaseModel` instead of `TypedDict`
- Checkpoint equivalent: JSON state serialization before tool execution (~50 lines)
- Prototype passes at least 3 benchmark tasks from the golden set with equivalent quality
- This is an **evaluation prototype**, not a production replacement — it lives in `meta/` and is only used if the feasibility gate fails

**Test Obligations:**
- L4: benchmark comparison between LangGraph loop and fallback loop on 3 tasks (marker: `@pytest.mark.simulation`, `@pytest.mark.live_llm`)
- L2: state serialization roundtrip test (no LLM needed)
- Failure path: tool execution failure → state restored from JSON checkpoint

---

## Implementation Ordering (Iteration Plan)

### Iteration 1: Foundation (Week 1)
**Stories:** STORY-401, STORY-405, STORY-407, STORY-412

These have no inter-dependencies and can be implemented in parallel. They establish the data foundations: enhanced analytics, drift CLI, drift test hardening, and framework telemetry counters.

```
STORY-401 (analytics enhancement)      ──┐
STORY-405 (drift CLI)                   ──┤── Parallel
STORY-407 (drift test hardening)        ──┤
STORY-412 (framework instrumentation)  ──┘
```

### Iteration 2: Core Agents (Week 2)
**Stories:** STORY-402, STORY-406, STORY-408, STORY-409

Depends on Iteration 1. Meta-optimizer core, drift alerting, and CodeReviewer agent + validators.

```
STORY-402 (optimizer core)     ← STORY-401
STORY-406 (drift alerting)    ← STORY-405
STORY-408 (CodeReviewer agent) ← (trust/review_schema.py exists)
STORY-409 (deterministic validators) ← STORY-408
```

### Iteration 3: Integration & CLI (Week 3)
**Stories:** STORY-403, STORY-410, STORY-411, STORY-413

Benchmark runner, CodeReviewer CLI, architecture test alignment, and feasibility report.

```
STORY-403 (benchmark runner)        ← STORY-402
STORY-410 (CodeReviewer CLI)        ← STORY-408, STORY-409
STORY-411 (architecture alignment)  ← STORY-409
STORY-413 (feasibility report)      ← STORY-412
```

### Iteration 4: Completion & Decision (Week 4)
**Stories:** STORY-404, STORY-414

Optimizer CLI with config persistence, and the Pydantic AI fallback prototype.

```
STORY-404 (optimizer CLI)           ← STORY-403
STORY-414 (fallback prototype)      ← STORY-413
```

---

## Cross-Cutting Constraints

### Architecture Rules Enforced Across All Stories

| Rule ID | Constraint | Affected Stories |
|---------|-----------|-----------------|
| `AP8` | Meta-layer must not import from `orchestration/` | ALL (401-414) |
| `M2` | Meta may call horizontal services directly (downward dependency allowed) | 406, 408, 410 |
| `DEP.no_upward_to_orch` | Nothing imports orchestration from below | ALL |
| `O1` | Orchestration nodes are thin wrappers (no domain logic) | 412 |
| `H1` | All prompts via PromptService, no hardcoded strings | 408, 410 |
| `AP3` | No hardcoded prompts in Python code | 408, 410 |
| `AP5` | No domain logic in orchestration nodes | 412 |
| `T1-T4` | Trust kernel remains pure — no new trust types needed for Phase 4 | — (trust/review_schema.py already exists) |

### Test Pyramid Distribution

| Tier | Stories | Count | CI Policy |
|------|---------|-------|-----------|
| L1 | STORY-407, STORY-409 | 2 | Block merge, <10s |
| L2 | STORY-401, STORY-402, STORY-404, STORY-405, STORY-406, STORY-410, STORY-411, STORY-412, STORY-413 | 9 | Block merge, <30s |
| L3 | STORY-403, STORY-408 | 2 | `@pytest.mark.slow`, nightly |
| L4 | STORY-414 | 1 | `@pytest.mark.simulation`, `@pytest.mark.live_llm`, on-demand |

---

## Validation Log

| Check | Result | Details |
|-------|--------|---------|
| `coverage_completeness` | **Pass** | All PLAN_v2 §4.1–4.5 goals covered: analytics (4.1→STORY-401), optimizer (4.2→STORY-402/403/404), drift (4.3→STORY-405/406/407), CodeReviewer (4.4→STORY-408/409/410/411), feasibility gate (4.5→STORY-412/413/414) |
| `layer_alignment` | **Pass** | All stories place modules in correct layers: `meta/` for offline optimization, `components/` for routing_config, `orchestration/` for instrumentation only, `trust/` not modified (review_schema.py pre-exists) |
| `dependency_rule_compliance` | **Pass** | No story implies upward imports. Meta→horizontal allowed (STORY-406, 408). Meta→vertical allowed for routing_config reads (STORY-402). Orchestration changes are instrumentation only (STORY-412). |
| `failure_path_coverage` | **Pass** | Every story has explicit failure-path acceptance criteria and test obligations. STORY-407 specifically hardens drift detection failure paths. |
| `anti_pattern_scan` | **Pass** | No story encodes AP1-AP9 violations. STORY-408 explicitly requires PromptService usage (prevents AP3). STORY-412 explicitly limits orchestration changes to counters (prevents AP5). |
| `contract_coverage` | **Pass** | Cross-module types: `OptimizerInput` (STORY-401→402), `BenchmarkResult` (STORY-403→404), `FrameworkTelemetry` (STORY-412→413), `ReviewReport` (trust/, consumed by STORY-408/410). All defined as Pydantic models. |
| `determinism_policy` | **Pass** | L1/L2 tests are deterministic (mock LLM, fixture data, `tmp_path`). L3 tests use recorded fixtures. L4 tests (STORY-414) are explicitly marked `live_llm` and `simulation`. |
| `cicd_marker_policy` | **Pass** | STORY-403/408 use `@pytest.mark.slow`. STORY-414 uses `@pytest.mark.simulation` + `@pytest.mark.live_llm`. All others run in default CI. |

---

## Gaps

### Uncovered Plan Goals
- None for Phase 4. All §4.1–4.5 goals are covered.

### Cross-Sprint Risks
- **STORY-403 depends on LangSmith evaluation datasets existing** — if golden set is empty or insufficient, benchmark results are unreliable. Mitigation: STORY-401 should validate golden set size as a precondition.
- **STORY-414 (fallback prototype) requires live LLM calls** — cannot validate in CI. Mitigation: manual run before feasibility decision, recorded fixture for regression.
- **STORY-412 (instrumentation) modifies `orchestration/react_loop.py`** — risk of breaking existing graph topology. Mitigation: changes are additive (counter increments), existing tests must pass.

### Explicit Deferrals
| Deferral | Impact | Deferred To |
|----------|--------|-------------|
| Webhook alerting for drift detection | Alerts are log-only; no external notification | Post-Phase 4 operational readiness sprint |
| Multi-model benchmark (comparing across LLM providers) | Optimizer benchmarks use current provider only | Phase 5 (if exists) or operational tuning |
| Full Pydantic AI migration (if feasibility gate fails) | Only a prototype is built; production migration is a separate effort | Dedicated migration sprint triggered by feasibility report |
| Automated optimizer scheduling (cron) | Optimizer runs manually via CLI | Operational readiness |

---

## Executive Summary

This sprint delivers Phase 4 of PLAN_v2 across four MECE workstreams in four iterations over approximately four weeks. **Workstream 1 (Meta-Optimizer)** closes the feedback loop between production logs and routing thresholds, with conservative defaults that never make things worse. **Workstream 2 (Drift Detection)** operationalizes the existing three-level drift algorithms with CLI tooling and governance alerting. **Workstream 3 (CodeReviewer)** produces an architecture validation agent with both deterministic AST-based checks and LLM-powered review, outputting structured `ReviewReport` artifacts. **Workstream 4 (Feasibility Gate)** instruments LangGraph usage and generates a data-driven keep-or-replace decision.

**Top risks:** LangSmith golden set readiness (blocks benchmark reliability), live LLM dependency for the fallback prototype (cannot CI-validate), and orchestration instrumentation changes (must not break existing graph). All are mitigated with conservative defaults, recorded fixtures, and additive-only changes.

The sprint produces 14 stories with 11 in L1/L2 (CI-blocking), 2 in L3 (nightly), and 1 in L4 (on-demand). No story violates the four-layer dependency rules, and no new trust kernel types are needed.
