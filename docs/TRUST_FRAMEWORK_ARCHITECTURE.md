# Seven-Layer Agent Trust Framework -- High-Level Architecture

**Analysis method:** Pyramid Principle with MECE decomposition
**Source documents:**
- `agent/TrustFrameworkAnd Governance.md` (Seven-Layer Agent Trust Framework)
- `agent/docs/LAYER1_IDENTITY_ANALYSIS.md` (Layer 1 structured analysis)
- `agent/docs/STYLE_GUIDE_LAYERING.md` (Composable layering architecture)
- `agent/docs/STYLE_GUIDE_PATTERNS.md` (Design patterns catalog)
- `agent/PLAN.md` (ReAct agent architecture)
- `agent/research/pyramid_react_system_prompt.md` (Analysis protocol)

---

## Governing Thought

The seven-layer trust framework is not a monolithic stack -- it is a **three-dimensional grid** where each layer operates across multiple enforcement planes, serves one of two trust scopes, and participates in a bidirectional data-and-control flow. The architecture maps onto the composable layering model by treating **agent trust layers (L1-L5) as vertical concerns with technical enforcement** and **ecosystem trust layers (L6-L7) as orchestration/meta concerns with process enforcement**, all consuming a shared set of horizontal trust infrastructure services.

---

## Part 1: Architecture Overview

### Dimension 1: Enforcement Planes

Every trust layer has a primary enforcement moment, but most layers span multiple planes. This is the critical distinction from a naive "stack" reading of the framework.

```
                    DESIGN-TIME          DEPLOY-TIME          RUNTIME             POST-HOC
                    ───────────          ───────────          ───────             ────────
 L1 Identity        Define identity      Issue credentials,   Verify before       Audit identity
                    schema, select       register in          execute (sync       events, detect
                    crypto model         registry, bind to    blocking), mTLS     orphans/drift
                                         org structure        handshake

 L2 Authorization   Define roles,        Bind permissions     Evaluate access     Review access
                    declare RBAC/ABAC    to identity,         per-request         logs, detect
                    policy structure     issue tokens         (OPA-style),        privilege drift
                                                              sandbox enforcement

 L3 Purpose &       Author purpose       Store in registry    LLM self-checks     Measure deviation
    Policy           declarations,        bound to L1          against declared    from declared
                    write policy         identity             purpose/policy      purpose over time
                    constraints

 L4 Task Planning   Define plan schema,  Configure plan       Capture plan        Reconstruct
    & Explainability explainability       logging infra        before execution,   decision rationale,
                    requirements                              record tool         explain to auditors
                                                              selection rationale

 L5 Observability   Define trace         Attach trace         Emit structured     Forensic analysis,
    & Traceability   schema, configure    correlation IDs,     logs, correlate     compliance reports,
                    log routing          wire dashboards      across agents       anomaly detection

 L6 Certification   Define evaluation    Run certification    (Primarily post-    Re-evaluate on
    & Compliance     criteria, build      suite before         hoc, but runtime    change, periodic
                    test harnesses       deployment gate      monitors feed       recertification,
                                                              signals)            judge scoring

 L7 Governance &    Define governance    Assign agent         Quarantine on       Recertification
    Lifecycle        board structure,     owners, set          policy violation,   triggers,
                    write lifecycle      review cadence       escalate incidents  decommissioning,
                    policies                                                      archive
```

**Key architectural insight**: Layers L1, L2, and L5 are "always-on" -- they enforce at every plane. Layers L3 and L4 are strongest at design-time and runtime. Layers L6 and L7 are strongest at deploy-time and post-hoc. This means the runtime enforcement engine must compose L1 + L2 + L5 into a single "verify-authorize-log" pipeline that executes on every agent action.

---

### Dimension 2: Trust Scope Boundary

The framework splits into two architecturally distinct zones:

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                          AGENT TRUST (L1-L5)                                       │
│                                                                                    │
│  Enforced by: TECHNICAL CONTROLS (code, cryptography, validators, logging)         │
│  Granularity: Per-agent, per-action                                                │
│  Latency requirement: Synchronous, sub-millisecond for L1/L2                       │
│  Implementation: Horizontal services + vertical component hooks                    │
│                                                                                    │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────┐   │
│  │    L1    │  │     L2       │  │    L3    │  │    L4      │  │     L5       │   │
│  │ Identity │──│Authorization │──│ Purpose  │──│Explainab.  │──│Observability │   │
│  │          │  │              │  │& Policy  │  │            │  │              │   │
│  └──────────┘  └──────────────┘  └──────────┘  └────────────┘  └──────────────┘   │
│       ▲                                                              │              │
│       │                    feeds data upward                         │              │
├───────┼──────────────────────────────────────────────────────────────┼──────────────┤
│       │                                                              ▼              │
│  ┌────┴──────────────────────────────────────────────────────────────────────────┐  │
│  │                      ECOSYSTEM TRUST (L6-L7)                                  │  │
│  │                                                                                │  │
│  │  Enforced by: PROCESS CONTROLS (governance boards, certification workflows,    │  │
│  │               recertification triggers, lifecycle state machines)               │  │
│  │  Granularity: Per-agent-type or fleet-wide                                     │  │
│  │  Latency requirement: Asynchronous (minutes to days)                           │  │
│  │  Implementation: Meta-layer orchestration (analogous to meta/ in PLAN.md)      │  │
│  │                                                                                │  │
│  │  ┌────────────────────────┐  ┌────────────────────────────────┐                │  │
│  │  │         L6             │  │            L7                   │                │  │
│  │  │  Certification &       │──│  Governance & Lifecycle         │                │  │
│  │  │  Compliance            │  │  Management                    │                │  │
│  │  └────────────────────────┘  └────────────────────────────────┘                │  │
│  │       │                                    │                                    │  │
│  │       │         control flows downward      │                                    │  │
│  │       ▼                                    ▼                                    │  │
│  │  Revoke identity (L1), Suspend access (L2), Trigger re-evaluation (L6)         │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

