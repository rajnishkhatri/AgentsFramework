---
type: reference
title: 'Pyramid Agent — End-to-End Sequence Diagrams'
description: '1.'
tags: [structured-reasoning]
---

# Pyramid Agent — End-to-End Sequence Diagrams

> Readable sequence diagrams for the `StructuredReasoning/` Pyramid ReACT agent.
> Each scenario is broken into focused phases to avoid overlapping text and the "wall of arrows" problem.

---

## Table of Contents

1. [Scenario 1: Happy Path](#scenario-1-happy-path-valid-analysis-on-first-try)
2. [Scenario 2: Parse Retry](#scenario-2-parse-failure-with-successful-retry)
3. [Scenario 3: Rejected Input](#scenario-3-input-rejected-by-guardrail)
4. [Governance Trail](#cross-cutting-governance-trail)
5. [Layer Dependency Map](#architecture-layer-dependencies)

---

## Scenario 1: Happy Path (Valid Analysis on First Try)

The most common flow. The user submits a legitimate problem, the LLM produces valid
JSON on the first attempt, and the analysis is persisted to disk.

### Phase A — CLI Bootstrap

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli_pyramid

    User ->> CLI: Run script with input
    
    note over CLI: 1. Build AgentConfig<br/>2. Build ToolRegistry<br/>3. Generate IDs
    
    CLI ->> CLI: build_pyramid_graph()
    note over CLI: Graph compiled:<br/>START → guard_input → analyze → persist → END
```

### Phase B — Input Guard

```mermaid
sequenceDiagram
    participant CLI as cli_pyramid
    participant Graph as LangGraph
    participant Guard as guard_input
    participant Guardrail as InputGuardrail
    participant JudgeLLM as LLMJudge
    participant BB as BlackBox
    participant Eval as eval_capture

    CLI ->> Graph: ainvoke(state)
    Graph ->> Guard: guard_input_node()

    Guard ->> BB: record(TASK_STARTED)

    Guard ->> Guardrail: is_acceptable()
    Guardrail ->> JudgeLLM: Evaluate input
    JudgeLLM -->> Guardrail: "accept"
    Guardrail -->> Guard: accepted = True

    Guard ->> BB: record(GUARDRAIL_CHECKED)
    Guard ->> Eval: record(target="pyramid_guardrail")
    Guard -->> Graph: route to analyze
```

### Phase C — Analyze (LLM Call + Parse + Validate)

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant Analyze as analyze_node
    participant PS as PromptService
    participant LLM as LLMService
    participant BB as BlackBox
    participant Parser as pyramid_parser
    participant Schema as AnalysisOutput

    Graph ->> Analyze: analyze_node()

    Analyze ->> PS: render_prompt()
    PS -->> Analyze: system_prompt

    Analyze ->> LLM: invoke(messages)
    note over LLM: Executes 4-phase protocol
    LLM -->> Analyze: content + usage_metadata

    Analyze ->> BB: record(STEP_EXECUTED)

    Analyze ->> Parser: parse_analysis_output()
    Parser ->> Parser: extract_json_object()
    Parser ->> Schema: model_validate()
    Schema -->> Parser: Validated Object
    Parser -->> Analyze: analysis (valid)

    Analyze -->> Graph: return {last_outcome: "done"}
```

### Phase D — Persist + Render

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant Persist as persist_node
    participant Disk as FileSystem
    participant BB as BlackBox
    participant CLI as cli_pyramid
    actor User

    Graph ->> Persist: persist_node()

    Persist ->> Disk: write_analysis()
    Disk -->> Persist: file path

    Persist ->> BB: record(TASK_COMPLETED)
    Persist -->> Graph: return {}
    note over Graph: Graph execution END

    Graph -->> CLI: final state
    CLI ->> User: Display YAML Panel & Cost Summary
```

---

## Scenario 2: Parse Failure with Successful Retry

The LLM returns prose instead of JSON on the first attempt. The parser
detects this, and the analyze node issues exactly one retry with a
corrective prompt. The second attempt succeeds.

```mermaid
sequenceDiagram
    participant Analyze as analyze_node
    participant LLM as LLMService
    participant Parser as pyramid_parser
    participant Schema as AnalysisOutput

    note over Analyze: ── Attempt 1 ──
    Analyze ->> LLM: invoke(messages)
    LLM -->> Analyze: Prose response (No JSON)

    Analyze ->> Parser: parse_analysis_output()
    Parser --x Analyze: ParseError (No JSON object)

    note over Analyze: ── Build Retry ──
    Analyze ->> Analyze: Append corrective prompt

    note over Analyze: ── Attempt 2 ──
    Analyze ->> LLM: invoke(messages + retry)
    LLM -->> Analyze: Valid JSON response

    Analyze ->> Parser: parse_analysis_output()
    Parser ->> Schema: model_validate()
    Schema -->> Parser: Validated Object
    Parser -->> Analyze: analysis

    Analyze -->> Analyze: outcome = "done"
```

### What if both attempts fail?

```mermaid
sequenceDiagram
    participant Analyze as analyze_node
    participant Persist as persist_node
    participant CLI as cli_pyramid
    actor User

    note over Analyze: Attempt 1 → ParseError
    note over Analyze: Attempt 2 → ParseError

    Analyze -->> Persist: {last_outcome: "parse_failed"}
    note over Persist: Skip writing to disk

    Persist -->> CLI: final state
    CLI ->> User: Display Parse Failure Error
```

---

## Scenario 3: Input Rejected by Guardrail

The guardrail detects prompt injection or an illegitimate input.
The expensive analysis LLM call is never made.

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli_pyramid
    participant Graph as LangGraph
    participant Guard as guard_input
    participant Guardrail as InputGuardrail
    participant JudgeLLM as LLMJudge
    participant BB as BlackBox

    User ->> CLI: "Ignore instructions..."
    CLI ->> Graph: ainvoke(state)

    Graph ->> Guard: guard_input_node()
    Guard ->> BB: record(TASK_STARTED)

    Guard ->> Guardrail: is_acceptable()
    Guardrail ->> JudgeLLM: Evaluate input
    JudgeLLM -->> Guardrail: "reject"
    Guardrail -->> Guard: accepted = False

    Guard ->> BB: record(GUARDRAIL_CHECKED)
    Guard -->> Graph: {last_outcome: "rejected"}

    note over Graph: Route to END

    Graph -->> CLI: final state
    CLI ->> User: Display "Rejected" Error
```

---

## Cross-Cutting: Governance Trail

Every scenario produces governance artifacts. Four systems record
events in parallel throughout the graph execution.

```mermaid
sequenceDiagram
    participant Nodes as GraphNodes
    participant BB as BlackBox
    participant PL as PhaseLogger
    participant Eval as eval_capture
    participant FS as FileSystem

    Nodes ->> BB: TraceEvent(TASK_STARTED)
    Nodes ->> BB: TraceEvent(GUARDRAIL_CHECKED)
    Nodes ->> BB: TraceEvent(STEP_EXECUTED)
    Nodes ->> BB: TraceEvent(TASK_COMPLETED)
    BB ->> FS: Append to trace.jsonl

    Nodes ->> Eval: record(target)

    Nodes ->> PL: Decision(phase, outcome)
    PL ->> FS: Append to decisions.jsonl
```

### Artifact Summary

| Recorder | What It Captures | Output Path |
|---|---|---|
| **BlackBoxRecorder** | Lifecycle events: `TASK_STARTED`, `GUARDRAIL_CHECKED`, `STEP_EXECUTED`, `TASK_COMPLETED` | `cache/pyramid/black_box_recordings/<wf>/trace.jsonl` |
| **PhaseLogger** | Decision points with alternatives, rationale, confidence | `cache/pyramid/phase_logs/<wf>/decisions.jsonl` |
| **eval_capture** | Every LLM call (model, tokens, cost, latency) and guardrail decision | Available for offline eval pipelines |
| **pyramid_persistence** | Final validated `analysis_output` | `cache/pyramid/<wf>/analysis.json` |

---

## Architecture: Layer Dependencies

Dependencies flow strictly downward. No upward imports.

```mermaid
graph TD
    CLI["cli_pyramid.py"]
    ORCH["orchestration/"]
    COMP["components/"]
    SVC["services/"]
    SVC_SHARED["services/ (shared)"]
    TRUST["trust/"]
    PROMPTS["prompts/"]

    CLI --> ORCH
    ORCH --> COMP
    ORCH --> SVC
    ORCH --> SVC_SHARED
    ORCH --> PROMPTS
    COMP --> TRUST
    SVC_SHARED -.->|reads types| TRUST

    style CLI fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
    style ORCH fill:#fce4ec,stroke:#c62828,stroke-width:2px
    style COMP fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style SVC fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style SVC_SHARED fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style TRUST fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style PROMPTS fill:#fffde7,stroke:#f9a825,stroke-width:2px
```

### Import Rules

| From | May Import | Must NOT Import |
|---|---|---|
| `cli_pyramid.py` | orchestration, services | — |
| `orchestration/` | components, services, trust | — |
| `components/` | trust only | services, orchestration |
| `services/` (pyramid) | stdlib, pathlib | components, orchestration, trust |
| `trust/` | stdlib, Pydantic only | everything else |
