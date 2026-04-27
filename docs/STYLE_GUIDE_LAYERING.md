# Style Guide: Composable Four-Layer Architecture for Agentic Systems

A style guide for organizing agentic systems into composable layers with a trust foundation.
Technology-agnostic principles with concrete examples from the [composable_app](../../composable_app/) reference implementation.

**Related documents:**
- [STYLE_GUIDE_PATTERNS.md](STYLE_GUIDE_PATTERNS.md) -- Design patterns catalog with implementation guidance
- [STYLE_GUIDE_FRONTEND.md](STYLE_GUIDE_FRONTEND.md) -- Frontend Ring counterpart to this guide (W/P/A/T/X/C/B/U/S/O rule families for the Next.js + CopilotKit + AG-UI stack)
- [FOUR_LAYER_ARCHITECTURE.md](Architectures/FOUR_LAYER_ARCHITECTURE.md) -- Trust Foundation integration and dependency analysis
- [TRUST_FRAMEWORK_ARCHITECTURE.md](TRUST_FRAMEWORK_ARCHITECTURE.md) -- Seven-layer trust framework mapped to the four-layer grid
- [LAYER1_IDENTITY_ANALYSIS.md](LAYER1_IDENTITY_ANALYSIS.md) -- Detailed L1 Identity implementation analysis

---

## Table of Contents