**Architectural consequence**: Agent trust (L1-L5) maps to the existing three-layer grid -- horizontal services (identity verification, authorization checks, logging) consumed by vertical agent components. Ecosystem trust (L6-L7) maps to a separate meta-layer (like `meta/` in PLAN.md) that operates offline on accumulated data and produces governance decisions that cascade downward.

---

### Dimension 3: Data and Control Flow

Data flows upward through the stack. Control flows downward. This bidirectional dependency is what makes the framework more than a linear pipeline.

```
                         DATA FLOWS UP                    CONTROL FLOWS DOWN
                         ─────────────                    ──────────────────

   L7 Governance    ◄── lifecycle decisions,         ──► revoke identity (L1)
                        recertification triggers          suspend access (L2)
                               ▲                          update policies (L3)
                               │                          trigger recertification (L6)
                               │                                │
   L6 Certification ◄── certification status,        ──► deployment gate (go/no-go)
                        compliance reports                 rollback permissions (L2)
                               ▲                                │
                               │                                │
   L5 Observability ◄── traces, audit logs,          ──► alert on anomaly
                        dashboards, anomaly signals        quarantine agent (L2)
                               ▲                                │
                               │                                │
   L4 Explainability◄── task plans, decision         ──► (advisory: informs L5
                        rationale, tool selection            logging schema)
                               ▲                                │
                               │                                │
   L3 Purpose &     ◄── purpose declarations,        ──► (advisory: informs L2
      Policy            policy constraints                  authorization rules)
                               ▲                                │
                               │                                │
   L2 Authorization ◄── access tokens, permission    ──► deny/allow/throttle
                        grants, policy evaluations           per-request decisions
                               ▲                                │
                               │                                │
   L1 Identity      ◄── identity cards, credentials  ──► (foundation: consumed
                        signature hashes                    by all layers above)
```

**The three feedback loops that the architecture must support:**

1. **L5 -> L2 (Runtime feedback)**: Observability detects an anomaly -> authorization suspends the agent's access in real time. This is the "quarantine" pattern from the trust framework.

2. **L6 -> L1/L2 (Certification feedback)**: Certification fails or expires -> identity is suspended (L1), permissions are rolled back (L2). This is the "decertification" cascade.

3. **L7 -> L6 (Governance feedback)**: Governance board decides an agent must be recertified (due to update, drift, or policy change) -> triggers the L6 certification pipeline. This is the "recertification trigger."

---

### Mapping to the Composable Layering Grid

The trust framework maps onto the existing composable architecture:

