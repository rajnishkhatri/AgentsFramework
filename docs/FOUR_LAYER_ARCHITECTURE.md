# Four-Layer Architecture with Trust Foundation

**Analysis method:** Feasibility integration of Trust Framework (L1 Identity) with Composable Layering Architecture
**Source documents:**
- `agent/docs/TRUST_FRAMEWORK_ARCHITECTURE.md` (Seven-Layer Agent Trust Framework)
- `agent/docs/LAYER1_IDENTITY_ANALYSIS.md` (Layer 1 structured analysis)
- `agent/docs/STYLE_GUIDE_LAYERING.md` (Composable layering architecture -- three-layer grid)
- `agent/docs/STYLE_GUIDE_PATTERNS.md` (Design patterns catalog)

**External references:**
- [Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit) -- Nine-package monorepo separating identity models (AgentMesh) from policy engine (Agent OS)
- [Agent Identity Protocol (AIP)](https://github.com/openagentidentityprotocol/agentidentityprotocol) -- Two-layer design: identity documents vs. enforcement proxy
- [NANDA Index / AgentFacts spec](https://github.com/agentfacts/agentfacts-spec) -- Three-layer registry: lean index, AgentFacts metadata, dynamic resolution
- [CSA Agentic Trust Framework](https://cloudsecurityalliance.org/blog/2026/02/02/the-agentic-trust-framework-zero-trust-governance-for-ai-agents) -- Zero Trust governance specification for AI agents
- DDD Shared Kernel pattern -- Centralized domain models imported by multiple bounded contexts
- [ESAA: Event Sourcing for Autonomous Agents](https://arxiv.org/abs/2602.23193) -- Append-only event log with deterministic replay and projection verification for LLM-based agents
- [Governance-as-a-Service (GaaS)](https://arxiv.org/abs/2508.18765) -- Modular runtime enforcement layer with Trust Factor scoring for multi-agent compliance
- [AgentCity: Constitutional Governance](https://arxiv.org/abs/2604.07007) -- Separation of Power model with EMA reputation scoring and on-chain audit trails
- [Confluent: Four Design Patterns for Event-Driven Multi-Agent Systems](https://www.confluent.io/blog/event-driven-multi-agent-systems/) -- Orchestrator-Worker, Hierarchical, Blackboard, Market-Based patterns
- Hexagonal Architecture (Ports and Adapters) -- Alistair Cockburn; structural pattern for isolating domain logic from infrastructure
- [Apache Libcloud exception hierarchy](https://libcloud.readthedocs.io/en/latest/apidocs/libcloud.common.types.html) -- Domain-categorized exception tree pattern (`LibcloudError` -> `ProviderError` -> `InvalidCredsError`)

---

## Governing Thought

The original three-layer composable grid (horizontal services, vertical components, orchestration) requires a **fourth foundational layer** to support the trust framework. Trust models (`AgentFacts`, `Capability`, `Policy`, `TrustTraceRecord`, signature logic) are neither horizontal services nor vertical components -- they are **portable trust artifacts** consumed by every layer. Placing them in a dependency-free foundation follows the same pattern used by Microsoft's Agent Governance Toolkit (identity model separate from policy engine), AIP (identity document separate from enforcement proxy), and the DDD Shared Kernel (types shared across bounded contexts with zero outward dependencies).

---

## Architectural Identity

The Four-Layer Architecture is a **layered onion with hexagonal ports and event-driven governance feedback**. The Trust Foundation is the domain core (innermost ring of the onion). The `typing.Protocol` definitions (`IdentityProvider`, `PolicyProvider`, `CredentialProvider`, `PolicyBackend`) are hexagonal ports. Cloud provider adapters (`utils/cloud_providers/`) and policy backend adapters (`utils/policy_backends/`) are the hexagonal adapters that plug into those ports. The orchestration layer is the driving side that composes services into use cases. Dependencies point exclusively inward -- no inner layer imports from an outer layer.

Governance feedback uses **event-driven communication via direct method calls in Phase 1**. The `TrustTraceRecord` is the event. Governance consumers (`governance/event_consumers.py`) react to trust events by calling horizontal services directly (Meta-Layer -> Horizontal is permitted by the dependency table). In Phase 2, direct calls evolve to event bus subscriptions; in Phase 3, the in-process bus evolves to a distributed bus for multi-agent coordination. The event schema, the governance logic, and the feedback loop definitions remain unchanged across all three phases -- only the transport mechanism changes.

**Abstraction introduction principle:** Introduce protocols, buses, and event sourcing only when the second consumer arrives. A single-orchestrator pipeline does not need an `EventBus` protocol -- direct method calls are simpler, debuggable, and sufficient. The architecture *documents* future abstractions now (so the door stays open) but does not *build* them until the need materializes. This follows YAGNI applied to architecture: design for extension, implement on demand.

---

## The Problem with Three Layers

The original Style Guide Layering defines three layers:

1. **Horizontal Services** (`utils/`) -- domain-agnostic infrastructure (prompt rendering, logging, guardrails)
2. **Vertical Components** (`agents/`) -- domain-specific pipeline stages (writers, reviewers, classifiers)
3. **Orchestration Layer** -- topology-only thin wrappers connecting verticals

When integrating the trust framework (starting with L1 Identity), the `AgentFacts` Pydantic model needs to be imported by:
- `identity_service.py` (horizontal -- stores and retrieves identity cards)
- `authorization_service.py` (horizontal -- reads capabilities and status for access decisions)
- `trace_service.py` (horizontal -- reads agent_id for trace attribution, verifies signatures for tamper detection)
- `purpose_checker.py` (vertical -- reads policies and capabilities for scope validation)
- `certification.py` (meta-layer -- reads identity for evaluation, writes certification status)
- `lifecycle_manager.py` (meta-layer -- reads/writes lifecycle state)

If `AgentFacts` lives inside `identity_service.py` (horizontal), then other horizontal services import from a peer -- creating hidden coupling. If it lives in `agents/` (vertical), horizontal services import from vertical -- **forbidden** by the style guide. If it lives in the orchestration layer, everything imports upward -- **forbidden**.

The model has no valid home in a three-layer grid.

---

## The Four-Layer Grid

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  META-LAYER (offline, process controls)                                  │
  │  governance/                                                             │
  │    lifecycle_manager.py    certification.py    compliance_reporter.py     │
  └────────────────────────────────┬─────────────────────────────────────────┘
                                   │
  ┌────────────────────────────────┴─────────────────────────────────────────┐
  │  ORCHESTRATION LAYER (topology only, thin wrappers)                      │
  │  verify_authorize_log_node    explain_plan_node    (existing ReAct nodes)│
  └────────────────────────────────┬─────────────────────────────────────────┘
                                   │
  ┌────────────────────────────────┴─────────────────────────────────────────┐
  │  VERTICAL COMPONENTS (framework-agnostic domain logic)                   │
  │  purpose_checker    plan_builder    router    evaluator    schemas        │
  └────────────────────────────────┬─────────────────────────────────────────┘
                                   │
  ┌────────────────────────────────┴─────────────────────────────────────────┐
  │  HORIZONTAL SERVICES (domain-agnostic infrastructure)                    │
  │  identity_service    authorization_service    trace_service              │
  │  prompt_service    llm_config    guardrails    eval_capture    memory     │
  └────────────────────────────────┬─────────────────────────────────────────┘
                                   │
  ═══════════════════════════════════════════════════════════════════════════
                                   │
  ┌────────────────────────────────┴─────────────────────────────────────────┐
  │  TRUST FOUNDATION (shared kernel -- models, schemas, crypto)             │
  │  trust/                                                                  │
  │    models.py          AgentFacts, Capability, Policy, AuditEntry         │
  │    enums.py           CertificationStatus, LifecycleState                │
  │    trace_schema.py    TrustTraceRecord                                   │
  │    signature.py       compute_signature(), verify_signature()            │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## Trust Foundation Layer

### What Belongs Here

The trust foundation contains **types and pure functions** that define the trust domain. It is the single source of truth for trust-related data structures.

A component belongs in the trust foundation if it satisfies **all** of these criteria:

1. **Pure**: No I/O, no storage, no network, no logging. Only data models (Pydantic) and deterministic functions.
2. **Shared**: Consumed by two or more layers above. If only one service needs a type, it stays in that service.
3. **Stable**: Changes less frequently than the services that consume it. Schema changes are deliberate and trigger re-signing (per Layer 1 Analysis H3a).
4. **Dependency-free**: Zero imports from horizontal, vertical, orchestration, or meta-layer code.

### Contents

#### `trust/models.py` -- Identity and Governance Data Models

| Model | Purpose | Consumers |
|-------|---------|-----------|
| `AgentFacts` | Pydantic model: the agent identity card | identity_service (CRUD), authorization_service (reads capabilities/status), trace_service (reads agent_id), certification (reads for evaluation), lifecycle_manager (reads/writes state) |
| `Capability` | Value object: what an agent can do | AgentFacts field, authorization_service (derives rules), purpose_checker (scope validation) |
| `Policy` | Value object: behavioral constraints | AgentFacts field, authorization_service (enforcement rules), purpose_checker (plan boundaries) |
| `AuditEntry` | Value object: change record schema | identity_service (appends entries), trace_service (ingests into observability), certification (evidence) |
| `VerificationReport` | Value object: bulk verify results | identity_service (produces), governance (consumes for fleet health) |

#### `trust/enums.py` -- Trust State Enumerations

| Enum | Values | Consumers |
|------|--------|-----------|
| `IdentityStatus` | `active`, `suspended`, `revoked` | identity_service (lifecycle), authorization_service (gate check), trace_service (log attribution). See [Dual State Machine Contract](#dual-state-machine-contract) for interaction with `LifecycleState`. |
| `CertificationStatus` | `certified`, `provisional`, `failed`, `expired` | certification (writes), authorization_service (deployment gate), governance dashboard |
| `LifecycleState` | `defined`, `building`, `onboarding`, `deployed`, `operating`, `adapting`, `suspended`, `decommissioned` | lifecycle_manager (state machine), certification (recertification trigger). See [Dual State Machine Contract](#dual-state-machine-contract) for interaction with `IdentityStatus`. |
| `EventCategory` | `identity`, `authorization`, `credential`, `governance`, `execution` | trace_service (log routing and filtering), governance event_consumers (subscription targeting), compliance_reporter (category-filtered audit export) |

#### Event Type Taxonomy

`EventCategory` classifies every `TrustTraceRecord.event_type` into a MECE routing category. Consumers subscribe to categories rather than individual event types, decoupling consumer logic from the growing set of specific events.

| Category | Event Types | Primary Consumer |
|---|---|---|
| `identity` | `identity_registered`, `identity_verified`, `identity_suspended`, `identity_revoked`, `identity_restored` | `lifecycle_manager`, compliance dashboard |
| `authorization` | `access_granted`, `access_denied`, `agent_quarantined`, `policy_evaluated` | `trust_scoring`, anomaly detector |
| `credential` | `credential_issued`, `credential_refreshed`, `credential_evicted`, `credential_expired` | `credential_cache`, audit system |
| `governance` | `lifecycle_transition`, `governance_decision`, `recertification_triggered`, `trust_score_updated` | `certification`, `compliance_reporter` |
| `execution` | `plan_captured`, `plan_validated`, `tool_executed`, `purpose_checked` | `trace_service`, explainability |

**Classification convention:** Each `event_type` maps to exactly one `EventCategory`. The mapping is defined in `trust/enums.py` as a dict or method on the enum. If a new event type could fit two categories, classify by the **originating layer**: events emitted by L1 services are `identity`, events emitted by L2 services are `authorization`, etc.

#### Dual State Machine Contract

`IdentityStatus` and `LifecycleState` are two distinct state machines operating at different control planes. They are linked but not equivalent.

| Dimension | IdentityStatus (L1) | LifecycleState (L7) |
|-----------|---------------------|---------------------|
| Control plane | Data plane (runtime enforcement) | Control plane (governance) |
| Checked when | Every agent action (synchronous, sub-millisecond) | Lifecycle events (asynchronous, minutes to days) |
| Changed by | `identity_service` (triggered by governance commands or anomaly signals) | `lifecycle_manager` (triggered by certification results, governance decisions, schedules) |
| Granularity | 3 states | 8 states |
| Purpose | "Can this agent execute right now?" | "Where is this agent in its organizational lifecycle?" |

**Command flow is one-directional:** governance *commands* identity (downward), identity *informs* governance (upward via `TrustTraceRecord` events). The identity service never changes lifecycle state. The lifecycle manager changes lifecycle state and *triggers* identity status changes by calling `identity_service.suspend()` / `.restore()` / `.revoke()`.

**Valid combinations:**

| LifecycleState | Valid IdentityStatus | Notes |
|---|---|---|
| `defined`, `building` | N/A (no identity issued yet) | `AgentFacts` does not exist until `onboarding` |
| `onboarding` | `active` | Identity created, certification pending |
| `deployed`, `operating`, `adapting` | `active` | Normal operation |
| `suspended` | `suspended` | Governance suspension cascades to identity |
| `decommissioned` | `revoked` | Permanent |

**Lifecycle-to-identity side effects:**

| LifecycleState Transition | IdentityStatus Side Effect |
|---|---|
| `onboarding` -> `deployed` | Set status to `active` |
| `operating` -> `suspended` | Set status to `suspended` |
| `suspended` -> `operating` (restore) | Set status to `active` |
| `suspended` -> `decommissioned` | Set status to `revoked` |
| Any -> `decommissioned` | Set status to `revoked` |
| `operating` -> `adapting` | Status remains `active` (agent still runs during recertification) |
| `adapting` -> `operating` | No change (already `active`) |

**Feedback loop:** If the identity service detects an anomaly at runtime (e.g., signature tamper), it emits a `TrustTraceRecord` event. The governance layer consumes that event and may decide to transition the agent to `suspended` lifecycle state, which in turn commands the identity service to suspend the identity. Runtime incidents feed back into governance via events, never via direct state mutation.

*Source: HashiCorp/Microsoft Entra dual control plane pattern.*

#### `trust/trace_schema.py` -- Cross-Layer Event Schema

| Model | Purpose | Consumers |
|-------|---------|-----------|
| `TrustTraceRecord` | Pydantic model: unified envelope for all trust events | All trust-aware services emit to this schema; trace_service routes; certification and governance consume for evidence and dashboards |

```python
class TrustTraceRecord(BaseModel):
    schema_version: int = 2
    event_id: str                       # unique ID for this event (UUID, auto-generated)
    source_agent_id: str | None = None  # the agent that emitted this event
    causation_id: str | None = None     # event_id of the event that caused this one
    timestamp: datetime
    trace_id: str           # correlates all events in one task
    agent_id: str           # the agent this event is about (from L1 identity)
    layer: str              # "L1" | "L2" | "L3" | "L4" | "L5" | "L6" | "L7"
    event_type: str         # "identity_verified" | "access_granted" | ...
    details: dict           # layer-specific payload
    outcome: str | None     # "pass" | "fail" | "alert" | None
```

The three fields added in schema version 2 enable multi-agent event correlation and causal tracing:

| Field | Purpose | Multi-Agent Relevance |
|---|---|---|
| `event_id` | Unique addressable handle for every event (UUID). Eliminates timestamp-based deduplication. | Required for `causation_id` references and distributed event deduplication. |
| `source_agent_id` | The agent that emitted this event (distinct from `agent_id` which is the agent the event is about). | When Agent A verifies Agent B, `source_agent_id = A`, `agent_id = B`. Without this, cross-agent attribution is ambiguous. |
| `causation_id` | The `event_id` of the event that caused this event, creating a causal chain. | Enables backward tracing from a governance action to its root cause without timestamp heuristics. ESAA calls this the intention-dispatch-effect chain. |

All three fields are backward-compatible: `event_id` defaults to a new UUID, `source_agent_id` and `causation_id` default to `None`. Version 1 events are valid version 2 events.

#### `trust/signature.py` -- Cryptographic Primitives

| Function | Purpose | Consumers |
|----------|---------|-----------|
| `compute_signature(facts) -> str` | SHA256 over signed fields of AgentFacts | identity_service (register, update, re_sign_all) |
| `verify_signature(facts) -> bool` | Recompute and compare against stored hash | identity_service (verify), trace_service (tamper detection on logs), certification (integrity check) |
| `get_signed_fields(facts) -> dict` | Extract only the fields included in signature | signature computation, audit display |

These are **pure functions**: deterministic, no side effects, no I/O. `compute_signature` takes a dict of signed fields and returns a SHA256 hex string. `verify_signature` recomputes and compares. Nothing is stored or logged here -- that is the identity service's job.

**Signed vs. unsigned metadata boundary convention:** `get_signed_fields()` partitions `AgentFacts` fields into signed (governance-grade) and unsigned (operational) sets. The boundary rule: any field that determines what an agent is *authorized* to do is signed; everything else is not.

| Category | Signed (`signed_metadata`) | Unsigned (`metadata`) |
|----------|---------------------------|----------------------|
| Compliance | `compliance_frameworks`, `data_classification` | `last_security_review` |
| Model | `model_version` | `deployment_environment` |
| Organization | (N/A -- `owner` is a top-level signed field) | `team_email`, `cost_center` |
| Operations | (N/A) | `baseline_accuracy`, `incident_response_contact` |

Changing a `signed_metadata` field triggers signature recomputation and may trigger L6 recertification. Changing a `metadata` field creates an audit entry but does not break the signature. The full field list is defined in `trust/models.py` at implementation time.

---

## Horizontal Services: Identity Service (Option C)

The identity service (`utils/identity_service.py`) implements the `AgentFactsRegistry` as a **single module with internal class decomposition**. One public class, four internal concerns.

### Public API

```python
from trust.models import AgentFacts, AuditEntry, VerificationReport
from trust.signature import compute_signature, verify_signature
from trust.enums import IdentityStatus

class AgentFactsRegistry:
    """Single entry point for all identity operations.

    Internally delegates to _Storage, _Verifier, _LifecycleManager,
    and _QueryEngine. Callers see one class with a focused API per concern.
    """

    # --- CRUD (delegates to _Storage) ---
    def register(self, facts: AgentFacts, registered_by: str) -> AgentFacts: ...
    def get(self, agent_id: str) -> AgentFacts: ...
    def update(self, agent_id: str, updates: dict, updated_by: str) -> AgentFacts: ...
    def deregister(self, agent_id: str, reason: str, deregistered_by: str) -> None: ...

    # --- Verification (delegates to _Verifier) ---
    def verify(self, agent_id: str) -> bool: ...
    def verify_all(self) -> VerificationReport: ...
    def re_sign_all(self, reason: str, re_signed_by: str) -> None: ...

    # --- Lifecycle (delegates to _LifecycleManager) ---
    def suspend(self, agent_id: str, reason: str, suspended_by: str) -> None: ...
    def restore(self, agent_id: str, reason: str, restored_by: str) -> None: ...
    def revoke(self, agent_id: str, reason: str, revoked_by: str) -> None: ...
    def renew(self, agent_id: str, new_valid_until: datetime, renewed_by: str) -> None: ...

    # --- Queries (delegates to _QueryEngine) ---
    def list_all(self) -> list[str]: ...
    def find_by_owner(self, owner: str) -> list[str]: ...
    def find_by_capability(self, name: str) -> list[str]: ...
    def find_orphans(self, known_owners: list[str]) -> list[str]: ...
    def audit_trail(self, agent_id: str) -> list[AuditEntry]: ...
    def export_for_audit(self, agent_ids: list[str], filepath: str) -> None: ...
```

### Internal Decomposition

| Internal Class | Responsibility | State |
|----------------|---------------|-------|
| `_Storage` | File-based CRUD, LRU cache for reads, JSON serialization | Owns disk I/O and cache |
| `_Verifier` | Calls `trust.signature.verify_signature()`, checks status and expiry | Stateless (reads from _Storage) |
| `_LifecycleManager` | State transition guards (suspended -> active, but not revoked -> active), audit entry creation | Stateless (writes through _Storage) |
| `_QueryEngine` | Filtering, search, bulk operations, audit export | Stateless (reads from _Storage) |

Only `_Storage` manages persistent state. The other three are stateless logic that read from and write through `_Storage`. This keeps the single-responsibility principle intact while presenting a unified API.

### Style Guide Compliance

| Rule | Verdict | Rationale |
|------|---------|-----------|
| H1: No vertical awareness | Pass | Accepts `agent_id: str`, returns `AgentFacts` (from `trust/`). No knowledge of writers, reviewers, or pipeline stages. |
| H2: Single responsibility | Pass | "Agent identity management" is one responsibility. Internal decomposition prevents method bloat within a single class. |
| H3: Own logging stream | Pass | `trust_identity.log` via `logging.json` configuration. |
| H4: Parameterized | Pass | The service stores whatever `AgentFacts` instance the caller provides. It does not define what capabilities or policies mean -- that's L2/L3 territory. |
| Stateful but scoped | Pass | Same pattern as Memory (H6): persistent state scoped by `agent_id`. |

---

## Dependency Rules

### Complete Dependency Table

| From | To | Allowed? | Rationale |
|------|----|----------|-----------|
| **Trust Foundation** | Anything above | **FORBIDDEN** | Zero outward dependencies. This is the invariant that makes the foundation stable. |
| **Horizontal** | Trust Foundation | **Yes** | Services import the models they operate on. |
| **Horizontal** | Horizontal | **Yes, cautiously** | A service may use another (e.g., Guardrails uses Prompt Service). identity_service does not import authorization_service or vice versa. |
| **Vertical** | Trust Foundation | **Yes** | Components can read trust types directly (e.g., purpose_checker reads `Policy` model). |
| **Vertical** | Horizontal | **Yes** | Vertical components consume infrastructure services. (Existing rule, unchanged.) |
| **Vertical** | Vertical | **FORBIDDEN** | Creates coupling. (Existing rule, unchanged.) |
| **Orchestration** | Trust Foundation | **Yes** | Thin wrappers may reference trust types for gate decisions. |
| **Orchestration** | Horizontal | **Yes** | Orchestrator calls services. (Existing rule, unchanged.) |
| **Orchestration** | Vertical | **Yes** | Orchestrator calls pipeline stages. (Existing rule, unchanged.) |
| **Meta-Layer** | Trust Foundation | **Yes** | Governance reads/writes trust models directly. |
| **Meta-Layer** | Horizontal | **Yes** | Governance calls services to persist changes (e.g., `identity_service.suspend()`). |
| **Any** | Orchestration | **FORBIDDEN** | Circular dependency. (Existing rule, unchanged.) |
| **Horizontal** | Vertical | **FORBIDDEN** | (Existing rule, unchanged.) |

### Dependency Diagram

```
  Meta-Layer ──────────┐
       │               │
       ▼               │
  Orchestration ───────┤
       │               │
       ▼               │
  Vertical ────────────┤
       │               │
       ▼               │
  Horizontal ──────────┤
       │               │
       ▼               ▼
  ══════════════════════════
  Trust Foundation (all layers import from here)
```

Every arrow points downward. No layer imports from a layer above it. The trust foundation sits at the bottom, imported by all.

### Trust Service Dependency Rules

The three trust-aware horizontal services (`identity_service`, `authorization_service`, `trace_service`) require explicit inter-service dependency rules to prevent circular coupling as the trust framework grows.

**Principle:** On the synchronous runtime path (every agent action), the three trust services are **completely independent peers** that share nothing except the `trust/` foundation types. The orchestrator composes them. Off the synchronous path (batch operations, audit export), `trace_service` may call `identity_service.get()` for agent metadata resolution.

**DAG:**

```
trust/ foundation (types, pure functions)
    ▲         ▲           ▲
    │         │           │
identity    authz       trace
service     service     service
    ▲         ▲           ▲
    │         │           │
    └─────────┴───────────┘
              │
    verify_authorize_log_node
         (orchestrator)
```

**Inter-service dependency table:**

| From | To | Allowed? | Rationale |
|------|----|----------|-----------|
| `identity_service` | `trust/` | **Yes** | Imports models, signature functions |
| `authorization_service` | `trust/` | **Yes** | Imports models (`AgentFacts` type, `Policy`, `Capability`) |
| `trace_service` | `trust/` | **Yes** | Imports `TrustTraceRecord`, `verify_signature()` |
| `identity_service` | `authorization_service` | **FORBIDDEN** | Identity does not know authorization exists |
| `identity_service` | `trace_service` | **FORBIDDEN** | Identity does not emit traces directly; the orchestrator does |
| `authorization_service` | `identity_service` | **FORBIDDEN** | Authorization receives `AgentFacts` as a parameter from the orchestrator, not by calling identity. See [Runtime Trust Gate](#runtime-trust-gate). |
| `authorization_service` | `trace_service` | **FORBIDDEN** | Authorization returns decisions to the orchestrator; the orchestrator logs via trace_service |
| `trace_service` | `identity_service` | **Allowed (read-only, off-path only)** | For agent_id resolution in batch/async operations. Not on the synchronous hot path. |
| `trace_service` | `authorization_service` | **FORBIDDEN** | Tracing does not make access decisions |

*Source: Microsoft AGT Agent OS / Agent Mesh independence pattern -- identity and policy packages are independently installable with no cross-imports.*

---

## Directory Structure

```
project/
├── trust/                              # TRUST FOUNDATION
│   ├── __init__.py                     # Re-exports key types
│   ├── models.py                       # AgentFacts, Capability, Policy, AuditEntry,
│   │                                   # VerificationReport, CredentialRecord,
│   │                                   # PolicyDecision, TrustScoreRecord, CloudBinding
│   ├── enums.py                        # IdentityStatus, CertificationStatus,
│   │                                   # LifecycleState, EventCategory
│   ├── trace_schema.py                 # TrustTraceRecord (v2: +event_id, source_agent_id,
│   │                                   # causation_id)
│   ├── signature.py                    # compute_signature(), verify_signature()
│   ├── exceptions.py                   # TrustProviderError hierarchy (cloud-agnostic)
│   ├── cloud_identity.py              # IdentityContext, AccessDecision,
│   │                                   # TemporaryCredentials, PolicyBinding,
│   │                                   # PermissionBoundary
│   └── protocols.py                   # IdentityProvider, PolicyProvider,
│                                       # CredentialProvider, PolicyBackend
│
├── utils/                              # HORIZONTAL SERVICES
│   ├── identity_service.py             # AgentFactsRegistry
│   ├── authorization_service.py        # Access decisions, policy evaluation (L2)
│   ├── trace_service.py                # TrustTraceRecord emission/routing (L5)
│   ├── credential_cache.py            # CachedCredentialManager (TTL-based)
│   ├── cloud_providers/               # Cloud-specific adapters (hexagonal adapters)
│   │   ├── __init__.py                 # get_provider() factory
│   │   ├── config.py                  # TrustProviderSettings (pydantic-settings)
│   │   ├── aws_identity.py            # AWSIdentityProvider (boto3 sts+iam)
│   │   ├── aws_policy.py              # AWSPolicyProvider (boto3 iam)
│   │   ├── aws_credentials.py         # AWSCredentialProvider (boto3 sts)
│   │   └── local_provider.py          # Local* providers (testing, no cloud)
│   ├── policy_backends/               # External policy engine adapters
│   │   ├── yaml_backend.py            # YAMLPolicyBackend
│   │   ├── opa_backend.py             # OPAPolicyBackend (remote/local/built-in)
│   │   └── cedar_backend.py           # CedarPolicyBackend
│   ├── prompt_service.py               # (existing, unchanged)
│   ├── llms.py                         # (existing, unchanged)
│   ├── guardrails.py                   # (existing, unchanged)
│   ├── long_term_memory.py             # (existing, unchanged)
│   ├── save_for_eval.py                # (existing, unchanged)
│   └── human_feedback.py               # (existing, unchanged)
│
├── agents/                             # VERTICAL COMPONENTS
│   ├── task_assigner.py                # (existing, unchanged)
│   ├── generic_writer_agent.py         # (existing, unchanged)
│   ├── reviewer_panel.py               # (existing, unchanged)
│   ├── purpose_checker.py              # Validates actions against declared scope (L3+L4)
│   └── plan_builder.py                 # Captures task plan structure (L4)
│
├── governance/                         # META-LAYER
│   ├── lifecycle_manager.py            # Agent state machine, transition guards (L7)
│   ├── certification.py                # Evaluation suite, pass/fail gates (L6)
│   ├── compliance_reporter.py          # Audit export, regulatory reports (L6+L7)
│   ├── trust_scoring.py               # TrustScoringEngine (EMA + decay)
│   └── event_consumers.py             # Governance feedback loop handlers
│
├── prompts/                            # Prompt templates (data, not code)
├── data/                               # Pre-built indexes (for RAG)
├── evals/                              # Evaluation scripts
├── logging.json                        # Per-module log routing config
└── app.py                              # Entry point
```

---

## How Layers Consume Trust Foundation: Examples

### Horizontal: identity_service.py

```python
from trust.models import AgentFacts, AuditEntry
from trust.signature import compute_signature, verify_signature
from trust.enums import IdentityStatus
```

The identity service imports models and crypto from the foundation. It owns storage (disk I/O), caching (LRU), and audit trail management (JSONL append). The foundation provides the types; the service provides the persistence.

### Horizontal: trace_service.py

```python
from trust.trace_schema import TrustTraceRecord
from trust.signature import verify_signature  # tamper detection on log records
```

The trace service imports the event envelope schema and signature verification. It does not go through the identity service to verify signatures -- it calls the pure function directly from the foundation.

### Vertical: purpose_checker.py

```python
from trust.models import AgentFacts, Policy, Capability
```

The purpose checker reads the `Policy` and `Capability` models to validate whether a proposed action falls within the agent's declared scope. It imports types from the foundation and reads agent data from the identity service (via horizontal dependency).

### Meta-Layer: certification.py

```python
from trust.models import AgentFacts
from trust.enums import CertificationStatus
from trust.trace_schema import TrustTraceRecord
```

Certification reads agent identity for evaluation, reads trace records as evidence, and writes certification status back. It imports types from the foundation and calls the identity service to persist status changes.

### Meta-Layer: lifecycle_manager.py

```python
from trust.enums import LifecycleState, IdentityStatus
from trust.models import AgentFacts
```

The lifecycle manager operates the state machine. It imports state enums from the foundation and calls the identity service (`suspend()`, `revoke()`, `restore()`) to execute transitions.

---

## Logging Configuration Extension

The trust-aware services extend the existing `logging.json` per-concern routing:

```json
{
    "handlers": {
        "trust_identity": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "trust_identity.log"
        },
        "trust_authorization": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "trust_authorization.log"
        },
        "trust_trace": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "trust_trace.log"
        }
    },
    "loggers": {
        "utils.identity_service": {
            "handlers": ["trust_identity"],
            "level": "DEBUG",
            "propagate": false
        },
        "utils.authorization_service": {
            "handlers": ["trust_authorization"],
            "level": "DEBUG",
            "propagate": false
        },
        "utils.trace_service": {
            "handlers": ["trust_trace"],
            "level": "DEBUG",
            "propagate": false
        }
    }
}
```

Each trust service gets its own log stream, following the H3 pattern from the Style Guide. Trust events are also emitted as `TrustTraceRecord` instances to the trace service for cross-layer correlation.

The new services introduced in the [Ephemeral Credential Lifecycle](#ephemeral-credential-lifecycle), [External Policy Engine Support](#external-policy-engine-support), and [Continuous Trust Scoring Specification](#continuous-trust-scoring-specification) sections require additional log stream configuration:

```json
{
    "handlers": {
        "trust_credentials": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "trust_credentials.log"
        },
        "trust_policy": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "trust_policy.log"
        },
        "trust_scoring": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "trust_scoring.log"
        }
    },
    "loggers": {
        "utils.credential_cache": {
            "handlers": ["trust_credentials"],
            "level": "DEBUG",
            "propagate": false
        },
        "utils.policy_backends": {
            "handlers": ["trust_policy"],
            "level": "DEBUG",
            "propagate": false
        },
        "governance.trust_scoring": {
            "handlers": ["trust_scoring"],
            "level": "DEBUG",
            "propagate": false
        }
    }
}
```

This produces three additional log files: `trust_credentials.log` (credential issuance, refresh, eviction events), `trust_policy.log` (external policy evaluation decisions), `trust_scoring.log` (score updates, ring transitions, decay events).

---

## Runtime Trust Gate

The `verify_authorize_log_node` in the orchestration layer is the **Policy Enforcement Point (PEP)** for the trust framework, following the NIST 800-207 Zero Trust Architecture model. It composes three independent horizontal services into a single sequential gate.

### NIST 800-207 Mapping

| NIST Component | Architecture Component | Responsibility |
|---|---|---|
| **Policy Enforcement Point (PEP)** | `verify_authorize_log_node` (orchestration layer) | Gatekeeper on the data plane. Intercepts every agent action. Calls PDP for decisions. |
| **Policy Decision Point (PDP)** | `identity_service.verify()` + `authorization_service.evaluate()` | Makes allow/deny decisions. Two sub-components called sequentially by PEP. |
| **Policy Information Point (PIP)** | `trust/` foundation (`AgentFacts`, policies, capabilities) | Data source the PDP reads from to make decisions. |

### Sequential Flow

```
Agent Action arrives
       │
       ▼
verify_authorize_log_node (PEP -- orchestration layer)
       │
       ├──1. facts = identity_service.get(agent_id)
       │     identity_service.verify(agent_id)
       │     - Recompute signature → match?
       │     - Check status == "active"?
       │     - Check valid_until not expired?
       │     FAIL → trace_service.record(...) + REJECT
       │
       ├──2. authorization_service.evaluate(
       │        facts=facts,       ← passed as data, NOT fetched by authz
       │        action=action,
       │        context=context)
       │     - Check certification_status
       │     - Evaluate RBAC/ABAC rules against capabilities
       │     - Check action against declared purpose
       │     FAIL → trace_service.record(...) + DENY/THROTTLE
       │
       └──3. trace_service.record(
              TrustTraceRecord with L1+L2 results)
              - Emit event regardless of pass/fail
              - Correlate with trace_id
```

### Critical Design Rule

The `authorization_service` receives `AgentFacts` as a **function parameter** from the orchestrator. It never calls `identity_service.get()` directly. This eliminates the horizontal-to-horizontal dependency between authorization and identity:

```python
# In verify_authorize_log_node (orchestration layer)
facts = identity_service.get(agent_id)
is_valid = identity_service.verify(agent_id)
if not is_valid:
    trace_service.record(...)
    return REJECT

access_decision = authorization_service.evaluate(
    facts=facts,          # passed as data, not fetched by authz
    action=action,
    context=context
)

trace_service.record(...)
```

The orchestrator is the only component that knows both services exist and calls them in sequence. This preserves Rule O1 (orchestrator controls topology) and prevents H->H coupling between trust services. See [Trust Service Dependency Rules](#trust-service-dependency-rules) for the full inter-service dependency table.

*Source: NIST SP 800-207 Zero Trust Architecture (PEP/PDP/PIP model), InfoQ AI Agent Gateway pattern.*

---

## External Research Summary

The decision to introduce a trust foundation layer is supported by production systems in the ecosystem:

| Project | Identity Model Layer | Service/Enforcement Layer | Key Insight |
|---------|---------------------|--------------------------|-------------|
| **Microsoft Agent Governance Toolkit** (1,000+ stars) | `AgentIdentity` + `AgentDID` in AgentMesh package | Agent OS policy engine (separate package) | Identity models are an independent package; policy engine imports them. Trust scoring (0-1000) with decay. |
| **Agent Identity Protocol (AIP)** | Agent Identity Document (AID) | Policy proxy that verifies Agent Authentication Tokens | Explicit two-layer separation: "Layer 1 is identity, Layer 2 is enforcement." |
| **NANDA Index / AgentFacts** | AgentFacts as JSON-LD documents (W3C Verifiable Credentials) | Lean Index (resolution) + Dynamic Resolution (routing) | Identity metadata is a portable document, not a service API. |
| **CSA Agentic Trust Framework** | Five pillars: Identity, Behavior, Data, Segmentation, Incident Response | Zero Trust governance specification | Build order: identity first, then everything else reads from it. |
| **DDD Shared Kernel** | Centralized domain models | Multiple bounded contexts import the kernel | Types shared across modules with zero outward dependencies. |

The consistent pattern: **the identity model is a portable artifact that lives below the services that operate on it.** No production system embeds identity types inside a service module.

---

## Design Decisions and Deferrals

### Certification Trigger Mechanism (G2)

**Decision:** Governance triggers certification via *events* (emitted through `trace_service`), not via direct orchestrator calls.

The dependency table states "Any -> Orchestration is FORBIDDEN." This means `governance/lifecycle_manager.py` cannot call the orchestration layer to start a certification workflow. Instead:

- **Phase 1:** Certification (`governance/certification.py`) runs as a standalone batch process that calls horizontal services directly (`identity_service.get()` to load the agent, `trace_service` to read evidence, `identity_service.suspend()` to act on failure). No orchestrator involvement.
- **Phase 2:** When certification becomes a multi-step workflow, the lifecycle manager emits a `TrustTraceRecord` event with `event_type: "recertification_triggered"`. A separate scheduler or event consumer picks up the event and initiates the certification pipeline. The orchestrator is never called directly by governance.

### Trust Scoring Deferral (G6)

**Decision:** Phase 1 uses discrete identity states (`active`/`suspended`/`revoked`). Continuous trust scoring with decay is an intentional Phase 2 deferral.

Microsoft's Agent Governance Toolkit implements trust scoring (0-1000) where scores decay over time without positive signals. This is a more nuanced model than binary status, enabling graduated access control (e.g., Ring 0 at score >= 900, Ring 3 at score < 400).

The current architecture accommodates trust scoring as an additive feature:
- `trust_score: float | None = None` is added to `AgentFacts` in Phase 2 without breaking the existing `status` field
- `IdentityStatus` remains the synchronous runtime gate (fast, binary)
- `trust_score` becomes an input to `authorization_service.evaluate()` for graduated access decisions
- Trust decay is a periodic batch operation in `governance/`, updating scores based on activity signals from `trace_service`

The two models coexist: `status` is the hard gate ("can this agent execute at all?"), `trust_score` is the soft gate ("what level of access should this agent have?").

---

## Governance Feedback Loops

The trust framework specifies three feedback loops (`TRUST_FRAMEWORK_ARCHITECTURE.md`): L5->L2 (anomaly->quarantine), L6->L1/L2 (certification failure->suspend), L7->L6 (governance->recertification). A fourth loop (trust decay) was added by the [Continuous Trust Scoring Specification](#continuous-trust-scoring-specification). All four are wired as **direct method calls** in Phase 1 -- not via an event bus -- for debuggability and simplicity.

**Dependency rule:** Governance consumers in `governance/event_consumers.py` call horizontal services directly. This is permitted (Meta-Layer -> Horizontal is allowed). They **never** call the orchestration layer (Any -> Orchestration is FORBIDDEN).

### Loop Specification

| Loop | Trigger | Action | Emitted Event |
|---|---|---|---|
| **Anomaly -> Quarantine** | `authorization_service` denial count exceeds threshold (e.g., 5 denials within 10 minutes for the same `agent_id`) | `identity_service.suspend(agent_id, "anomaly_threshold_exceeded", "event_consumers")` | `TrustTraceRecord(event_type="agent_quarantined", category="governance")` |
| **Certification Failure -> Suspend** | `certification.evaluate()` returns `failed` | `identity_service.suspend(agent_id, "certification_failed", "event_consumers")` | `TrustTraceRecord(event_type="identity_suspended", category="identity")` |
| **Lifecycle -> Recertification** | `lifecycle_manager` transitions agent to `adapting` state | `certification.run_evaluation(agent_id)` | `TrustTraceRecord(event_type="recertification_triggered", category="governance")` |
| **Trust Decay** | Periodic timer (every hour) | For each active agent with no positive signal in the period: decrement `trust_score` by decay rate. If score < 100: `identity_service.suspend(agent_id, "trust_floor_breached", "event_consumers")` | `TrustTraceRecord(event_type="trust_score_updated", category="governance")` per agent |

### Phase 1 Wiring

In Phase 1, these loops are implemented as methods in `governance/event_consumers.py` called directly by the modules that detect the trigger condition:

```python
class GovernanceEventConsumers:
    def __init__(self, identity_service, certification, trust_scoring):
        self._identity = identity_service
        self._certification = certification
        self._scoring = trust_scoring

    def on_anomaly_threshold(self, agent_id: str, denial_count: int) -> None: ...
    def on_certification_failed(self, agent_id: str, report: dict) -> None: ...
    def on_lifecycle_adapting(self, agent_id: str) -> None: ...
    def on_trust_decay_tick(self) -> None: ...
```

The caller chain is traceable via the call stack. No event bus indirection, no subscription management, no broken stack traces. In Phase 2, these methods become event subscribers -- see [Event-Driven Architecture Migration Path](#event-driven-architecture-migration-path).

*Source: TRUST_FRAMEWORK_ARCHITECTURE.md feedback loops; GaaS Trust Factor enforcement modes.*

---

## Event-Driven Architecture Migration Path

The architecture evolves from direct method calls to a distributed event bus across three phases. Each phase changes only the **transport mechanism** -- the event schema (`TrustTraceRecord`), the governance logic (`event_consumers.py`), and the feedback loop definitions remain unchanged.

### Phase Progression

| Phase | Transport | Scope | Infrastructure |
|---|---|---|---|
| **Phase 1 (current)** | Direct method calls | Single pipeline, in-process | None -- standard Python function calls |
| **Phase 2** | `EventBus` protocol + `InProcessEventBus` adapter | Single pipeline, decoupled consumers | In-process observer pattern (`dict[str, list[Callable]]`) |
| **Phase 3** | `KafkaEventBus` or `RedisStreamsEventBus` adapter | Multi-agent fleet, distributed | Apache Kafka or Redis Streams |

### Phase 2: EventBus Protocol (Deferred)

The `EventBus` protocol will be added to `trust/protocols.py` when the second consumer arrives (per the abstraction introduction principle in [Architectural Identity](#architectural-identity)):

```python
@runtime_checkable
class EventBus(Protocol):
    def publish(self, event: TrustTraceRecord) -> None: ...
    def subscribe(self, event_type: str, handler: Callable[[TrustTraceRecord], None]) -> None: ...
    def subscribe_category(self, category: str, handler: Callable[[TrustTraceRecord], None]) -> None: ...
```

The `InProcessEventBus` implementation in `utils/event_bus.py` uses a simple observer pattern (~30 lines). The `GovernanceEventConsumers` methods become subscription handlers without changing their logic.

### Phase 3: Distributed Bus and the Blackboard Pattern

For multi-agent fleet coordination, the `InProcessEventBus` is replaced with a `KafkaEventBus` (or `RedisStreamsEventBus`) adapter. Events are published to topics partitioned by `agent_id`, ensuring per-agent ordering.

The **Blackboard pattern** (Confluent's fourth multi-agent design pattern) enables fleet-wide coordination without peer-to-peer communication:

- A shared event topic (the "blackboard") where all agents publish `TrustTraceRecord` events
- Governance consumers subscribe to the blackboard to build fleet-wide views (materialized via CQRS read models)
- No agent-to-agent discovery or connection management required
- The orchestrator or a scheduler reads from the blackboard and dispatches governance actions

This avoids the complexity of peer-to-peer mesh (IATP trust handshakes) while enabling multi-agent coordination. The blackboard is a stepping stone: if peer-to-peer is eventually needed, agents that already communicate via events can be wired to exchange events directly.

### Latency Contract

| Operation | Timing | Latency | Network Call? |
|---|---|---|---|
| Internal identity verification (SHA256 + status) | Every agent action | < 1ms | No |
| Cached credential expiry check | Every agent action | < 1ms | No |
| Trust score ring lookup | Every agent action | < 1ms | No (in-memory) |
| Governance feedback loop execution | On trigger condition | 1-10ms | No (in-process Phase 1) |
| Cloud credential issuance (STS assume_role) | Registration + cache miss | 100-300ms | Yes |
| Cloud policy evaluation (IAM simulate) | Registration + periodic | 200-500ms | Yes |
| Event bus publish (Phase 2, in-process) | Every trust event | < 0.1ms | No |
| Event bus publish (Phase 3, Kafka) | Every trust event | 1-5ms | Yes |

**Rule: All network calls to cloud IAM are off the per-action hot path.** The synchronous trust gate uses only cached, in-memory data.

### Event Sourcing Migration Path for Identity

| Phase | Storage Model | Source of Truth | Reconstruction |
|---|---|---|---|
| **Phase 1 (current)** | Mutable JSON + append-only JSONL audit trail | JSON file (mutable) | Not applicable |
| **Phase 2** | JSONL becomes primary; JSON becomes materialized view | JSONL event log (immutable) | `rebuild_from_events(agent_id)` replays JSONL to reconstruct JSON; `verify_projection(agent_id)` hashes the replay result against the JSON file to detect corruption |
| **Phase 3** | Event log on distributed bus + periodic snapshots | Kafka topic or equivalent | Replay from latest snapshot + subsequent events |

Phase 1 to Phase 2 migration is a single-module change in `identity_service._Storage`: reverse the write order (event first, then JSON) and add the `rebuild_from_events()` and `verify_projection()` methods. The hot path (`verify()`) is unchanged -- it still reads from the JSON/LRU cache.

*Source: ESAA append-only event log with projection verification; Confluent Blackboard pattern; GaaS Trust Factor real-time enforcement.*

---

## Ephemeral Credential Lifecycle

**Gap addressed:** AgentMesh uses 15-minute TTL ephemeral credentials with auto-rotation; the Four-Layer Architecture has only `valid_until` + status transitions. This section specifies a credential manager that wraps the cloud provider's `CredentialProvider` protocol with TTL-based caching and proactive refresh.

### Credential TTL Convention

| Parameter | Value | Rationale |
|---|---|---|
| Default TTL | 15 minutes | Aligned with AgentMesh convention and AWS STS / GCP IAM minimum session durations |
| Proactive refresh threshold | 80% of TTL (12 minutes) | Prevents expired-credential errors by refreshing before expiry |
| Per-agent override | `AgentFacts.metadata["credential_ttl_seconds"]` | Agents with elevated privileges may use shorter TTLs |

Credentials are issued at registration time (pre-provisioned) and refreshed proactively. They are **not** issued per-action (JIT) because per-action issuance puts network calls on the hot path, violating the sub-millisecond latency requirement established in the [Runtime Trust Gate](#runtime-trust-gate).

### `CredentialRecord` Value Object

Defined in `trust/models.py`. The `provider` field uses a constrained `Literal` type rather than a free-form string, keeping it within the foundation's "deterministic schema" boundary. The rationale: `provider` constrains which credential refresh strategy applies, making it a structural classification (like `IdentityStatus`) rather than operational metadata.

```python
class CredentialRecord(BaseModel):
    agent_id: str
    provider: Literal["aws_sts", "gcp_iam", "azure_ad", "local"]
    issued_at: datetime
    expires_at: datetime
    scope: list[str]
    credential_hash: str   # SHA256 of the credential for audit, not the credential itself
```

### Lifecycle State Integration

When `identity_service.suspend()` is called, the orchestrator must also call `credential_cache.evict(agent_id)`. This extends the Dual State Machine Contract's lifecycle-to-identity side effects table:

| LifecycleState Transition | IdentityStatus Side Effect | Credential Side Effect |
|---|---|---|
| `operating` -> `suspended` | Set status to `suspended` | Evict cached credentials via `credential_cache.evict(agent_id)` |
| `suspended` -> `operating` (restore) | Set status to `active` | Credentials re-provisioned on next proactive refresh cycle |
| Any -> `decommissioned` | Set status to `revoked` | Evict cached credentials; no re-provisioning |

**Cross-section interaction:** Credential eviction emits a trust signal (see [Continuous Trust Scoring Specification](#continuous-trust-scoring-specification)) of type `infrastructure` with value -10, recording that a forced eviction degraded operational continuity.

### Grid Placement

| Artifact | Grid Layer | Module |
|---|---|---|
| `CredentialRecord` (type) | Trust Foundation | `trust/models.py` |
| `CachedCredentialManager` (behavior) | Horizontal | `utils/credential_cache.py` |
| Eviction orchestration (topology) | Orchestration | `verify_authorize_log_node` or lifecycle transition handler |

### Just-in-Time vs. Pre-Provisioned

| Strategy | Used? | Rationale |
|---|---|---|
| Pre-provisioned + proactive refresh | **Yes** | Credentials ready before needed; no network call on the hot path |
| Just-in-Time (per-action) | **No** | Puts credential issuance on the synchronous action path; violates latency requirement |

*Source: AgentMesh ephemeral credential pattern; AWS STS session token best practices.*

---

## External Policy Engine Support

**Gap addressed:** AgentMesh supports YAML, OPA/Rego, and Cedar policy backends via a unified `PolicyEvaluator` pipeline; the Four-Layer Architecture embeds policies in the identity card only. This section specifies a dual-layer policy model that preserves governance-grade embedded policies while adding operationally agile external policy evaluation.

### Dual-Layer Policy Model

| Dimension | Layer A (Embedded, governance-grade) | Layer B (External, operationally agile) |
|---|---|---|
| Storage | `list[Policy]` in `AgentFacts.policies` | Policy files in YAML / Rego / Cedar |
| Signing | Signed. Changes trigger re-signing and may trigger recertification | NOT signed. Changes are immediate, no recertification |
| Scope | Defines *what the agent is allowed to be* | Defines *how the agent should behave right now* |
| Examples | `max_token_budget`, `allowed_data_classifications`, `prohibited_actions` | `rate_limit: 100/hour`, `require_approval_for_delete`, `block_pii_export` |
| Change velocity | Slow (governance process) | Fast (deploy new policy file) |

### `PolicyBackend` Protocol

Defined in `trust/protocols.py`. Runtime-checkable protocol that all external policy backends implement.

```python
@runtime_checkable
class PolicyBackend(Protocol):
    def evaluate(
        self, agent_id: str, action: str, context: dict
    ) -> PolicyDecision: ...
```

### `PolicyDecision` Value Object

Defined in `trust/models.py`. The `enforcement` field is the single source of truth for the decision outcome. A convenience property derives the boolean to avoid ambiguity (an earlier design had separate `allowed: bool` and `action: str` fields, creating undefined states like `allowed=True` with `action="require_approval"`).

```python
class PolicyDecision(BaseModel):
    enforcement: Literal["allow", "deny", "require_approval", "throttle"]
    reason: str
    backend: Literal["embedded", "opa", "cedar", "yaml"]
    audit_entry: dict

    @property
    def allowed(self) -> bool:
        return self.enforcement == "allow"
```

### Evaluation Precedence

Embedded policies (Layer A) are checked first. If an embedded policy denies, the action is denied regardless of external policy. External policies (Layer B) are checked second, providing additional runtime constraints.

```
Agent Action
    │
    ├──1. Evaluate embedded policies (Layer A)
    │     Source: AgentFacts.policies (signed, governance-grade)
    │     DENY → action denied, skip Layer B
    │
    ├──2. Evaluate external policies (Layer B)
    │     Source: PolicyBackend.evaluate() (unsigned, operationally agile)
    │     DENY / THROTTLE / REQUIRE_APPROVAL → enforce
    │
    └──3. Both layers allow → action proceeds
```

Embedded policies are a **floor** (minimum restrictions). External policies add further restrictions on top.

**One-directional restriction trade-off:** The precedence model is intentionally one-directional: external policies can only tighten, never loosen. This is a deliberate security posture. If an embedded policy is set too aggressively, the fix is to update the embedded policy (which triggers re-signing and recertification), not to override it from an unsigned external source. This trade-off preserves the governance-grade integrity of Layer A.

**Cross-section interaction with trust scoring:** Ring thresholds from the [Continuous Trust Scoring Specification](#continuous-trust-scoring-specification) feed into `authorization_service.evaluate()`. When `trust_score` places an agent in Ring 2 (read-only), external policies that grant write access are overridden by the ring constraint. The ring acts as a ceiling on what external policies can authorize.

### Grid Placement

| Artifact | Grid Layer | Module |
|---|---|---|
| `PolicyDecision` (type) | Trust Foundation | `trust/models.py` |
| `PolicyBackend` (protocol) | Trust Foundation | `trust/protocols.py` |
| `YAMLPolicyBackend` (implementation) | Horizontal | `utils/policy_backends/yaml_backend.py` |
| `OPAPolicyBackend` (implementation) | Horizontal | `utils/policy_backends/opa_backend.py` |
| `CedarPolicyBackend` (implementation) | Horizontal | `utils/policy_backends/cedar_backend.py` |
| Dual-layer evaluation orchestration | Horizontal | `utils/authorization_service.py` (`.evaluate()` calls both layers) |

### Microsoft AGT Alignment

The three evaluation modes for the `OPAPolicyBackend` adapter follow the same pattern as AGT's `ExternalPolicyBackend` protocol:

| Mode | Description | Use Case |
|---|---|---|
| Remote OPA server | HTTP call to a running OPA instance | Production with centralized policy management |
| Local CLI subprocess | Invoke `opa eval` as a subprocess | Development and testing |
| Built-in pattern matcher | Evaluate simple rules without OPA | Lightweight deployments without OPA infrastructure |

*Source: Microsoft Agent Governance Toolkit policy evaluation pipeline; Cedar policy language specification.*

---

## Continuous Trust Scoring Specification

**Gap addressed:** AgentMesh implements 0-1000 trust scoring with decay; the Four-Layer Architecture defers to Phase 2 with only a brief outline (see [Trust Scoring Deferral (G6)](#trust-scoring-deferral-g6)). This section promotes that deferral to a full architectural specification.

### Scoring Algorithm

Exponential Moving Average (EMA) with asymmetric signal weights:

```
score_new = (1 - α) * score_old + α * signal_value
```

| Parameter | Default | Description |
|---|---|---|
| `α` (smoothing factor) | 0.1 | Controls how quickly new signals influence the score |
| Positive signal range | 0 to +20 | Trust is slow to build |
| Negative signal range | 0 to -50 | Trust is fast to lose |
| Initial score | 500 | New agents start at Ring 1 (Standard) |

The asymmetry is intentional: a single compliance violation (-50) has far more impact than a successful task completion (+15). Trust is harder to gain than to lose.

### Signal Taxonomy

Five mutually exclusive categories with a classification convention for boundary cases.

| Signal Category | Example Events | Weight Range | Source Layer |
|---|---|---|---|
| Compliance | Policy violation, guardrail trigger | -30 to -50 | L2 (`authorization_service`) |
| Performance | Task success, evaluation pass | +5 to +15 | L6 (`certification`) |
| Behavioral | Consistent actions within scope | +3 to +10 | L5 (`trace_service`) |
| Infrastructure | Credential refresh failure, storage error, service timeout | -5 to -15 | Horizontal (`credential_cache`, `policy_backends`) |
| Temporal | Idle decay (no positive signals) | -1 per hour | L7 (governance batch) |

**Classification convention:** When an event could fit both Compliance and Infrastructure (e.g., a credential refresh failure caused by a revoked policy), classify by **root cause**. If the failure originated from a policy decision, it is Compliance. If it originated from an operational fault (network timeout, provider outage), it is Infrastructure. Log the secondary classification in the `TrustScoreRecord.details` dict.

### Trust Decay

Score decreases by a configurable amount per time period without positive signals. Default: -1 per hour of inactivity. This prevents "sleeper agents" from maintaining high trust indefinitely.

| Parameter | Default | Description |
|---|---|---|
| Decay rate | -1 per hour | Applied when no positive signal received in the period |
| Decay floor | 0 | Score cannot go below 0 (triggers automatic suspension at <100) |
| Decay exemption | Agents in `suspended` or `decommissioned` state | No decay applied to already-inactive agents |

### Enforcement Thresholds (Rings)

| Ring | Score Range | Access Level |
|---|---|---|
| Ring 0 (Full trust) | 900-1000 | All capabilities, including sensitive operations |
| Ring 1 (Standard) | 700-899 | Standard capabilities, no sensitive operations |
| Ring 2 (Restricted) | 400-699 | Read-only, no write/delete/external calls |
| Ring 3 (Probation) | 100-399 | Logging only, all actions denied, under review |
| Suspended | 0-99 | Automatic suspension, triggers governance alert |

### Coexistence with IdentityStatus

`IdentityStatus` remains the hard gate (binary). `trust_score` is the soft gate (graduated). The two models coexist:

| Scenario | IdentityStatus | trust_score | Effective Access |
|---|---|---|---|
| Normal operation | `active` | 850 | Ring 1 (Standard) |
| Degraded trust | `active` | 250 | Ring 3 (Probation) -- active but restricted |
| Governance suspension | `suspended` | 750 | **Blocked** -- hard gate overrides soft gate |
| New agent | `active` | 500 | Ring 1 (Standard) -- initial score |

An agent with `status=active` and `trust_score=250` is active but restricted to Ring 3. An agent with `status=suspended` is blocked regardless of score.

### `TrustScoreRecord` Value Object

Defined in `trust/models.py`. Records every score change for audit and trend analysis.

```python
class TrustScoreRecord(BaseModel):
    agent_id: str
    score: float
    previous_score: float
    signal_type: Literal["compliance", "performance", "behavioral", "infrastructure", "temporal"]
    signal_value: float
    timestamp: datetime
    details: dict
```

### Grid Placement

| Artifact | Grid Layer | Module |
|---|---|---|
| `TrustScoreRecord` (type) | Trust Foundation | `trust/models.py` |
| `trust_score` field on `AgentFacts` | Trust Foundation | `trust/models.py` |
| `TrustScoringEngine` (behavior) | Meta-Layer | `governance/trust_scoring.py` |
| Ring-based access decisions | Horizontal | `utils/authorization_service.py` (`.evaluate()` reads the score) |

*Source: Microsoft Agent Governance Toolkit trust scoring (0-1000 with decay); CSA Agentic Trust Framework graduated access control.*

---

## Multi-Agent Trust Handshake Readiness

**Gap addressed:** AgentMesh supports peer-to-peer trust handshakes via IATP; the Four-Layer Architecture has no multi-agent scope. This section does **not** implement IATP (out of scope for a pipeline architecture) but specifies extension points that make future multi-agent support structurally possible without redesigning the foundation.

### Architectural Readiness, Not Implementation

The Four-Layer Architecture is a pipeline system. Peer-to-peer trust handshakes are a mesh concern. This section documents what would need to change and what already works.

### What Already Works for Multi-Agent

| Existing Artifact | Multi-Agent Relevance |
|---|---|
| `AgentFacts` | Portable identity document that can be exchanged between systems |
| `TrustTraceRecord` | Has `agent_id` + `trace_id` for cross-agent correlation |
| `CredentialProvider` protocol | Cloud-agnostic; could issue credentials for cross-system access |
| `trust_score` (when implemented) | Provides the minimum trust threshold check needed for peer verification |

### Extension Points Needed for Multi-Agent

The `AgentFacts` serialization for exchange is placed in the **Horizontal** layer, not Trust Foundation. Adding W3C Verifiable Credential serialization (JSON-LD context resolution, DID document construction) to a foundation model would violate the purity constraint ("No I/O, no storage, no network"). Instead, a horizontal serializer accepts `AgentFacts` and produces the exchange format.

| Extension | Description | Grid Layer | Module |
|---|---|---|---|
| `AgentFacts` serialization for exchange | `serialize_to_vc(facts)` function producing W3C VC or DID-linked JSON | Horizontal | `utils/trust_exchange.py` (new) |
| Asymmetric signing | Replace SHA256 hash with Ed25519 (or ML-DSA-65 for quantum-safe) key pair for identity proofs | Trust Foundation | `trust/signature.py` |
| Peer verification protocol | `verify_peer(peer_facts, min_trust_score)` | Horizontal | `utils/trust_handshake.py` (new) |
| Trust bridge integration | Adapter for IATP, A2A, or MCP trust headers | Horizontal | `utils/protocol_bridges/` (new) |

### IATP Latency Constraint

The Microsoft AGT ADR specifies a 200ms handshake SLA. This is compatible with the existing architecture since handshakes would occur at session establishment (not per-action), similar to how cloud credential issuance is off the hot path.

### Migration Path: SHA256 to Ed25519

SHA256 -> Ed25519 is the critical upgrade. The `trust/signature.py` module already isolates cryptographic primitives. Replacing `compute_signature()` and `verify_signature()` with asymmetric equivalents is a single-module change that does not affect any consumer (they call the same functions, just get stronger guarantees).

| Phase | Signing | Verification | Backward Compatible? |
|---|---|---|---|
| Current (Phase 1) | SHA256 hash | Recompute and compare | N/A |
| Phase 2 | Ed25519 private key signature | Ed25519 public key verification | Yes -- same function signatures, stronger guarantees |
| Phase 3 (optional) | ML-DSA-65 (quantum-safe) | ML-DSA-65 verification | Yes -- same function signatures |

*Source: Microsoft AGT IATP handshake specification; W3C Verifiable Credentials Data Model; NIST FIPS 204 (ML-DSA).*

---

## Phase 2 Extension Points

The following table tracks all Phase 2 features. Features promoted to full specifications in this document are marked as **Specified** with a link to the relevant section. Remaining features are documented with their grid placement to prevent misplacement by future developers.

| Feature | Status | Specification / Phase 2 Addition | Grid Layer | Module |
|---------|--------|----------------------------------|------------|--------|
| Credential lifecycle | **Specified** | [`CredentialRecord` + `CachedCredentialManager`](#ephemeral-credential-lifecycle) | Trust Foundation + Horizontal | `trust/models.py`, `utils/credential_cache.py` |
| External policy engines | **Specified** | [`PolicyBackend` protocol + dual-layer model](#external-policy-engine-support) | Trust Foundation + Horizontal | `trust/models.py`, `trust/protocols.py`, `utils/policy_backends/` |
| Continuous trust scoring | **Specified** | [EMA algorithm + ring thresholds + decay](#continuous-trust-scoring-specification) | Trust Foundation + Meta-Layer + Horizontal | `trust/models.py`, `governance/trust_scoring.py`, `utils/authorization_service.py` |
| Trust decay | **Specified** | [Included in trust scoring specification](#trust-decay) | Meta-Layer | `governance/trust_scoring.py` |
| Governance feedback loops | **Specified** | [Four loops as direct method calls](#governance-feedback-loops) | Meta-Layer | `governance/event_consumers.py` |
| EDA migration path | **Documented** | [Phase 1/2/3 progression with latency contract](#event-driven-architecture-migration-path) | All layers | See migration table |
| TrustTraceRecord v2 | **Specified** | [+event_id, source_agent_id, causation_id](#trusttrace_schemapy----cross-layer-event-schema) | Trust Foundation | `trust/trace_schema.py` |
| EventCategory enum | **Specified** | [MECE event type taxonomy](#event-type-taxonomy) | Trust Foundation | `trust/enums.py` |
| Cloud-agnostic protocols | **Specified** | [IdentityProvider, PolicyProvider, CredentialProvider](TRUST_FOUNDATION_PROTOCOLS_PLAN.md) | Trust Foundation + Horizontal | `trust/protocols.py`, `utils/cloud_providers/` |
| Exception hierarchy | **Specified** | [TrustProviderError tree](TRUST_FOUNDATION_PROTOCOLS_PLAN.md) | Trust Foundation | `trust/exceptions.py` |
| Multi-agent readiness | **Extension points documented** | [Serialization + Ed25519 migration path](#multi-agent-trust-handshake-readiness) | Trust Foundation + Horizontal | `trust/signature.py`, `utils/trust_exchange.py`, `utils/trust_handshake.py` |
| EventBus protocol | **Deferred** | YAGNI -- introduce when second consumer arrives. See [EDA Migration Path](#event-driven-architecture-migration-path). | Trust Foundation | `trust/protocols.py` (Phase 2) |
| Event sourcing for identity | **Deferred** | JSONL becomes source of truth; JSON becomes materialized view. See [EDA Migration Path](#event-driven-architecture-migration-path). | Horizontal | `utils/identity_service.py` |
| Blackboard pattern | **Deferred** | Shared event topic for fleet-wide multi-agent coordination. See [EDA Migration Path](#event-driven-architecture-migration-path). | Horizontal | `utils/event_bus.py` (Phase 3) |
| Namespace isolation | Deferred | `namespace: str \| None = None` field | Trust Foundation | `trust/models.py` (new field on `AgentFacts`) |
| Delegation tokens | Deferred | `DelegationToken` Pydantic model | Trust Foundation | `trust/models.py` (new model) |
| Chain of trust traversal | Deferred | `resolve_delegation_chain(agent_id)` method | Horizontal | `utils/identity_service.py` (new method on `AgentFactsRegistry`) |
| Supply chain attestation | Deferred | `build_hash`, `code_signature`, `provenance_uri` fields | Trust Foundation | `trust/models.py` (new fields in `signed_metadata` convention) |
| Centralized audit index | Deferred | `registry_events.jsonl` cross-fleet time-range queries | Horizontal | `utils/identity_service.py` (new `_QueryEngine` capability) |
| Partitioned storage | Deferred | Per-namespace storage directories | Horizontal | `utils/identity_service.py` (new `_Storage` capability) |

All features follow the same principle: **types go in the trust foundation, behavior goes in the appropriate grid layer.** The abstraction introduction principle governs timing: build when the second consumer arrives, not before.

---

## Relationship to Existing Documents

This document **extends** the Style Guide Layering (`STYLE_GUIDE_LAYERING.md`) by adding the trust foundation as a fourth layer beneath the existing three. The original three-layer rules remain unchanged -- horizontal, vertical, and orchestration rules all apply as documented.

The **Trust Framework Architecture** (`TRUST_FRAMEWORK_ARCHITECTURE.md`) maps onto this four-layer grid as follows:

| Trust Framework Layer | Four-Layer Grid Placement |
|-----------------------|--------------------------|
| L1 Identity | Trust Foundation (models) + Horizontal (identity_service) |
| L2 Authorization | Trust Foundation (models) + Horizontal (authorization_service) |
| L3 Purpose & Policy | Trust Foundation (Policy model) + Vertical (purpose_checker) |
| L4 Explainability | Vertical (plan_builder) |
| L5 Observability | Trust Foundation (TrustTraceRecord) + Horizontal (trace_service) |
| L6 Certification | Trust Foundation (CertificationStatus) + Meta-Layer (certification) |
| L7 Governance | Trust Foundation (LifecycleState) + Meta-Layer (lifecycle_manager) |

Every trust layer splits into: **types in the foundation** and **behavior in the appropriate grid layer**.
