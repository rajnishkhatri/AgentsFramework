# Explainability & Compliance Dashboard — Brainstorm

> **Date:** April 27, 2026
> **Status:** Brainstorm / Design Phase
> **Participants:** Dev team

---

## Table of Contents

1. [Existing Data Infrastructure](#1-existing-data-infrastructure)
2. [Personas & Use Cases](#2-personas--use-cases)
3. [Proposed Module Architecture](#3-proposed-module-architecture)
4. [Module 1: Dashboard (Home)](#module-1-dashboard-home)
5. [Module 2: Trace Explorer](#module-2-trace-explorer)
6. [Module 3: Guardrail Monitor](#module-3-guardrail-monitor)
7. [Module 4: Decision Audit Trail](#module-4-decision-audit-trail)
8. [Module 5: Compliance Center](#module-5-compliance-center)
9. [Module 6: Agent Registry](#module-6-agent-registry)
10. [Module 7: Log Viewer](#module-7-log-viewer)
11. [Recommended Tech Stack](#recommended-tech-stack)
12. [Navigation & Data Flow Architecture](#navigation--data-flow-architecture)
13. [Unique Differentiators vs. Commercial Tools](#unique-differentiators-vs-commercial-tools)
14. [Pyramid Principle Gap Analysis](#pyramid-principle-gap-analysis)
15. [External Research Summary](#external-research-summary)
16. [Open Questions](#open-questions)

---

## 1. Existing Data Infrastructure

The codebase produces rich observability data across four artifact families:

| Artifact Family | Source | Format | Key Fields |
|---|---|---|---|
| **Black Box Traces** | `BlackBoxRecorder` | JSONL per `workflow_id` | `event_id`, `event_type`, `timestamp`, `details`, `integrity_hash` (SHA-256 chain) |
| **Phase Decisions** | `PhaseLogger` | JSONL per `workflow_id` | `phase`, `description`, `alternatives`, `rationale`, `confidence` |
| **Trust Trace Records** | `TrustTraceRecord` (trust kernel) | Pydantic model | `trace_id`, `agent_id`, `layer` (L1-L7), `event_type`, `outcome`, `causation_id` |
| **Per-Concern Logs** | `logging.json` routes | 6+ log files | `identity.log`, `guards.log`, `prompts.log`, `black_box.log`, `phases.log`, `evals.log` |

### Additional Data Sources

- **`AgentFacts`** — Signed identity cards (`agent_id`, `owner`, `version`, `capabilities`, `policies`, `signature_hash`)
- **`PolicyDecision`** — Allow/deny/throttle with backend type (OPA/Cedar/YAML/embedded) and reason
- **`AuditEntry`** — Per-agent change trail (`agent_id`, `action`, `performed_by`, `timestamp`, `details`)
- **`FrameworkTelemetry`** — Checkpoint/rollback counters (`checkpoint_invocations`, `rollback_invocations`, `rollback_time_saved_ms`)
- **Compliance bundles** — Joined output from `export_for_compliance()` combining black box events + agent identity + phase decisions

### Key Source Files

| File | Role |
|---|---|
| `services/governance/black_box.py` | Append-only JSONL recorder with SHA-256 chain |
| `services/governance/phase_logger.py` | Per-decision routing/evaluation logs |
| `services/governance/agent_facts_registry.py` | Agent identity, capabilities, HMAC signatures |
| `services/observability.py` | Logging setup + framework telemetry |
| `trust/models.py` | `TrustTraceRecord`, `PolicyDecision`, `AuditEntry`, `AgentFacts` |
| `services/trace_service.py` | `TraceService.emit(TrustTraceRecord)` fan-out to sinks |
| `services/eval_capture.py` | Per-LLM-call structured logging |
| `orchestration/react_loop.py` | Graph nodes that drive all four layers |
| `logging.json` | Per-concern log routing configuration |

### Known Gap

`END_TO_END_TRACING_GUIDE.md` documents a known gap: cross-correlation between `trace_id`, `workflow_id`, `task_id`, and `user_id` is incomplete in the LangGraph config threading. The UI should handle missing correlation keys gracefully and possibly show a "correlation health" indicator.

---

## 2. Personas & Use Cases

### Three Personas

| Persona | Goal | Primary Modules |
|---|---|---|
| **Developer** | Debug a failing agent run, understand why model X was chosen, replay execution | Trace Explorer, Log Viewer, Guardrail Monitor |
| **ML/Platform Engineer** | Monitor system health, spot latency regressions, track cost, detect drift | Dashboard, Trace Explorer |
| **Compliance Officer / Auditor** | Verify tamper-proof audit trails, export compliance bundles, review policy decisions | Compliance Center, Decision Audit, Agent Registry |

### Mapping to Four Pillars of Explainability

The governance triangle (`governanaceTriangle/`) defines four foundational pillars. Each must have a dedicated UI surface:

| Pillar | Question | Component | UI Module |
|---|---|---|---|
| **Recording** | What happened? | `BlackBoxRecorder` | Trace Explorer |
| **Identity** | Who did it? | `AgentFacts Registry` | Agent Registry |
| **Validation** | What was checked? | `GuardRails` | Guardrail Monitor |
| **Reasoning** | Why was it done? | `PhaseLogger` | Decision Audit |

---

## 3. Proposed Module Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  SIDEBAR                            PILLAR MAPPING               │
│  ┌──────────────────────────────┐                                │
│  │ 📊 Dashboard                 │  All Pillars (KPIs)           │
│  │ 🔍 Trace Explorer            │  RECORDING (What happened?)   │
│  │    ├─ Timeline View          │                                │
│  │    ├─ Cascade Analysis       │                                │
│  │    └─ Replay Mode            │                                │
│  │ 🛡 Guardrail Monitor        │  VALIDATION (What checked?)   │
│  │ 🧠 Decision Audit           │  REASONING (Why done?)        │
│  │ 📋 Compliance Center         │  Cross-pillar join            │
│  │    ├─ Compliance Bundle      │                                │
│  │    ├─ Templates (HIPAA/SOX)  │                                │
│  │    └─ Workflow Deep Dive     │  (4-pillar join view)         │
│  │ 👤 Agent Registry            │  IDENTITY (Who did it?)       │
│  │ 📋 Log Viewer                │  Observability (debugging)    │
│  │ ⚙ Settings                   │                                │
│  └──────────────────────────────┘                                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Module 1: Dashboard (Home)

**Pattern:** Inverted pyramid / progressive disclosure (Grafana best practice)

**Design principles:**
- **5-second rule** — Users should understand the main system status within 5 seconds
- Global filters at the top: time range, environment, agent_id
- KPI cards use color: green (healthy), amber (warning), red (critical)
- Every metric is clickable and drills into the relevant detail view

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  KPI Cards Row                                               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐              │
│  │Total │ │Avg   │ │P95   │ │Guard │ │Chain │              │
│  │Runs  │ │Cost  │ │Latency│ │Reject│ │Valid │              │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘              │
├─────────────────────────────────────────────────────────────┤
│  Time-Series Charts (2 rows)                                 │
│  ┌─────────────────┐  ┌─────────────────┐                    │
│  │ Cost over time   │  │ Latency (p50/95)│                    │
│  └─────────────────┘  └─────────────────┘                    │
│  ┌─────────────────┐  ┌─────────────────┐                    │
│  │ Token usage      │  │ Model routing   │                    │
│  │ (in/out stacked) │  │ distribution    │                    │
│  └─────────────────┘  └─────────────────┘                    │
├─────────────────────────────────────────────────────────────┤
│  Recent Runs Table (click → Trace Explorer)                  │
│  workflow_id | status | model | cost | latency | time        │
└─────────────────────────────────────────────────────────────┘
```

---

## Module 2: Trace Explorer

**Pattern:** Hierarchical trace tree (Langfuse/LangSmith pattern)

The core debugging module. Each `workflow_id` becomes a trace you can inspect.

### 2a. Timeline View

```
┌────────────────────────────────────────────────────────────────────┐
│  Trace: wf-21b731f5                                                │
│  Status: ✓ Success | Duration: 6.3s | Cost: $0.0024 | Steps: 1    │
├──────────────────────┬─────────────────────────────────────────────┤
│  TIMELINE (left)     │  DETAIL PANEL (right)                       │
│                      │                                             │
│  ▼ task_started      │  Event: guardrail_checked                   │
│    ├─ guardrail ✓    │  ─────────────────────                      │
│    │  (agent_facts)  │  Type: prompt_injection                     │
│    ├─ guardrail ✓    │  Result: accepted                           │
│    │  (prompt_inj)   │  Model: gpt-4o-mini (fast tier)             │
│    ├─ model_selected │  Latency: 4.5s                              │
│    │  gpt-4o         │  Template: input_guardrail.j2               │
│    ├─ step_executed  │                                             │
│    │  "Paris"        │  ┌─ Input ──────────────────────┐           │
│    └─ ✓ complete     │  │ "What is the capital of..."  │           │
│                      │  └──────────────────────────────┘           │
│                      │  ┌─ Output ─────────────────────┐           │
│                      │  │ {"accepted": true, ...}      │           │
│                      │  └──────────────────────────────┘           │
└──────────────────────┴─────────────────────────────────────────────┘
```

**Key features:**
- Waterfall timeline on the left showing span durations proportionally (like Jaeger)
- Click any span to see details in the right panel: inputs, outputs, metadata, token counts
- Color-coded by event type: guardrails (blue), model selection (purple), execution (green), errors (red)
- Decision overlay: for `model_selected` events, show the `PhaseLogger` decision inline — rationale, alternatives, confidence
- Hash chain badge: shield icon (intact) or warning (broken) for the black box chain

### 2b. Cascade Analysis View

Automatically detects ERROR → downstream SKIP patterns and renders a causal chain:

```
┌─────────────────────────────────────────────────────────────────┐
│  CASCADE FAILURE ANALYSIS: wf-21b731f5                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ROOT CAUSE                                                     │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │ Parameter Change: confidence_threshold 0.8 → 0.95          │  │
│   │ Agent: invoice-extractor-v2 at 14:00:10                    │  │
│   └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│   IMMEDIATE EFFECT                                               │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │ Extraction confidence: 0.92 < new threshold: 0.95         │  │
│   └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│   PROPAGATION                                                    │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │ ValidationError: "threshold too high - no valid results"  │  │
│   └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│   SYSTEM RESPONSE                                                │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │ Workflow terminated. Downstream steps skipped.             │  │
│   └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│   Plan vs. Actual:                                               │
│   Step 1 (extract) ✅ | Step 2 (validate) ❌ | Step 3 (approve) ⚠ SKIPPED │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2c. Replay Mode

- Scrubber/slider that moves through events chronologically
- At each position, show the full state: active agent, inputs/outputs, parameters in effect
- Highlight divergence points where actual execution deviated from the TaskPlan
- Step forward/backward through events

---

## Module 3: Guardrail Monitor

**Pattern:** Safety dashboard with drill-down (covers the Validation pillar)

```
┌──────────────────────────────────────────────────────────────────┐
│  Guardrail Monitor                                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ Summary KPIs ──────────────────────────────────────────┐     │
│  │ Total Checks: 1,247 | Pass: 98.2% | Reject: 1.1%       │     │
│  │ PII Detected: 3     | Escalated: 5  | Fixed: 8          │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─ Per-Validator Breakdown ───────────────────────────────┐     │
│  │ Validator          │ Pass  │ Fail │ Action │ Trend      │     │
│  │ prompt_injection   │ 98%   │ 2%   │ REJECT │ ↗ stable   │     │
│  │ output_pii_scan    │ 99.7% │ 0.3% │ REJECT │ → flat     │     │
│  │ length_check       │ 100%  │ 0%   │ LOG    │ → flat     │     │
│  │ confidence_range   │ 95%   │ 5%   │ FIX    │ ↘ watch    │     │
│  │ required_fields    │ 100%  │ 0%   │ REJECT │ → flat     │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─ Failure Action Distribution (pie chart) ───────────────┐     │
│  │ REJECT: 45% | FIX: 30% | LOG: 15% | ESCALATE: 8%      │     │
│  │ RETRY: 2%                                                │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─ Recent Failures (table, click → Trace Explorer) ──────┐     │
│  │ Time | Validator | Input Excerpt | Action | workflow_id  │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key features:**
- Per-validator drill-down: what inputs triggered failures, what action was taken
- PII detection heat map: which fields/workflows trigger PII detections most often
- Validator configuration viewer: show declarative constraint definitions alongside results
- Links to Trace Explorer for investigating specific failures

---

## Module 4: Decision Audit Trail

**Pattern:** Timeline + explainability overlay (covers the Reasoning pillar)

Surfaces `PhaseLogger` decisions and `PolicyDecision` records.

```
┌───────────────────────────────────────────────────────────────┐
│  Decision Audit: wf-21b731f5                                   │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  ● Routing Decision                           confidence: 75% │
│  ├─ Chose: gpt-4o (capable tier)                              │
│  ├─ Rejected: gpt-4o-mini                                     │
│  ├─ Rationale: "capable-for-planning (step=0, errors=0,       │
│  │              last_err=none, cost_usd=0.0000)"              │
│  └─ Phase: routing                                            │
│                                                               │
│  ● Evaluation Decision                       confidence: 100% │
│  ├─ Outcome: success                                          │
│  ├─ Alternatives: [retry, escalate, terminal]                 │
│  ├─ Rationale: "Step completed successfully"                  │
│  └─ Phase: evaluation                                         │
│                                                               │
│  ● Policy Enforcement (ACL)                                   │
│  ├─ Enforcement: allow                                        │
│  ├─ Backend: embedded                                         │
│  └─ Reason: "admin role has shell access"                     │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**Key features:**
- Confidence scores shown as progress bars
- Expandable rationale with syntax-highlighted JSON
- Filter by phase (routing, evaluation, tool_execution, etc.)
- Comparison view: what alternatives were considered and why they were rejected

---

## Module 5: Compliance Center

**Pattern:** Role-based compliance dashboard with export capabilities

### 5a. Compliance Bundle View

```
┌──────────────────────────────────────────────────────────────────┐
│  Compliance Center                                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ Integrity Status ──────────────────────────────────────┐     │
│  │ 🛡 42/42 workflows have valid hash chains               │     │
│  │ ⚠ 0 tampered chains detected                            │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─ Agent Identity Cards ──────────────────────────────────┐     │
│  │ cli-agent  │ ACTIVE │ v1.0 │ sig: a3f2...  │ View Card │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─ Guardrail Summary ─────────────────────────────────────┐     │
│  │ prompt_injection  │ 98% accept │ 2% reject │ trend ↗   │     │
│  │ output_pii_scan   │ 100% pass  │ 0% fail   │ trend →   │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─ Export ────────────────────────────────────────────────┐     │
│  │ [Export Compliance Bundle (JSON)]  [Export CSV]  [PDF]  │     │
│  │ Date range: [Apr 1] to [Apr 27]   Agent: [All ▼]      │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 5b. Workflow Deep Dive (4-Pillar Join View)

All four pillars side by side for a single `workflow_id`:

```
┌────────────────────────────────────────────────────────────────────┐
│  Workflow Deep Dive: wf-21b731f5                                    │
├──────────────────────┬─────────────────────────────────────────────┤
│                      │  IDENTITY (Who)                              │
│  RECORDING (What)    │  cli-agent v1.0 │ ACTIVE │ sig ✓            │
│  ──────────────────  │─────────────────────────────────────────────│
│  ▼ task_started      │  VALIDATION (Checked)                       │
│    ├─ guardrail ✓    │  prompt_injection: accepted ✓               │
│    ├─ model_selected │  agent_facts: verified ✓                    │
│    ├─ step_executed  │─────────────────────────────────────────────│
│    └─ ✓ complete     │  REASONING (Why)                            │
│                      │  Routing: gpt-4o (confidence: 75%)          │
│  Chain: intact 🛡    │  Evaluation: success (confidence: 100%)     │
└──────────────────────┴─────────────────────────────────────────────┘
```

### 5c. Compliance Templates

Predefined query templates per industry:

| Template | Questions Answered | Pillars Used |
|---|---|---|
| **HIPAA Audit** | "Show all decisions for scan ID X", "Prove PHI was never stored" | Identity + Validation |
| **SOX Trail** | "Reconstruct processing for invoice X", "Who approved and which version?" | Recording + Identity |
| **E-Discovery** | "Explain why document X was classified as not relevant" | Reasoning + Recording |
| **General Compliance** | "Has the audit trail been tampered with?" | Recording (hash chain) |

---

## Module 6: Agent Registry

**Pattern:** Agent catalog with identity verification (covers the Identity pillar)

```
┌──────────────────────────────────────────────────────────────────┐
│  Agent Registry                                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ Agent Catalog ─────────────────────────────────────────┐     │
│  │ Agent ID       │ Owner       │ Version │ Status │ Sig   │     │
│  │ cli-agent      │ cli-bootstrap│ 1.0    │ ACTIVE │ ✓     │     │
│  │ invoice-ext-v2 │ finance-team│ 2.1.0  │ ACTIVE │ ✓     │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─ Identity Card: cli-agent ──────────────────────────────┐     │
│  │ Capabilities: [extract_vendor, validate_amount, ...]     │     │
│  │ Policies: [rate_limit: 100/min, approval_threshold: 10k]│     │
│  │ Signature: a3f2b1c4... (verified ✓)                      │     │
│  │ Created: 2026-04-26 │ Updated: 2026-04-26                │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─ Audit Trail ───────────────────────────────────────────┐     │
│  │ 2026-04-26 07:13 │ Registered │ by cli-bootstrap        │     │
│  │ 2026-04-26 07:14 │ Verified   │ by react_loop           │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  [Search by capability: ________________]                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key features:**
- Agent catalog with status, owner, version, signature verification
- Identity card detail view: capabilities with schemas, policies, metadata
- Signature verification panel: current hash, last verified, tamper detection history
- Agent audit trail: chronological list of all changes (from `AuditEntry` records)
- Capability-based search: "Which agents can `extract_vendor`?"

---

## Module 7: Log Viewer

**Pattern:** Real-time streaming log viewer with per-concern filtering

```
┌──────────────────────────────────────────────────────────────┐
│  Log Viewer                                                    │
│  Concerns: [✓ guards] [✓ prompts] [✓ black_box] [○ evals]    │
│  Level: [✓ INFO] [✓ WARN] [✓ ERROR]  Search: [________]      │
├──────────────────────────────────────────────────────────────┤
│  07:14:07.341 INFO  black_box  Recorded task_started wf-21b  │
│  07:14:07.342 INFO  black_box  Recorded guardrail_checked    │
│  07:14:07.343 INFO  prompts    Rendered input_guardrail.j2   │
│  07:14:11.896 INFO  guards     prompt_injection: accepted    │
│  07:14:11.897 INFO  evals      AI Response                   │
│  07:14:11.899 INFO  phases     Decision [routing]: gpt-4o    │
│  07:14:11.900 INFO  black_box  Recorded model_selected       │
│  07:14:13.654 INFO  evals      AI Response                   │
│  07:14:13.654 INFO  black_box  Recorded step_executed        │
│  07:14:13.657 INFO  phases     Decision [eval]: success      │
└──────────────────────────────────────────────────────────────┘
```

**Key features:**
- Maps directly to the 6+ per-concern log files from `logging.json`
- Color-coded by concern
- Click any log line → jumps to the corresponding trace in the Trace Explorer
- Text search with regex support
- Tail mode for real-time streaming during development

---

## Recommended Tech Stack

Based on the existing frontend (Next.js 15 + React 19 + Tailwind v4 + shadcn):

| Concern | Recommendation | Why |
|---|---|---|
| **Charts** | Recharts or Visx | Recharts for standard dashboards; Visx for custom waterfall/flame graphs |
| **Timeline/Waterfall** | Custom component with Visx or vis.js | The trace tree is the core differentiator |
| **Data Tables** | TanStack Table (React Table v8) | Sorting, filtering, virtualization for large log sets |
| **Log Viewer** | `@monaco-editor/react` or custom virtual scroller | Monaco gives syntax highlighting + search for free |
| **State Management** | React Query (TanStack Query) + Zustand | React Query for server state, Zustand for UI state |
| **DAG Visualization** | React Flow | For visualizing the LangGraph topology |
| **Export/PDF** | jsPDF + html2canvas or react-pdf | For compliance bundle PDF export |

### Component Libraries for Specific Visualizations

| Use Case | Library |
|---|---|
| Flame Graphs | `react-flame-graph` |
| Timelines | `vis.js` |
| DAG/Networks | ECharts for React or Visx |
| Real-time Logs | ECharts for React or React-chartjs-2 |

---

## Navigation & Data Flow Architecture

### Data Flow

```
Python Backend                    API Layer              React Frontend
───────────────                   ─────────              ──────────────
BlackBoxRecorder ──┐
PhaseLogger ───────┼─→ /api/traces/{wf_id}        →  Trace Explorer
AgentFactsRegistry─┤   /api/traces                 →  Dashboard
                   ├─→ /api/compliance/{wf_id}     →  Compliance Center
Per-concern logs ──┤   /api/decisions/{wf_id}      →  Decision Audit
                   ├─→ /api/guardrails/summary     →  Guardrail Monitor
                   └─→ /api/logs?concern=...       →  Log Viewer
                       /api/dashboard/metrics      →  Dashboard KPIs
                       /api/agents                 →  Agent Registry
FrameworkTelemetry ──→ /api/telemetry              →  Dashboard
```

A thin API layer (extending the existing `middleware/` FastAPI server) would read from the JSONL files, SQLite checkpoints, and log files, then serve them as JSON endpoints.

---

## Unique Differentiators vs. Commercial Tools

Features that Langfuse, LangSmith, and other commercial tools do not offer:

| Feature | Our System | Langfuse/LangSmith |
|---|---|---|
| **Tamper-proof hash chains** | SHA-256 chained integrity verification per workflow | No equivalent |
| **Four-pillar tracing** | Cross-layer (L1-L7) trust tracing with `TrustTraceRecord` | Generic spans only |
| **Decision explainability with alternatives** | `PhaseLogger` records what was chosen, what was rejected, and why, with confidence scores | Basic metadata only |
| **Policy decision audit** | `PolicyDecision` with backend type (OPA/Cedar/YAML/embedded) and enforcement type | No policy layer |
| **Cascade failure analysis** | Root cause → propagation → system response visualization | Flat error display |
| **Compliance bundle export** | `export_for_compliance()` joins all four pillars | Manual assembly |

---

## Pyramid Principle Gap Analysis

Using the Pyramid Principle structured reasoning framework (`prompts/StructuredReasoning/PyramidAgent_system_prompt.j2`) to evaluate the initial proposal against the governance triangle (`governanaceTriangle/`).

### Governing Thought

**"The proposed UI covers 3 of 4 pillars well (Recording, Identity, Reasoning) but entirely misses the Validation pillar as a first-class surface, underserves cascade failure analysis and replay — the two features the governance triangle treats as its strongest differentiators — and lacks the cross-pillar 'join view' that makes compliance bundles actionable."**

### Gap Summary

| # | Gap | Severity | Resolution |
|---|---|---|---|
| 1 | **Validation pillar has no dedicated UI surface** — governance triangle treats it as co-equal to the other three pillars | Critical | Added Module 3: Guardrail Monitor |
| 2 | **No cascade failure visualization** — governance triangle's most detailed section (Tutorial 2) is cascade debugging | High | Added Cascade Analysis View to Trace Explorer |
| 3 | **No replay capability** — `replay()` is a first-class API; aviation analogy built around "simulate incident in flight simulator" | High | Added Replay Mode to Trace Explorer |
| 4 | **Cross-pillar correlation missing** — `export_for_compliance()` joins all four pillars but UI shows each in isolation | Medium | Added Workflow Deep Dive (4-pillar join view) |
| 5 | **Agent identity underserved** — governance triangle shows rich identity governance with capabilities, schemas, policies, tamper detection | Medium | Expanded to full Agent Registry module |
| 6 | **No industry-specific compliance templates** — governance triangle has per-industry component selection matrix | Medium | Added Compliance Templates to Compliance Center |

### Confidence: 0.87

Strong evidence from direct comparison. Minor uncertainty: some governance triangle features (e.g., rich `TaskPlan`, `PlanStep`, `AgentInfo`, `ParameterSubstitution` classes) may be aspirational rather than fully implemented in the current codebase. The UI design should be based on what's actually built, with extension points for future capabilities.

---

## External Research Summary

### Design Patterns from Industry (Langfuse, LangSmith, Grafana, Datadog)

| Pattern | Source | Application |
|---|---|---|
| **Inverted Pyramid (Progressive Disclosure)** | Grafana best practices | Dashboard → drill into traces |
| **Hierarchical Trace Trees** | Langfuse/LangSmith | Nested spans for execution flow |
| **One Page = One Decision** | Grafana | Each module answers one question type |
| **Consistent Contextual Linking** | Grafana | Every KPI links to logs/traces for same time window |
| **Metadata-Driven Filtering** | LangSmith | Filter by model, user, cost, latency |
| **Thread/Session Grouping** | Langfuse | Group traces by `thread_id` for multi-turn |
| **Playground Integration** | Langfuse | Jump from failed trace to prompt playground |
| **Annotation Queues** | LangSmith | Human review of production traces |
| **Framework-Agnostic (OTEL)** | Langfuse/Arize Phoenix | Vendor-neutral trace visualization |

### Compliance Dashboard Best Practices

| Pattern | Source | Application |
|---|---|---|
| **Timeline Visualization** | react-admin `ra-audit-log` | Chronological event lists for audit |
| **Metric Cards (North Star KPIs)** | Enterprise dashboards | Top-of-page critical metrics |
| **XAI Overlays** | AI governance dashboards | Hover-based decision explanations |
| **Action-Driven Modules** | Compliance platforms | Execute remediation from dashboard |
| **Role-Based Views** | MetricStream, Collibra | Different layouts per persona |
| **Append-Only Audit Logs** | SOC2 best practices | Tamper-proof event chains |
| **Export Capabilities** | React-Admin Enterprise | CSV/JSON/PDF for auditors |

---

## Open Questions

1. **Deployment model:** Is this UI for local dev use only (reading from `cache/` and `logs/` on disk), or should it also work against a deployed agent (reading from a remote API/database)?

2. **Real-time vs. historical:** Do we need live streaming of logs/traces as the agent runs, or is post-mortem analysis sufficient? (Affects architecture: SSE/WebSocket vs. REST polling)

3. **Multi-agent visualization:** `TrustTraceRecord` has `source_agent_id` and `causation_id` for multi-agent correlation. Do we want to visualize cross-agent causal chains?

4. **MVP scope:** Should we build all seven modules, or start with a focused MVP? Suggested MVP: Dashboard + Trace Explorer + Guardrail Monitor.

5. **Integration with existing frontend:** Should this be:
   - (a) A separate app/route within the same Next.js project?
   - (b) A completely separate React app (e.g., Vite + React)?
   - (c) Embedded panels within the existing chat UI?

6. **Authentication:** Should this dashboard be behind WorkOS auth, or is it a dev-only tool?

7. **Data volume expectations:** How many workflow runs per day? This affects whether file-based storage (JSONL) is sufficient or if we need a proper database (Postgres, ClickHouse).

8. **Compliance frameworks:** Are we targeting specific standards (SOC 2, ISO 27001, EU AI Act, NIST AI RMF)? This shapes the compliance center's export format.