```
                 TRUST FRAMEWORK LAYER                    COMPOSABLE GRID PLACEMENT
                 ─────────────────────                    ─────────────────────────

                 ┌──────────────────────────────────────────────────────────────────┐
                 │            META-LAYER (offline, process controls)                 │
    L7           │  governance/                                                      │
    L6           │    lifecycle_manager.py    -- agent state machine, decommission   │
                 │    certification.py        -- evaluation suite, pass/fail gates   │
                 │    compliance_reporter.py  -- audit export, regulatory reports    │
                 │    recertification.py      -- drift-triggered re-evaluation       │
                 └──────────────────────────────────────────────────────────────────┘
                        │ reads from ▼                         │ controls ▼
                 ┌──────────────────────────────────────────────────────────────────┐
                 │         ORCHESTRATION LAYER (topology only, thin wrappers)        │
                 │                                                                   │
                 │  verify_authorize_log_node  -- L1+L2+L5 composed into one gate   │
                 │  explain_plan_node          -- L4 plan capture before execution   │
                 │  (existing ReAct nodes: route, call_llm, execute_tool, evaluate) │
                 └──────────────────────────────────────────────────────────────────┘
                        │ delegates to ▼
                 ┌──────────────────────────────────────────────────────────────────┐
                 │         VERTICAL COMPONENTS (framework-agnostic domain logic)     │
                 │                                                                   │
    L3           │  purpose_checker.py    -- validates action against declared scope │
    L4           │  plan_builder.py       -- structures task plan before execution   │
                 │  (existing: router.py, evaluator.py, schemas.py)                 │
                 └──────────────────────────────────────────────────────────────────┘
                        │ consumes ▼
                 ┌──────────────────────────────────────────────────────────────────┐
                 │         HORIZONTAL SERVICES (domain-agnostic infrastructure)      │
                 │                                                                   │
    L1           │  identity_service.py      -- AgentFacts registry, verify(),       │
                 │                              signature computation                 │
    L2           │  authorization_service.py -- token validation, policy evaluation, │
                 │                              permission grants/denials             │
    L5           │  trace_service.py         -- correlation IDs, structured logging, │
                 │                              cross-agent trace linking             │
                 │  (existing: prompt_service, llm_config, guardrails, eval_capture) │
                 └──────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Per-Layer Architecture

Each layer's architecture follows a consistent structure: **interfaces** (what it consumes/produces), **enforcement mechanism**, **data contracts**, and **phase scope**.

---

### Layer 1: Identity and Authentication

*Full decomposition in [LAYER1_IDENTITY_ANALYSIS.md](LAYER1_IDENTITY_ANALYSIS.md). Summary of interfaces for cross-layer integration:*

**Produces (consumed by all other layers):**

| Artifact | Type | Consumers |
|---|---|---|
| `AgentFacts` identity card | Pydantic model | L2 (permission binding), L3 (purpose binding), L5 (trace attribution), L6 (certification subject), L7 (lifecycle subject) |
| `signature_hash` | SHA256 string | L2 (verify-before-authorize), L5 (tamper detection in logs) |
| `status` field | `"active" \| "suspended" \| "revoked"` | L2 (access denied if not active), L6 (certification invalid if not active) |
| Audit trail entries | JSONL records | L5 (ingested into observability), L6 (evidence for certification), L7 (lifecycle history) |

**Consumes (from other layers):**

| Input | Source Layer | Purpose |
|---|---|---|
| Revocation command | L7 (governance) | Permanently invalidate identity |
| Suspension command | L6 (certification failure) or L7 | Temporarily invalidate identity |
| Restoration command | L7 (after investigation) | Restore suspended identity |

**Enforcement mechanism**: Horizontal service (`identity_service.py`). Synchronous `verify()` on every agent action. SHA256 tamper detection over signed fields. Per the Layer 1 analysis: split `signed_metadata` (governance-grade) from `metadata` (operational).

---

### Layer 2: Authorization and Access Control

**Issue tree:**

```
Root: How does the system enforce that agents act within authorized bounds?
│
├── Branch 1: Permission Model
│   (What structures define what an agent can/cannot do?)
│   ├── 1a: Role definitions (RBAC roles mapped to agent capabilities)
│   └── 1b: Attribute-based rules (ABAC contextual conditions)
│
├── Branch 2: Token Lifecycle
│   (How are permissions granted, scoped, and revoked?)
│   ├── 2a: Token issuance (OAuth2-style, scoped, time-bounded)
│   ├── 2b: Token validation (per-request verification)
│   └── 2c: Token revocation (on suspension, recertification failure)
│
├── Branch 3: Runtime Policy Evaluation
│   (How are access decisions made in real-time?)
│   ├── 3a: Policy engine integration (OPA-style evaluate on each action)
│   ├── 3b: Contextual decisions (identity + task context + environment)
│   └── 3c: Response actions (deny, throttle, quarantine)
│
└── Branch 4: Zero-Trust Enforcement
    (How is the "never trust, always verify" principle implemented?)
    ├── 4a: Default-deny posture (agents start with no permissions)
    └── 4b: Continuous verification (no cached trust, verify per-interaction)