- [Core Principle: The Four-Layer Grid](#core-principle-the-four-layer-grid)
- [Trust Foundation: Shared Kernel](#trust-foundation-shared-kernel)
- [Horizontal Layer: Cross-Cutting Services](#horizontal-layer-cross-cutting-services)
- [Vertical Layer: Pipeline Components](#vertical-layer-pipeline-components)
- [Orchestration Layer: Pipeline Topology](#orchestration-layer-pipeline-topology)
- [Meta-Layer: Governance and Lifecycle](#meta-layer-governance-and-lifecycle)
- [Dependency Rules](#dependency-rules)
- [Anti-Patterns](#anti-patterns)
- [Composability Checklists](#composability-checklists)

---

## Core Principle: The Four-Layer Grid

An agentic system is a pipeline of LLM-powered components organized into four layers plus a trust foundation. Each layer has a distinct role:

- **Trust Foundation** (`trust/`) contains portable trust artifacts -- pure data models, enums, and deterministic functions consumed by every layer above. It has zero outward dependencies.

- **Horizontal services** (`utils/`) are cross-cutting infrastructure consumed by every pipeline stage. They have no knowledge of domain logic. Examples: prompt rendering, model configuration, guardrails, logging, evaluation capture, memory, identity management, authorization.

- **Vertical components** (`agents/`) are independently swappable pipeline stages that own domain logic. Each one performs a distinct step in the pipeline. Examples: input classifier, content generator, reviewer, purpose checker.

- **Orchestration layer** defines the pipeline topology -- which verticals exist, what order they run in, and where parallelism is possible. It contains no domain logic.

- **Meta-layer** (`governance/`) contains offline governance and process controls -- lifecycle management, certification, compliance reporting. It operates outside the runtime pipeline.

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

The power of this grid: every vertical component automatically gets observability, prompt management, evaluation data capture, guardrails, and trust verification without implementing any of that infrastructure itself. Every horizontal service works with any vertical component without knowing what it does. And every layer shares a common trust vocabulary through the foundation, eliminating hidden coupling between services that need the same trust types.

---

## Trust Foundation: Shared Kernel

The trust foundation (`trust/`) sits beneath all other layers, separated by a double line in the grid diagram. It contains **types and pure functions** that define the trust domain. It is the single source of truth for trust-related data structures.

This layer follows the DDD Shared Kernel pattern: centralized domain models imported by multiple bounded contexts with zero outward dependencies. The same pattern is used by Microsoft's Agent Governance Toolkit (identity model separate from policy engine) and the Agent Identity Protocol (identity document separate from enforcement proxy).

### What Belongs in the Trust Foundation

A component belongs in the trust foundation if it satisfies **all** of these criteria:

1. **Pure**: No I/O, no storage, no network, no logging. Only data models (Pydantic) and deterministic functions.
2. **Shared**: Consumed by two or more layers above. If only one service needs a type, it stays in that service.
3. **Stable**: Changes less frequently than the services that consume it. Schema changes are deliberate and trigger re-signing.
4. **Dependency-free**: Zero imports from horizontal, vertical, orchestration, or meta-layer code.

### Contents

| Module | Contents | Consumers |
|--------|----------|-----------|
| `trust/models.py` | `AgentFacts`, `Capability`, `Policy`, `AuditEntry`, `CredentialRecord`, `PolicyDecision`, `TrustScoreRecord` | identity_service, authorization_service, trace_service, certification, lifecycle_manager |
| `trust/enums.py` | `IdentityStatus`, `CertificationStatus`, `LifecycleState` | identity_service, authorization_service, certification, lifecycle_manager |
| `trust/trace_schema.py` | `TrustTraceRecord` -- unified envelope for all trust events | All trust-aware services emit to this schema; trace_service routes; governance consumes |
| `trust/signature.py` | `compute_signature()`, `verify_signature()`, `get_signed_fields()` | identity_service, trace_service, certification |
| `trust/protocols.py` | `PolicyBackend` -- runtime-checkable protocol for external policy engines | authorization_service, policy backend implementations |

### Rules

**Rule T1: Pure types only.**
The trust foundation contains no I/O, no storage, no network calls, no logging. Only Pydantic models and deterministic functions. `compute_signature()` takes a dict and returns a SHA256 hex string. It does not store or log anything -- that is the identity service's job.

**Rule T2: Shared across two or more layers.**
If only one service needs a type, the type stays in that service. A type moves to the foundation when a second consumer appears. This prevents the foundation from becoming a dumping ground for every model in the system.

**Rule T3: Stable -- changes less frequently than consumers.**
Schema changes to foundation types are deliberate. Changing a signed field triggers signature recomputation and may trigger recertification. The foundation is the slowest-moving layer in the system.

**Rule T4: Zero outward dependencies.**
The trust foundation imports nothing from horizontal, vertical, orchestration, or meta-layer code. This is the invariant that makes the foundation stable. If a foundation module needs a type from a service, the design is wrong -- the type should move to the foundation or the dependency should be inverted.

### Signed vs. Unsigned Metadata Convention

`get_signed_fields()` partitions `AgentFacts` fields into signed (governance-grade) and unsigned (operational) sets. The boundary rule: any field that determines what an agent is *authorized* to do is signed; everything else is not.

| Category | Signed (`signed_metadata`) | Unsigned (`metadata`) |
|----------|---------------------------|----------------------|
| Compliance | `compliance_frameworks`, `data_classification` | `last_security_review` |
| Model | `model_version` | `deployment_environment` |
| Organization | (N/A -- `owner` is a top-level signed field) | `team_email`, `cost_center` |
| Operations | (N/A) | `baseline_accuracy`, `incident_response_contact` |

Changing a `signed_metadata` field triggers signature recomputation and may trigger recertification. Changing a `metadata` field creates an audit entry but does not break the signature. See [FOUR_LAYER_ARCHITECTURE.md](Architectures/FOUR_LAYER_ARCHITECTURE.md) for the full field specification.

---

## Horizontal Layer: Cross-Cutting Services

### What Belongs in the Horizontal Layer

A service is horizontal if it satisfies **all** of these criteria:

1. **Domain-agnostic**: It works the same whether called by a math writer, a grammar reviewer, or a task classifier. It has no knowledge of topic types, content formats, or pipeline stage semantics.

2. **Used by multiple vertical components**: At least two (and typically all) pipeline stages consume it.

3. **Infrastructure, not logic**: It provides a capability (render a template, validate input, record data) rather than making a domain decision (which writer to assign, whether content is good enough).

### Rules

**Rule H1: Stateless utilities with no vertical awareness.**
Horizontal services must not import from, reference, or hold state about any vertical component. They accept generic inputs (strings, dicts, template names) and return generic outputs.

```python
# composable_app/utils/prompt_service.py -- correct
# Accepts a template name and variables. Has no idea who is calling it.
class PromptService:
    @staticmethod
    def render_prompt(prompt_name, **variables) -> str:
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template(f"{prompt_name}.j2")
        return template.render(**variables)
```

**Rule H2: Single responsibility.**
Each horizontal service does exactly one thing. Prompt rendering, input validation, eval recording, and memory retrieval are four separate modules, not one "agent utilities" class.

| Service | Responsibility | NOT its job |
|---------|---------------|-------------|
| Prompt Service | Render templates, log rendered prompts | Deciding which template to use |
| LLM Config | Define model tiers and settings | Choosing which tier for a given step |
| Guardrails | Validate input against a condition | Defining what the condition should be |
| Observability | Route structured logs to per-service streams | Interpreting log contents |
| Eval Capture | Record AI input/output pairs | Evaluating whether the output is good |
| Memory | Store and retrieve past interactions | Deciding what context is relevant |
| Human Feedback | Record human overrides of AI decisions | Making the override decision itself |
| Identity Service | Register, verify, and manage agent identity cards (`AgentFacts`) | Defining what capabilities or policies mean |
| Authorization Service | Evaluate access decisions against policies and capabilities | Fetching agent identity (receives `AgentFacts` as a parameter) |
| Trace Service | Emit and route `TrustTraceRecord` events for cross-layer correlation | Making access decisions or changing agent state |
| Credential Cache | Cache and proactively refresh ephemeral credentials | Issuing credentials (delegates to cloud provider) |

**Rule H3: Own logging stream.**
Each horizontal service logs to its own structured file via the logging configuration. This creates separate, machine-parseable data streams without any vertical component needing to configure logging.

```json
{
    "loggers": {
        "utils.prompt_service": {
            "handlers": ["prompts"],
            "level": "DEBUG",
            "propagate": false
        },
        "utils.guardrails": {
            "handlers": ["guards"],
            "level": "DEBUG",
            "propagate": false
        },
        "utils.save_for_eval": {
            "handlers": ["evals"],
            "level": "DEBUG",
            "propagate": false
        }
    }
}
```

This produces separate log files: `prompts.log` (every prompt rendered), `guards.log` (every guardrail decision), `evals.log` (every AI response for evaluation).

Trust-aware horizontal services extend this pattern with their own log streams:

```json
{
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

This produces additional log files: `trust_identity.log` (identity CRUD and verification events), `trust_authorization.log` (access decisions), `trust_trace.log` (cross-layer trust event routing). Trust events are also emitted as `TrustTraceRecord` instances to the trace service for cross-layer correlation. See [FOUR_LAYER_ARCHITECTURE.md](Architectures/FOUR_LAYER_ARCHITECTURE.md) for the complete logging configuration including credential, policy, and trust scoring log streams.

**Rule H4: Parameterized, not specialized.**
Horizontal services are configured by their callers, not hardcoded for specific use cases. The guardrail service accepts an `accept_condition` string -- it does not have a built-in "topic safety check".

```python
# composable_app/utils/guardrails.py -- correct: parameterized
class InputGuardrail:
    def __init__(self, name: str, accept_condition: str):
        self.system_prompt = PromptService.render_prompt(
            "InputGuardrail_prompt", accept_condition=accept_condition
        )
        self.agent = Agent(llms.SMALL_MODEL, output_type=bool, ...)
```

The caller decides the condition:

```python
# composable_app/agents/task_assigner.py -- the vertical component configures it
self.topic_guardrail = InputGuardrail(
    name="topic_guardrail",
    accept_condition=PromptService.render_prompt("TaskAssigner_input_guardrail")
)
```

### Trust Service H-Rule Compliance

Trust-aware horizontal services follow the same H-rules as existing services. The identity service demonstrates this:

| Rule | Verdict | Rationale |
|------|---------|-----------|
| H1: No vertical awareness | Pass | Accepts `agent_id: str`, returns `AgentFacts` (from `trust/`). No knowledge of writers, reviewers, or pipeline stages. |
| H2: Single responsibility | Pass | "Agent identity management" is one responsibility. Internal decomposition (`_Storage`, `_Verifier`, `_LifecycleManager`, `_QueryEngine`) prevents method bloat. |
| H3: Own logging stream | Pass | `trust_identity.log` via `logging.json` configuration. |
| H4: Parameterized | Pass | Stores whatever `AgentFacts` instance the caller provides. Does not define what capabilities or policies mean. |

The three trust services (`identity_service`, `authorization_service`, `trace_service`) are **independent peers** on the synchronous runtime path. They share nothing except `trust/` foundation types. The orchestrator composes them into the Runtime Trust Gate (see [Orchestration Layer](#orchestration-layer-pipeline-topology) and [FOUR_LAYER_ARCHITECTURE.md](Architectures/FOUR_LAYER_ARCHITECTURE.md) for the full specification).

---

## Vertical Layer: Pipeline Components

### What Belongs in the Vertical Layer

A component is vertical if it satisfies **all** of these criteria:

1. **Domain-specific**: It makes decisions or produces artifacts that are specific to the pipeline's purpose (classifying topics, writing articles, reviewing content).

2. **Independently swappable**: You can replace one vertical component (e.g., swap `HistoryWriter` for `ScienceWriter`) without modifying any other vertical component.

3. **Self-contained stage**: It represents a complete step in the pipeline that receives input, does its work (typically via an LLM call), and produces output.

### Rules

**Rule V1: Depend on horizontal services, never on other verticals.**
Vertical components import from `utils/` (horizontal). They never import from each other. Only the orchestrator knows which verticals exist and in what order they run.

```python
# composable_app/agents/generic_writer_agent.py -- correct
from utils import llms                    # horizontal
from utils.prompt_service import PromptService  # horizontal
from utils import long_term_memory as ltm       # horizontal
from utils import save_for_eval as evals        # horizontal
```

**Rule V2: Specialize via abstraction + configuration, not code duplication.**
Define an abstract interface with template methods. Concrete subclasses override only the parts that vary. The shared workflow lives in the abstract base class.

```
AbstractWriter                          # template methods: write_about(), revise_article()
    └── ZeroshotWriter                  # concrete LLM call logic
            ├── MathWriter              # get_content_type() = "detailed solution"
            ├── HistoryWriter           # get_content_type() = "2 paragraphs"
            ├── GeneralistWriter        # get_content_type() = "short article"
            └── GenAIWriter             # overrides write_response() to add RAG
```

The abstract class `AbstractWriter.write_about()` defines the workflow that is **identical** across all writers:
1. Retrieve memories (horizontal)
2. Render prompt template (horizontal)
3. Call `self.write_response()` (polymorphic -- the only part that varies)
4. Record eval data (horizontal)

Leaf classes only define `get_content_type()` -- a single string.

**Rule V3: Persona via prompt, not code.**
When multiple agents have the same behavior but different personalities (reviewers, adversarial testers), use a single class parameterized by a system prompt. The persona is data (a `.j2` template), not code.

```python
# composable_app/agents/reviewer_panel.py -- one class, many personas
class ReviewerAgent:
    def __init__(self, reviewer: Reviewer):
        system_prompt_file = f"{reviewer.name}_system_prompt".lower()
        system_prompt = PromptService.render_prompt(system_prompt_file)
        self.agent = Agent(llms.DEFAULT_MODEL, output_type=str,
                           system_prompt=system_prompt)
```

Adding a new reviewer means writing a `.j2` file and adding an enum value. Zero code changes to `ReviewerAgent`.

**Rule V4: Use factories for instantiation.**
Vertical components are created through factory methods, not direct construction. This centralizes the enum-to-class mapping and makes the orchestrator indifferent to which concrete class is instantiated.

```python
# composable_app/agents/generic_writer_agent.py
class WriterFactory:
    @staticmethod
    def create_writer(writer: Writer) -> AbstractWriter:
        match writer:
            case Writer.MATH_WRITER.name:
                return MathWriter()
            case Writer.HISTORIAN.name:
                return HistoryWriter()
            case Writer.GENAI_WRITER:
                return GenAIWriter()
            case _:
                return GeneralistWriter()
```

**Rule V5: Every LLM call records eval data.**
Every vertical component must call the evaluation capture horizontal service after receiving an LLM response. The `target` tag identifies which pipeline stage produced the output.

```python
await evals.record_ai_response("initial_draft",
                               ai_input=prompt_vars,
                               ai_response=result)
```

---

## Orchestration Layer: Pipeline Topology

The orchestrator is the only component that knows the full pipeline topology -- which verticals exist, what order they run in, and where parallelism is possible. It contains **no domain logic**.

### Rules

**Rule O1: Topology only, no domain logic.**
The orchestrator calls vertical components and passes outputs between them. It does not inspect, transform, or make decisions about the content flowing through the pipeline.

```python
# composable_app/agents/task_assigner.py -- correct: pure orchestration
async def write_about(self, topic: str) -> Article:
    writer = WriterFactory.create_writer(await self.find_writer(topic))
    draft = await writer.write_about(topic)
    panel_review = await reviewer_panel.get_panel_review_of_article(topic, draft)
    article = await writer.revise_article(topic, draft, panel_review)
    return article
```

Four lines. No conditionals on content. No prompt rendering. No domain decisions. Just "classify, write, review, revise."

**Rule O2: Parallelism decisions live in the orchestrator.**
When two operations are independent (guardrail check and topic classification), the orchestrator runs them in parallel. The vertical components themselves are unaware of concurrency.

```python
# composable_app/agents/task_assigner.py
_, result = await asyncio.gather(
    self.topic_guardrail.is_acceptable(topic, raise_exception=True),
    self.agent.run(prompt)
)
```

**Rule O3: The orchestrator is the single place to understand the pipeline.**
A developer reading the orchestrator method should be able to understand the entire pipeline flow without looking at any other file.

**Rule O4: The Runtime Trust Gate composes trust services.**
The `verify_authorize_log_node` is the Policy Enforcement Point (PEP) for the trust framework, following the NIST 800-207 Zero Trust Architecture model. It composes three independent horizontal services into a single sequential gate:

1. `identity_service.verify()` -- recompute signature, check status, check expiry
2. `authorization_service.evaluate(facts, action, context)` -- check certification, evaluate RBAC/ABAC rules
3. `trace_service.record()` -- emit `TrustTraceRecord` regardless of pass/fail

The critical design rule: `authorization_service` receives `AgentFacts` as a **function parameter** from the orchestrator. It never calls `identity_service.get()` directly. This eliminates horizontal-to-horizontal coupling between trust services.

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

See [FOUR_LAYER_ARCHITECTURE.md](Architectures/FOUR_LAYER_ARCHITECTURE.md) for the full NIST 800-207 mapping and sequential flow specification.

---

## Meta-Layer: Governance and Lifecycle

The meta-layer (`governance/`) contains offline process controls that operate outside the runtime pipeline. These components manage agent lifecycle, certification, compliance reporting, and trust scoring.

### What Belongs in the Meta-Layer

A component is meta-layer if it satisfies **all** of these criteria:

1. **Governance-scoped**: It manages the lifecycle, certification, or compliance of agents -- not the runtime execution of agent tasks.

2. **Offline or asynchronous**: It runs as a batch process, scheduled job, or event-driven workflow -- not on the synchronous request path.

3. **Controls the control plane**: It operates on agent state (lifecycle transitions, certification status, trust scores) rather than on agent actions (request handling, content generation).

### Contents

| Module | Responsibility | Consumers |
|--------|---------------|-----------|
| `governance/lifecycle_manager.py` | Agent state machine, transition guards (L7) | Governance dashboards, certification triggers |
| `governance/certification.py` | Evaluation suite, pass/fail gates (L6) | Deployment pipelines, lifecycle_manager |
| `governance/compliance_reporter.py` | Audit export, regulatory reports (L6+L7) | External audit systems, compliance teams |
| `governance/trust_scoring.py` | Continuous trust scoring with EMA algorithm and ring thresholds | authorization_service (ring-based access), lifecycle_manager (suspension triggers) |

### Rules

**Rule M1: Governance triggers via events, not direct orchestrator calls.**
The meta-layer cannot call the orchestration layer (this would be an upward dependency). Instead, governance emits `TrustTraceRecord` events (e.g., `event_type: "recertification_triggered"`). A separate scheduler or event consumer picks up the event and initiates the workflow. In Phase 1, certification runs as a standalone batch process calling horizontal services directly.

**Rule M2: Meta-layer may call horizontal services directly.**
Governance components call horizontal services to persist changes. For example, `lifecycle_manager` calls `identity_service.suspend()` to cascade a governance suspension to the identity data plane. This is a downward dependency (meta -> horizontal) and is allowed.

**Rule M3: Meta-layer never calls orchestration.**
The `Any -> Orchestration: FORBIDDEN` rule applies to the meta-layer. Governance cannot start a pipeline run directly. It can only emit events or call horizontal services.

---

## Dependency Rules

### Dependency Diagram

Every arrow points downward. No layer imports from a layer above it. The trust foundation sits at the bottom, imported by all.

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

### Complete Dependency Table

| From | To | Allowed? | Rationale |
|------|----|----------|-----------|
| **Trust Foundation** | Anything above | **FORBIDDEN** | Zero outward dependencies. This is the invariant that makes the foundation stable. |
| **Horizontal** | Trust Foundation | **Yes** | Services import the models they operate on. |
| **Horizontal** | Horizontal | **Yes, cautiously** | A service may use another (e.g., Guardrails uses Prompt Service). identity_service does not import authorization_service or vice versa. |
| **Horizontal** | Vertical | **FORBIDDEN** | Prompt Service should not know about `HistoryWriter`. If it did, adding a new writer would require modifying a horizontal service. |
| **Vertical** | Trust Foundation | **Yes** | Components can read trust types directly (e.g., purpose_checker reads `Policy` model). |
| **Vertical** | Horizontal | **Yes** | Vertical components consume infrastructure services. |
| **Vertical** | Vertical | **FORBIDDEN** | Creates coupling: changing one writer breaks another. Makes it impossible to swap components independently. |
| **Orchestration** | Trust Foundation | **Yes** | Thin wrappers may reference trust types for gate decisions. |
| **Orchestration** | Horizontal | **Yes** | Orchestrator calls services. |
| **Orchestration** | Vertical | **Yes** | Orchestrator calls pipeline stages. |
| **Meta-Layer** | Trust Foundation | **Yes** | Governance reads/writes trust models directly. |
| **Meta-Layer** | Horizontal | **Yes** | Governance calls services to persist changes (e.g., `identity_service.suspend()`). |
| **Any** | Orchestration | **FORBIDDEN** | Circular dependency. The orchestrator calls downward; nothing calls upward into it. |

### Trust Service Inter-Dependency Rules

The three trust-aware horizontal services (`identity_service`, `authorization_service`, `trace_service`) require explicit rules to prevent circular coupling as the trust framework grows.

**Principle:** On the synchronous runtime path, the three trust services are **completely independent peers** that share nothing except `trust/` foundation types. The orchestrator composes them. Off the synchronous path (batch operations, audit export), `trace_service` may call `identity_service.get()` for agent metadata resolution.

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

| From | To | Allowed? | Rationale |
|------|----|----------|-----------|
| `identity_service` | `trust/` | **Yes** | Imports models, signature functions |
| `authorization_service` | `trust/` | **Yes** | Imports models (`AgentFacts` type, `Policy`, `Capability`) |
| `trace_service` | `trust/` | **Yes** | Imports `TrustTraceRecord`, `verify_signature()` |
| `identity_service` | `authorization_service` | **FORBIDDEN** | Identity does not know authorization exists |
| `identity_service` | `trace_service` | **FORBIDDEN** | Identity does not emit traces directly; the orchestrator does |
| `authorization_service` | `identity_service` | **FORBIDDEN** | Authorization receives `AgentFacts` as a parameter from the orchestrator, not by calling identity |
| `authorization_service` | `trace_service` | **FORBIDDEN** | Authorization returns decisions to the orchestrator; the orchestrator logs via trace_service |
| `trace_service` | `identity_service` | **Allowed (read-only, off-path only)** | For agent_id resolution in batch/async operations. Not on the synchronous hot path. |
| `trace_service` | `authorization_service` | **FORBIDDEN** | Tracing does not make access decisions |

*Source: Microsoft AGT Agent OS / Agent Mesh independence pattern -- identity and policy packages are independently installable with no cross-imports.*

---

## Anti-Patterns

### Anti-Pattern 1: The God Utility

A single horizontal module that handles prompts, logging, guardrails, and memory:

```python
# BAD: "AgentUtils" does everything
class AgentUtils:
    def render_and_validate_and_log(self, prompt_name, topic, ...):
        prompt = self._render_prompt(prompt_name, ...)
        self._check_guardrail(topic)
        self._log_to_all_streams(prompt, topic)
        memories = self._search_memory(topic)
        return prompt + memories
```

**Why it fails**: Cannot add a new guardrail condition without touching prompt rendering. Cannot change logging format without risking memory retrieval. Single-responsibility violation makes every change a shotgun surgery.

**Fix**: Separate modules, each with one responsibility. Vertical components compose them explicitly.

### Anti-Pattern 2: Vertical-to-Vertical Import

A writer that imports and calls a reviewer directly:

```python
# BAD: Writer knows about ReviewerPanel
from agents.reviewer_panel import get_panel_review_of_article

class SmartWriter(AbstractWriter):
    async def write_response(self, topic, prompt):
        draft = await self.agent.run(prompt)
        review = await get_panel_review_of_article(topic, draft.output)  # wrong layer
        revised = await self.agent.run(f"Revise based on: {review}")
        return revised.output
```

**Why it fails**: `SmartWriter` now depends on `ReviewerPanel`. Changing the review process requires modifying the writer. You cannot test the writer without the review panel. The orchestrator no longer controls the pipeline topology.

**Fix**: The orchestrator calls writer, then reviewer, then writer again. Each vertical component is unaware of the others.

### Anti-Pattern 3: Hardcoded Prompts in Agent Code

```python
# BAD: prompt is hardcoded in Python
class MathWriter:
    async def write_response(self, topic, prompt):
        full_prompt = f"You are a math educator. Write a detailed solution for: {topic}"
        return await self.agent.run(full_prompt)
```

**Why it fails**: Changing the prompt requires a code change, code review, and redeployment. Non-engineers cannot modify prompts. Prompt changes cannot be A/B tested independently. The prompt is not logged by the Prompt Service.

**Fix**: Externalize to a `.j2` template. Render via Prompt Service. The prompt becomes data, not code.

### Anti-Pattern 4: Business Logic in Horizontal Services

```python
# BAD: Prompt Service decides which template to use based on topic
class PromptService:
    @staticmethod
    def render_prompt(topic, **variables):
        if "math" in topic.lower():
            template_name = "math_writer_prompt"
        elif "history" in topic.lower():
            template_name = "history_writer_prompt"
        else:
            template_name = "general_prompt"
        # ...
```

**Why it fails**: The horizontal service now contains routing logic that belongs in the vertical layer (TaskAssigner). Adding a new writer type requires modifying the Prompt Service. The service is no longer domain-agnostic.

**Fix**: The vertical component (or orchestrator) decides which template to render. The Prompt Service just renders whatever template name it receives.

### Anti-Pattern 5: Duplicating Horizontal Logic in Vertical Components

```python
# BAD: each writer implements its own logging
class MathWriter:
    async def write_response(self, topic, prompt):
        result = await self.agent.run(prompt)
        with open("math_evals.log", "a") as f:  # duplicated logging
            json.dump({"input": prompt, "output": result}, f)
        return result
```

**Why it fails**: Every writer has its own logging implementation. Changing the log format requires modifying every writer. Some writers might forget to log. The log files are scattered and inconsistent.

**Fix**: Use the horizontal eval capture service (`save_for_eval.record_ai_response()`). It logs consistently for all vertical components.

### Anti-Pattern 6: Trust Types Inside a Service

Placing shared trust models inside a horizontal service instead of the trust foundation:

```python
# BAD: AgentFacts defined inside identity_service.py
# utils/identity_service.py
class AgentFacts(BaseModel):
    agent_id: str
    capabilities: list[Capability]
    ...

class AgentFactsRegistry:
    def register(self, facts: AgentFacts) -> AgentFacts: ...
```

**Why it fails**: `authorization_service` needs to read `AgentFacts` for access decisions. `trace_service` needs to read `agent_id` for attribution. `certification` needs to read identity for evaluation. All of them now import from `identity_service` -- a peer horizontal service -- creating hidden coupling. If `AgentFacts` lives in a vertical component, horizontal services import upward, which is forbidden.

**Fix**: Place `AgentFacts` in `trust/models.py` (the trust foundation). All services import the type from the foundation. The identity service imports the model and provides persistence; it does not own the model definition.

### Anti-Pattern 7: Horizontal-to-Horizontal Trust Coupling

The authorization service fetching agent identity directly from the identity service:

```python
# BAD: authorization_service imports and calls identity_service
# utils/authorization_service.py
from utils.identity_service import AgentFactsRegistry

class AuthorizationService:
    def __init__(self, registry: AgentFactsRegistry):
        self.registry = registry

    def evaluate(self, agent_id: str, action: str) -> bool:
        facts = self.registry.get(agent_id)  # H->H coupling
        return self._check_capabilities(facts, action)
```

**Why it fails**: `authorization_service` now depends on `identity_service`. Changing the identity service's API breaks authorization. Testing authorization requires a real or mocked identity service. The two services cannot evolve independently.

**Fix**: The orchestrator fetches `AgentFacts` from the identity service and passes it as a parameter to the authorization service. Authorization receives data, not a service dependency.

```python
# GOOD: orchestrator passes facts as data
# In verify_authorize_log_node (orchestration layer)
facts = identity_service.get(agent_id)
access_decision = authorization_service.evaluate(
    facts=facts,          # passed as data
    action=action,
    context=context
)
```

### Anti-Pattern 8: Upward Governance Calls

Governance components calling the orchestration layer to trigger workflows:

```python
# BAD: lifecycle_manager calls the orchestrator directly
# governance/lifecycle_manager.py
from orchestration import start_certification_pipeline

class LifecycleManager:
    def transition_to_adapting(self, agent_id: str):
        self.state[agent_id] = LifecycleState.ADAPTING
        start_certification_pipeline(agent_id)  # upward call
```

**Why it fails**: Governance now depends on orchestration -- an upward dependency. This creates a circular dependency: orchestration calls horizontal services, horizontal services are called by governance, and governance calls orchestration. Changes to the orchestration layer break governance.

**Fix**: Governance emits a `TrustTraceRecord` event with `event_type: "recertification_triggered"`. A separate scheduler or event consumer picks up the event and initiates the certification pipeline. Governance never calls the orchestrator directly.

```python
# GOOD: governance emits events, does not call orchestration
class LifecycleManager:
    def transition_to_adapting(self, agent_id: str):
        self.state[agent_id] = LifecycleState.ADAPTING
        trace_service.record(TrustTraceRecord(
            agent_id=agent_id,
            event_type="recertification_triggered",
            layer="L7",
            ...
        ))
```

### Anti-Pattern 9: Mixing Signed and Unsigned Metadata

Placing operational metadata in signed fields, causing unnecessary re-signing and recertification:

```python
# BAD: deployment_environment is signed
class AgentFacts(BaseModel):
    signed_metadata: dict = {
        "compliance_frameworks": ["SOC2", "HIPAA"],
        "model_version": "gpt-4o-2024-08",
        "deployment_environment": "staging",    # operational, not governance
        "team_email": "ml-team@company.com",    # operational, not governance
    }
```

**Why it fails**: Changing `deployment_environment` from `staging` to `production` triggers signature recomputation and may trigger recertification. A routine deployment becomes a governance event, creating friction and false alerts.

**Fix**: Only sign fields that determine what an agent is authorized to do. Operational metadata goes in the unsigned `metadata` dict. The boundary rule: if a field determines authorization scope, sign it; otherwise, don't.

```python
# GOOD: signed fields are governance-grade only
class AgentFacts(BaseModel):
    signed_metadata: dict = {
        "compliance_frameworks": ["SOC2", "HIPAA"],
        "model_version": "gpt-4o-2024-08",
    }
    metadata: dict = {
        "deployment_environment": "staging",
        "team_email": "ml-team@company.com",
    }
```

---

## Composability Checklists

### Checklist: Adding a New Vertical Component

Use this checklist when adding a new agent, writer, reviewer, or pipeline stage:

- [ ] **Horizontal and foundation dependencies only**: The component imports from `utils/` (horizontal services) and `trust/` (foundation types). It does not import from other vertical component packages.
- [ ] **Trust types from foundation**: If the component reads trust types (`AgentFacts`, `Policy`, `Capability`), it imports them from `trust/`, not from a horizontal service.
- [ ] **Uses Prompt Service**: All prompts are rendered via `PromptService.render_prompt()`. No hardcoded prompt strings.
- [ ] **Uses LLM Config**: The model is read from the centralized config (`llms.BEST_MODEL`, `llms.DEFAULT_MODEL`, etc.), not hardcoded.
- [ ] **Records eval data**: Every LLM response is recorded via `save_for_eval.record_ai_response()` with a descriptive `target` tag.
- [ ] **Prompt template created**: A `.j2` template exists in the `prompts/` directory for the system prompt and any task prompts.
- [ ] **Swappable**: The component can be replaced without modifying any other vertical component. Only the orchestrator and factory need to know about the new component.
- [ ] **Factory registered**: If using a factory pattern, the new component is registered in the factory's match/switch logic.
- [ ] **Orchestrator updated**: The orchestrator's pipeline topology is updated to include the new component (if it's a new stage, not just a new variant of an existing stage).

### Checklist: Adding a New Horizontal Service

Use this checklist when adding a new cross-cutting service (e.g., rate limiting, cost tracking, output validation):

- [ ] **Domain-agnostic API**: The service accepts generic inputs (strings, dicts, config objects). It has no knowledge of topic types, content formats, or which vertical component calls it.
- [ ] **Uses trust foundation types**: If the service operates on trust-related data, it imports models from `trust/`, not from other horizontal services.
- [ ] **Own log handler**: The `logging.json` configuration includes a dedicated handler and logger for the new service, routing to a separate log file (including trust-specific log streams if applicable).
- [ ] **Single responsibility**: The service does exactly one thing. If it does two things, split it into two services.
- [ ] **Parameterized**: The service is configured by its callers, not hardcoded for specific use cases.
- [ ] **No vertical imports**: The service does not import from any vertical component package.
- [ ] **No upward imports**: The service does not import from orchestration or meta-layer code.
- [ ] **Stateless or explicitly scoped**: The service is either stateless (like Prompt Service) or manages state with explicit scope (like Memory with user IDs, or Identity Service with agent IDs).
- [ ] **Integrated into existing verticals**: Existing vertical components are updated to consume the new service where appropriate.
- [ ] **Documented in this guide**: The service is added to the horizontal services list.

### Checklist: Adding a Trust Foundation Type

Use this checklist when adding a new model, enum, or function to the `trust/` foundation:

- [ ] **Pure**: The type has no I/O, no storage, no network calls, no logging. It is a Pydantic model or a deterministic function.
- [ ] **Shared by 2+ layers**: At least two layers above the foundation consume this type. If only one service needs it, keep it in that service.
- [ ] **Stable**: The type changes less frequently than the services that consume it. Schema changes are deliberate.
- [ ] **Dependency-free**: The type imports nothing from `utils/`, `agents/`, `governance/`, or orchestration code. Only standard library and Pydantic imports.
- [ ] **Re-exported**: The type is added to `trust/__init__.py` re-exports so consumers can import from the package directly.
- [ ] **Signed field boundary reviewed**: If the type is part of `AgentFacts`, determine whether new fields belong in `signed_metadata` (governance-grade, triggers re-signing) or `metadata` (operational, no re-signing).

### Checklist: Verifying Overall Composability

Use this checklist to verify the system's composability after any structural change:

- [ ] **Reading the orchestrator tells the whole story**: A developer reading the orchestrator method can understand the full pipeline without looking at any other file.
- [ ] **Any vertical component can be removed**: Removing one vertical component (e.g., deleting `HistoryWriter`) does not cause import errors in any other vertical component.
- [ ] **Any horizontal service can be mocked**: Each horizontal service can be replaced with a mock/stub for testing without modifying vertical components.
- [ ] **New verticals get horizontal services for free**: Adding a new writer or reviewer automatically gets prompt logging, eval capture, and guardrails because these are consumed via the shared abstract base class.
- [ ] **No layer imports upward**: No layer imports from a layer above it. The trust foundation has zero outward dependencies. Horizontal services do not import from vertical or orchestration. Vertical components do not import from orchestration or meta-layer.
- [ ] **Trust types come from the foundation**: Any `AgentFacts`, `Policy`, `Capability`, `TrustTraceRecord`, or other shared trust type is imported from `trust/`, never defined inside a service module.

---

## Directory Structure Convention

```
project/
├── trust/                              # TRUST FOUNDATION (shared kernel)
│   ├── __init__.py                     # Re-exports key types
│   ├── models.py                       # AgentFacts, Capability, Policy, AuditEntry
│   ├── enums.py                        # IdentityStatus, CertificationStatus, LifecycleState
│   ├── trace_schema.py                 # TrustTraceRecord
│   ├── signature.py                    # compute_signature(), verify_signature()
│   └── protocols.py                    # PolicyBackend protocol
│
├── utils/                              # HORIZONTAL SERVICES
│   ├── identity_service.py             # AgentFactsRegistry (trust L1)
│   ├── authorization_service.py        # Access decisions, policy evaluation (trust L2)
│   ├── trace_service.py                # TrustTraceRecord emission/routing (trust L5)
│   ├── credential_cache.py             # Ephemeral credential management
│   ├── policy_backends/                # External policy engine adapters
│   │   ├── yaml_backend.py
│   │   ├── opa_backend.py
│   │   └── cedar_backend.py
│   ├── prompt_service.py               # Template rendering
│   ├── llms.py                         # LLM configuration
│   ├── guardrails.py                   # Input validation
│   ├── long_term_memory.py             # Memory retrieval
│   ├── save_for_eval.py                # Eval data capture
│   └── human_feedback.py               # Human override recording
│
├── agents/                             # VERTICAL COMPONENTS
│   ├── task_assigner.py                # Orchestrator + classifier
│   ├── generic_writer_agent.py         # Abstract writer + concrete writers + factory
│   ├── reviewer_panel.py               # Reviewer agents + panel orchestration
│   ├── article.py                      # Shared data model (output schema)
│   ├── purpose_checker.py              # Validates actions against declared scope (trust L3+L4)
│   └── plan_builder.py                 # Captures task plan structure (trust L4)
│
├── governance/                         # META-LAYER
│   ├── lifecycle_manager.py            # Agent state machine, transition guards (trust L7)
│   ├── certification.py                # Evaluation suite, pass/fail gates (trust L6)
│   ├── compliance_reporter.py          # Audit export, regulatory reports (trust L6+L7)
│   └── trust_scoring.py               # Continuous trust scoring engine
│
├── prompts/                            # Prompt templates (data, not code)
│   ├── historian_system_prompt.j2
│   ├── math_writer_system_prompt.j2
│   ├── ReviewerAgent_review_prompt.j2
│   └── ...
├── data/                               # Pre-built indexes (for RAG)
├── evals/                              # Evaluation scripts
├── logging.json                        # Per-module log routing config
└── app.py                              # Entry point
```

The key structural signals:
- `trust/` (foundation) sits at the bottom -- all other packages import from it, it imports from none of them.
- `utils/` (horizontal) and `agents/` (vertical) are separate packages. Vertical components import from `utils/` and `trust/`. Nothing in `utils/` imports from `agents/`.
- `governance/` (meta-layer) imports from `trust/` and `utils/`. It never imports from `agents/` or orchestration code.

---

## Related Documents

| Document | Relationship |
|----------|-------------|
| [STYLE_GUIDE_PATTERNS.md](STYLE_GUIDE_PATTERNS.md) | Design patterns catalog (H1-H7, V1-V6) with implementation guidance. Patterns plug into the layering rules defined here. |
| [FOUR_LAYER_ARCHITECTURE.md](Architectures/FOUR_LAYER_ARCHITECTURE.md) | Trust Foundation integration analysis. Defines the trust foundation layer, identity service design, Runtime Trust Gate, ephemeral credentials, external policy engines, continuous trust scoring, and multi-agent readiness. |
| [TRUST_FRAMEWORK_ARCHITECTURE.md](TRUST_FRAMEWORK_ARCHITECTURE.md) | Seven-layer trust framework (L1-L7) mapped onto the four-layer grid. Each trust layer splits into types in the foundation and behavior in the appropriate grid layer. |
| [LAYER1_IDENTITY_ANALYSIS.md](LAYER1_IDENTITY_ANALYSIS.md) | Detailed L1 Identity implementation analysis. Structured analysis of the `AgentFacts` model, identity service design options, and storage patterns. |