```

**Produces:**

| Artifact | Type | Consumers |
|---|---|---|
| Access decision (allow/deny/throttle) | Boolean + reason | Orchestration layer (gate node) |
| Permission grant records | Structured log | L5 (observability), L6 (certification evidence) |
| Quarantine signals | Event | L1 (suspend identity), L5 (alert), L7 (escalation) |

**Consumes:**

| Input | Source Layer | Purpose |
|---|---|---|
| Identity + signature validity | L1 | Prerequisite for any authorization decision |
| Purpose declaration + policies | L3 | Authorization rules derived from declared scope |
| Anomaly signals | L5 | Trigger quarantine or permission rollback |
| Permission rollback commands | L6/L7 | Revoke access on certification failure |

**Enforcement mechanism**: Horizontal service (`authorization_service.py`). Composed with L1 into a single `verify_then_authorize()` call. The existing Pydantic validators on tools (command allowlist, path sandboxing from PLAN.md) are L2 controls at the tool level. The new authorization service adds agent-level access control above the tool level.

**Design decision**: L2 composes with L1 at runtime into a single gate. The orchestration layer calls `verify_then_authorize(agent_id, action, context)` which internally calls `identity_service.verify(agent_id)` then `authorization_service.evaluate(identity, action, context)`. This is one thin-wrapper node, not two.

---

### Layer 3: Purpose and Policies

**Issue tree:**

```
Root: How are agent purpose and policy constraints declared, stored, and enforced?
│
├── Branch 1: Purpose Declaration
│   (What structured format captures agent intent?)
│   ├── 1a: Schema (fields: scope, allowed_actions, excluded_actions)
│   └── 1b: Binding to identity (purpose stored as part of AgentFacts)
│
├── Branch 2: Policy Constraints
│   (How are behavioral boundaries expressed?)
│   ├── 2a: Structured policies (Pydantic models in AgentFacts.policies)
│   ├── 2b: Natural language policies (Jinja2 templates interpretable by LLM)
│   └── 2c: Policy precedence (regulatory > organizational > agent-specific)
│
└── Branch 3: Deviation Detection
    (How is purpose/policy violation detected?)
    ├── 3a: Pre-execution check (LLM self-check against declared purpose)
    └── 3b: Post-execution audit (L5 traces compared against L3 declarations)
```

**Produces:**

| Artifact | Type | Consumers |
|---|---|---|
| Purpose declaration | Structured text in AgentFacts | L2 (derives authorization rules), L4 (constrains plan scope), L6 (certification criteria) |
| Policy constraints | `list[Policy]` in AgentFacts | L2 (enforcement rules), L4 (plan boundaries), L5 (deviation benchmark) |
| Deviation events | Structured log | L5 (alert), L6 (certification evidence), L7 (governance escalation) |

**Consumes:**

| Input | Source Layer | Purpose |
|---|---|---|
| Identity card | L1 | Purpose bound to specific agent identity |
| Task plan | L4 | Pre-execution scope check: "is this plan within declared purpose?" |
| Governance policy updates | L7 | New organizational policies that override agent-specific ones |

**Enforcement mechanism**: Dual. (1) **Structural**: Purpose and policies are `signed_metadata` fields in AgentFacts -- changing them requires re-registration and re-signing, which triggers L6 recertification. (2) **Runtime**: The LLM receives purpose and policy constraints as part of its system prompt (via `PromptService` -- the H1 pattern). The L4 plan builder checks proposed actions against declared scope before execution.

**Design decision**: L3 is primarily a **data layer**, not a service. Purpose and policies are stored in AgentFacts (L1 registry) and consumed by L2 (authorization rules), L4 (plan constraints), and L6 (certification criteria). The "enforcement" of L3 happens through L2 and L4, not through a separate L3 service. This avoids creating a redundant enforcement point.

---

### Layer 4: Task Planning and Explainability

**Issue tree:**

```
Root: How does the system make agent reasoning visible and auditable?
│
├── Branch 1: Plan Structure
│   (What is captured before execution?)
│   ├── 1a: Step sequence (ordered actions with dependencies)
│   ├── 1b: Tool/collaborator selection rationale
│   └── 1c: Parameter construction logic
│
├── Branch 2: Explainability Artifacts
│   (What is recorded during and after execution?)
│   ├── 2a: Reasoning trace (already in PLAN.md's AgentState.reasoning_trace)
│   ├── 2b: Decision rationale (why this tool, why this model, why this approach)
│   └── 2c: Hypothesis tracking (what was expected vs. what was found)
│
└── Branch 3: Pre-Execution Scope Validation
    (How is the plan checked against L3 before execution?)
    ├── 3a: Purpose alignment check (is each step within declared scope?)
    └── 3b: Policy constraint check (does any step violate a declared policy?)
```

**Produces:**

| Artifact | Type | Consumers |
|---|---|---|
| Task plan (pre-execution) | Structured object (steps, tools, rationale) | L5 (logged for traceability), L6 (evidence of deliberate action) |
| Reasoning trace (during execution) | `list[str]` in AgentState | L5 (correlated with outcomes), L6 (certification evidence) |
| Step results (post-execution) | `list[StepResult]` | L5 (audit trail), L6 (evaluation data) |

**Consumes:**

| Input | Source Layer | Purpose |
|---|---|---|
| Purpose and policies | L3 | Scope boundaries for plan validation |
| Identity + permissions | L1 + L2 | What tools/actions the agent is authorized to use in the plan |

**Enforcement mechanism**: Vertical component (`plan_builder.py`). This is domain logic -- it belongs in the vertical layer, not horizontal, because different agent types may plan differently. The orchestration layer adds an `explain_plan_node` that captures the plan structure before `execute_tool_node` runs. This extends the existing ReAct cycle:

```
guard_input -> route -> call_llm -> [explain_plan] -> execute_tool -> evaluate
```

The `explain_plan` node is a thin wrapper that calls `plan_builder.capture_plan(state)` and `purpose_checker.validate_scope(plan, agent_facts)`. If the plan violates declared scope, the node short-circuits to `evaluate` with a policy violation outcome.

---

### Layer 5: Observability and Traceability

**Issue tree:**

```
Root: How does the system provide persistent, correlated visibility into agent behavior?
│
├── Branch 1: Structured Logging
│   (How are individual events captured?)
│   ├── 1a: Per-concern log streams (already in PLAN.md: prompts, guards, evals, tools, routing)
│   ├── 1b: Trust-specific log streams (identity events, authorization decisions, policy checks)
│   └── 1c: Schema unification (common fields across all streams)
│
├── Branch 2: Trace Correlation
│   (How are related events connected across agents and steps?)
│   ├── 2a: Task-level correlation (task_id linking all steps in one task)
│   ├── 2b: Cross-agent correlation (parent_task_id for delegated work)
│   └── 2c: Lifecycle correlation (agent_id linking all events for one agent over time)
│
├── Branch 3: Real-Time Monitoring
│   (How are system-wide patterns surfaced?)
│   ├── 3a: Dashboards (activity levels, success rates, error rates, cost)
│   ├── 3b: Alerting (threshold breach, anomaly detection, quarantine triggers)
│   └── 3c: Policy enforcement signals (feed anomalies back to L2 for quarantine)
│
└── Branch 4: Audit Infrastructure
    (How is evidence preserved for compliance?)
    ├── 4a: Tamper-resistant storage (append-only JSONL, integrity hashes)
    └── 4b: Export for compliance (structured reports for L6/L7 consumption)
```

**Produces:**

| Artifact | Type | Consumers |
|---|---|---|
| Correlated trace records | JSONL with task_id, agent_id, step, timestamp | L6 (certification evidence), L7 (lifecycle history) |
| Anomaly signals | Events | L2 (quarantine trigger), L7 (governance escalation) |
| Compliance export | Structured JSON/CSV | L6 (evaluation input), external auditors |
| Dashboards | Read-only views | L7 (governance oversight) |

**Consumes:**

| Input | Source Layer | Purpose |
|---|---|---|
| Identity metadata | L1 | Attribute every log record to a specific agent |
| Authorization decisions | L2 | Log access grants and denials |
| Task plans and reasoning | L4 | Log explainability artifacts |
| All agent actions | All layers | Universal logging of every event |

**Enforcement mechanism**: Horizontal service (`trace_service.py`). This extends the existing `eval_capture.py` and `observability.py` from PLAN.md. The key addition is a **unified trace schema** that all layers emit to:

```python
class TrustTraceRecord(BaseModel):
    schema_version: int = 1
    timestamp: datetime
    trace_id: str           # correlates all events in one task
    agent_id: str           # from L1 identity
    layer: str              # "L1" | "L2" | "L3" | "L4" | "L5" | "L6" | "L7"
    event_type: str         # "identity_verified" | "access_granted" | "plan_captured" | ...
    details: dict           # layer-specific payload
    outcome: str | None     # "pass" | "fail" | "alert" | None
```

This is the shared schema that makes cross-layer queries possible: "show me all L2 access denials for agent X in the last 24 hours" or "show me the L4 plan that preceded this L5 anomaly."

---

### Layer 6: Certification and Compliance

**Issue tree:**

```
Root: How are agents evaluated and certified for safe operation?
│
├── Branch 1: Evaluation Process
│   (How is an agent tested against trust criteria?)
│   ├── 1a: Automated test suite (stress tests, edge cases, adversarial inputs)
│   ├── 1b: LLM-as-judge scoring (already in PLAN.md's meta/judge.py)
│   └── 1c: Evaluation criteria (derived from L3 purpose + L2 permissions)
│
├── Branch 2: Certification Decisions
│   (How is the pass/fail determination made?)
│   ├── 2a: Scoring thresholds (minimum scores per dimension)
│   ├── 2b: Certification status (certified | provisional | failed | expired)
│   └── 2c: Certification records (timestamped, signed, stored in registry)
│
├── Branch 3: Recertification Triggers
│   (What events require re-evaluation?)
│   ├── 3a: Agent change (version update, capability addition, policy change)
│   ├── 3b: Environmental change (new regulations, organizational policy update)
│   ├── 3c: Drift detection (L5 anomaly signals, score drift from meta/drift.py)
│   └── 3d: Time-based (periodic schedule: every N months)
│
└── Branch 4: Deployment Gate
    (How does certification block or allow deployment?)
    ├── 4a: Pre-deployment gate (certification required before onboarding)
    └── 4b: Continuous compliance (runtime signals can revoke certification)
```

**Produces:**

| Artifact | Type | Consumers |
|---|---|---|
| Certification status | `"certified" \| "provisional" \| "failed" \| "expired"` | L2 (deployment gate), L7 (governance dashboard) |
| Evaluation reports | Structured JSON (scores, failure categories, evidence) | L7 (governance decisions), external auditors |
| Recertification signals | Events | L7 (trigger governance review) |

**Consumes:**

| Input | Source Layer | Purpose |
|---|---|---|
| Agent identity and metadata | L1 | Subject of certification |
| Purpose and policies | L3 | Evaluation criteria |
| Trace records and audit logs | L5 | Evidence for evaluation |
| Governance commands | L7 | Trigger recertification |

**Enforcement mechanism**: Meta-layer component (`governance/certification.py`). This extends the existing `meta/run_eval.py` and `meta/judge.py` from PLAN.md. It operates asynchronously -- certification runs are triggered by events (deployment request, agent update, drift signal, time schedule), not on every agent action.

**Design decision**: Certification status is stored as a field on the AgentFacts identity card: `certification_status: "certified" | "provisional" | "failed" | "expired"`. The L2 authorization service checks this field as part of the `verify_then_authorize()` gate. An agent with `certification_status == "failed"` is denied execution at L2, even if its L1 identity is valid and its permissions are intact. This is how L6 cascades downward through L2 to L1.

---

### Layer 7: Governance and Lifecycle Management

**Issue tree:**

```
Root: How is trust sustained across agent lifecycles and organizational change?
│
├── Branch 1: Lifecycle State Machine
│   (What states can an agent be in, and what triggers transitions?)
│   ├── 1a: States (defined, building, onboarding, deployed, operating,
│   │        adapting, suspended, decommissioned)
│   └── 1b: Transition guards (what conditions must hold for each transition?)
│
├── Branch 2: Governance Structure
│   (Who has authority over agent lifecycle decisions?)
│   ├── 2a: Agent ownership (designated owner per agent, from AgentFacts.owner)
│   ├── 2b: Governance board (cross-functional authority for fleet-wide decisions)
│   └── 2c: Escalation paths (incident -> investigation -> decision -> action)
│
├── Branch 3: Continuous Governance
│   (How are governance decisions triggered and tracked?)
│   ├── 3a: Recertification scheduling (time-based + event-based triggers to L6)
│   ├── 3b: Policy evolution (new policies propagated to all affected agents)
│   └── 3c: Incident response (quarantine -> investigate -> restore or revoke)
│
└── Branch 4: Decommissioning
    (How are agents safely retired?)
    ├── 4a: Credential revocation (L1 revoke, L2 permission removal)
    ├── 4b: Log archival (L5 traces preserved for compliance retention)
    └── 4c: Orphan prevention (verify no active dependencies before retirement)
```

**Produces:**

| Artifact | Type | Consumers |
|---|---|---|
| Lifecycle state transitions | Events | L1 (revoke/suspend/restore), L2 (permission changes), L5 (logged), L6 (recertification triggers) |
| Governance decisions | Structured records | L5 (audit trail), L6 (trigger re-evaluation) |
| Decommissioning commands | Cascading events | L1 (revoke), L2 (purge permissions), L5 (archive traces) |

**Consumes:**

| Input | Source Layer | Purpose |
|---|---|---|
| Certification results | L6 | Certification pass/fail drives lifecycle decisions |
| Anomaly signals | L5 | Trigger governance investigation |
| Agent metadata | L1 | Subject of governance decisions |
| Policy declarations | L3 | Basis for compliance evaluation |

**Enforcement mechanism**: Meta-layer orchestration (`governance/lifecycle_manager.py`). This is the highest-level orchestrator -- it doesn't operate on individual agent actions but on agent lifecycle events. It consumes L5 dashboards and L6 certification results, and emits commands that cascade to L1 (revoke/suspend), L2 (revoke permissions), and L6 (trigger recertification).

**Lifecycle state machine:**

```
                              ┌──────────────────────────────────────────────────┐
                              │                                                   │
    ┌─────────┐  define  ┌───▼─────┐  build   ┌──────────┐  onboard  ┌────────┐ │
    │ DEFINED │─────────►│BUILDING │────────►│ONBOARDING│──────────►│DEPLOYED│ │
    └─────────┘          └─────────┘         └──────────┘           └───┬────┘ │
                                                   ▲                     │      │
                                                   │ restore             │      │
                                              ┌────┴─────┐  suspend    │      │
                                              │SUSPENDED  │◄───────────┤      │
                                              └────┬─────┘             │      │
                                                   │ revoke       deploy│      │
                                                   ▼                    ▼      │
                                            ┌────────────┐      ┌──────────┐  │
                                            │DECOMMISSION│◄─────│OPERATING │  │
                                            │    ED      │      └────┬─────┘  │
                                            └────────────┘           │        │
                                                   ▲            adapt│        │
                                                   │                 ▼        │
                                                   │          ┌──────────┐    │
                                                   └──────────│ ADAPTING │────┘
                                                    revoke    └──────────┘
                                                              recertify ──► L6
```

**Transition table:**

| Transition | Guard Condition | Side Effect |
|---|---|---|
| DEFINED -> BUILDING | Purpose and policies declared (L3) | Log lifecycle event |
| BUILDING -> ONBOARDING | Tests pass, build complete | Trigger L6 initial certification |
| ONBOARDING -> DEPLOYED | L6 certification passes, L1 identity issued, L2 permissions bound | Log deployment, start monitoring |
| DEPLOYED -> OPERATING | First successful execution | Activate L5 dashboards |
| OPERATING -> ADAPTING | Version update, capability change, or scheduled recertification | Trigger L6 re-evaluation |
| ADAPTING -> OPERATING | L6 recertification passes | Resume normal operation |
| OPERATING -> SUSPENDED | L5 anomaly, L6 failure, or governance decision | L1 suspend, L2 deny all access |
| SUSPENDED -> OPERATING | Investigation clears, L7 restores | L1 restore, L2 re-enable permissions |
| SUSPENDED -> DECOMMISSIONED | Investigation confirms retirement | L1 revoke, L2 purge, L5 archive |
| Any -> DECOMMISSIONED | Governance board decision | Full cleanup cascade |

---

## Part 3: Cross-Layer Integration

Three architectural mechanisms bind the layers together: the **runtime trust gate**, the **shared trace schema**, and the **certification cascade**.

---

### Integration 1: The Runtime Trust Gate (L1 + L2 + L5 Composed)

Every agent action passes through a single composed gate. This is one orchestration node, not three separate nodes, because the three checks are sequential dependencies:

```
                              verify_authorize_log(agent_id, action, context)
                              ─────────────────────────────────────────────
                                              │
                                              ▼
                              ┌──────────────────────────────┐
                              │  Step 1: IDENTITY (L1)       │
                              │  identity_service.verify()   │
                              │  - Recompute signature       │
                              │  - Check status == "active"  │
                              │  - Check valid_until          │
                              │                              │
                              │  FAIL → log + reject         │
                              └──────────────┬───────────────┘
                                              │ PASS
                                              ▼
                              ┌──────────────────────────────┐
                              │  Step 2: AUTHORIZE (L2)      │
                              │  authorization_service       │
                              │    .evaluate()               │
                              │  - Check certification_status│
                              │  - Evaluate RBAC/ABAC rules  │
                              │  - Check action against      │
                              │    declared purpose (L3)     │
                              │                              │
                              │  FAIL → log + deny/throttle  │
                              └──────────────┬───────────────┘
                                              │ PASS
                                              ▼
                              ┌──────────────────────────────┐
                              │  Step 3: LOG (L5)            │
                              │  trace_service.record()      │
                              │  - Emit TrustTraceRecord     │
                              │  - Correlate with trace_id   │
                              │  - Include L1 + L2 results   │
                              │                              │
                              │  (always executes, even on   │
                              │   L1/L2 failure)             │
                              └──────────────┬───────────────┘
                                              │
                                              ▼
                                        PROCEED / REJECT
```

This gate composes into the existing ReAct cycle as a pre-check:

```
[START] -> guard_input -> verify_authorize_log -> route -> call_llm -> ...
```

The gate runs once per task entry, and optionally before sensitive operations (tool execution). For tool execution, the existing Pydantic validators (command allowlist, path sandboxing) remain as a second defense layer -- they are L2 enforcement at the tool level, while the trust gate is L2 enforcement at the agent level.

---

### Integration 2: The Shared Trace Schema (L5 as Universal Bus)

L5 is not just one layer -- it is the **integration bus** that all other layers emit to. The `TrustTraceRecord` schema provides a common envelope:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    L5 TRACE SERVICE (Universal Bus)                       │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  TrustTraceRecord envelope                                       │    │
│  │  {trace_id, agent_id, timestamp, layer, event_type, details}    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Emitters:                          Consumers:                           │
│  ─────────                          ──────────                           │
│  L1: identity_verified,             L6: reads traces for certification   │
│      identity_suspended,                 evidence                        │
│      identity_revoked               L7: reads traces for governance      │
│  L2: access_granted,                     dashboards and lifecycle        │
│      access_denied,                      decisions                       │
│      agent_quarantined              Alerting: real-time anomaly          │
│  L3: purpose_checked,                   detection triggers L2            │
│      policy_violation                    quarantine                      │
│  L4: plan_captured,                 Compliance: export for               │
│      plan_validated,                     external auditors               │
│      plan_scope_violation                                                │
│  L6: certification_passed,                                               │
│      certification_failed,                                               │
│      recertification_triggered                                           │
│  L7: lifecycle_transition,                                               │
│      governance_decision                                                 │
│                                                                          │
│  Storage: append-only JSONL files + per-concern routing                  │
│  ─────────────────────────────────────────────────────                   │
│  trust_identity.log    (L1 events)                                       │
│  trust_authorization.log (L2 events)                                     │
│  trust_purpose.log     (L3 events)                                       │
│  trust_explainability.log (L4 events)                                    │
│  trust_certification.log  (L6 events)                                    │
│  trust_governance.log     (L7 events)                                    │
│  + existing: prompts.log, guards.log, evals.log, tools.log, routing.log │
└─────────────────────────────────────────────────────────────────────────┘
```

The per-concern log routing from PLAN.md's `logging.json` extends naturally -- each trust layer gets its own log stream, following the same H4 pattern.

---

### Integration 3: The Certification Cascade (L7 -> L6 -> L2 -> L1)

When a governance decision triggers recertification, the cascade flows through four layers:

```
  L7: Governance Decision
  ─────────────────────
  "Agent invoice-extractor-v2 must be recertified because:
   - Version updated from 2.1.0 to 2.2.0
   - signed_metadata changed (new capability added)"
          │
          ▼
  L6: Certification Pipeline
  ──────────────────────────
  1. Load agent's L3 purpose + policies
  2. Run automated test suite against current version
  3. Score with LLM-as-judge (meta/judge.py)
  4. Compare against thresholds
  5. Result: PASS or FAIL
          │
    ┌─────┴──────┐
    │             │
  PASS          FAIL
    │             │
    ▼             ▼
  L2: Maintain   L2: Suspend permissions
  permissions    authorization_service.suspend_all(agent_id)
    │             │
    ▼             ▼
  L1: Status     L1: Suspend identity
  unchanged      identity_service.suspend(agent_id, reason="certification_failed")
    │             │
    ▼             ▼
  L5: Log        L5: Log
  "recertified"  "certification_failed" + "suspended"
  Continue       ALERT to governance dashboard
  operating
```

**The reverse cascade (restoration):**

```
  L7: Governance restores after investigation
          │
          ▼
  L1: identity_service.restore(agent_id, reason="investigation_cleared")
          │
          ▼
  L2: authorization_service.restore_permissions(agent_id)
          │
          ▼
  L5: Log "restored" + "permissions_reinstated"
          │
          ▼
  Agent resumes operation
```

---

### Shared Infrastructure: The Agent Registry as Integration Point

The `AgentFactsRegistry` (from Layer 1) is the central integration point because it holds the data that multiple layers need:

| Registry Field | Owning Layer | Consuming Layers |
|---|---|---|
| `agent_id`, `agent_name`, `owner`, `version` | L1 | All layers (identification) |
| `signature_hash`, `signed_metadata` | L1 | L2 (verify before authorize), L5 (tamper detection) |
| `status` (active/suspended/revoked) | L1 (written by L7/L6) | L2 (access gate), L5 (logging), L6 (certification prerequisite) |
| `capabilities`, `policies` | L3 (authored at design-time) | L2 (authorization rules), L4 (plan scope), L6 (evaluation criteria) |
| `certification_status` | L6 (written after evaluation) | L2 (deployment gate), L7 (governance dashboard) |
| `lifecycle_state` | L7 (written on transitions) | L6 (recertification trigger), L2 (deployed check) |
| `valid_until` | L1 (set at registration) | L2 (expiry check), L7 (renewal scheduling) |
| Audit trail (JSONL) | L1 (per-agent) | L5 (ingested), L6 (certification evidence), L7 (lifecycle history) |

The registry is a **read-heavy, write-rare** store. Reads happen on every agent action (L1 verify, L2 authorize). Writes happen on lifecycle events (register, update, suspend, revoke, certify). This asymmetry means the registry can use file-based storage (as in the current AgentFacts tutorial) with an LRU cache for reads -- the design already validated in LAYER1_IDENTITY_ANALYSIS.md.

---

## Component Summary

| New Component | Grid Placement | Trust Layers Served | Primary Responsibility |
|---|---|---|---|
| `identity_service.py` | Horizontal service | L1 | AgentFacts registry, verify(), signature computation |
| `authorization_service.py` | Horizontal service | L2 | Token validation, policy evaluation, access decisions |
| `trace_service.py` | Horizontal service | L5 | TrustTraceRecord emission, correlation IDs, per-layer log routing |
| `purpose_checker.py` | Vertical component | L3 + L4 | Validate action/plan against declared purpose and policies |
| `plan_builder.py` | Vertical component | L4 | Capture task plan structure, record tool selection rationale |
| `certification.py` | Meta-layer | L6 | Evaluation suite, scoring, pass/fail gate, recertification triggers |
| `lifecycle_manager.py` | Meta-layer | L7 | State machine, transition guards, decommissioning, governance cascade |
| `compliance_reporter.py` | Meta-layer | L6 + L7 | Export traces for audit, generate compliance reports |

The existing components from PLAN.md (`guardrails.py`, `eval_capture.py`, `prompt_service.py`, `router.py`, `evaluator.py`) remain unchanged -- they are already correctly placed in the layered architecture. The trust framework adds new horizontal services and meta-layer components alongside them.
