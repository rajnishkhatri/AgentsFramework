# Architectural Decisions Forced by the NAIC Mapping

**Purpose:** Capture the architectural choices that turn NAIC-style questions into runtime evidence.

The governing situation is straightforward. The NAIC exhibits ask for inventory, governance, high-risk controls, and data lineage. Agentic systems produce those facts only if the architecture makes them unavoidable.

The complication is that many AI governance implementations bolt evidence collection on after deployment. That produces brittle surveys, screenshots, and one-off exports.

The question is where the carrier should encode the control: in prompts, in process documents, in logs, or in runtime architecture.

The answer is the decisions below.

---

## Decision 1: Treat NAIC exhibits as runtime queries, not manual reports

**The decision.** Exhibit A/B/C/D evidence should be queryable from signed identities, trace events, black box recordings, eval logs, lifecycle decisions, and data lineage records.

**Alternatives considered.** Maintain a governance spreadsheet. Generate a quarterly model inventory. Ask each product team to fill out a questionnaire during audits.

**Why not those.** Manual evidence drifts from production. The highest-risk agent behavior happens during runtime: tool calls, data access, route decisions, guardrail outcomes, and delegation. A static report cannot prove those decisions were controlled.

**What this looks like.** `AgentFacts` answers inventory. `AuthorizationService` answers runtime permission. `TrustTraceRecord` answers event causality. `BlackBoxRecorder` answers replay and integrity. `PhaseLogger` answers rationale. Future data-lineage records answer source provenance.

**The trade-off.** More runtime instrumentation. A carrier must define event semantics before the regulator asks for them.

**The consequence.** Compliance becomes a projection of production evidence. Exhibit C no longer depends on a post-hoc narrative assembled from partial logs.

---

## Decision 2: Make high-risk classification an authorization input

**The decision.** High-risk classification should affect what an agent is allowed to do. It should not remain an unsigned label.

**Alternatives considered.** Store risk classification in `metadata`. Document risk level in the model card. Put a prompt instruction such as "seek human review for high-risk work."

**Why not those.** NAIC Exhibit C asks for high-risk controls. A label that does not change runtime behavior is not a control. Prompt instructions are advisory. Unsigned metadata can be useful operationally, but it is too weak for a regulated permission boundary.

**What this looks like.** The future state promotes risk classification into signed identity or signed policy material and feeds it into `AuthorizationService.authorize()` decisions. The service already emits `access_granted` and `access_denied` events.

**The trade-off.** This touches signed trust material, so it requires a re-signing plan and compatibility care.

**The consequence.** High-risk status becomes enforceable. The carrier can show not only that a system was classified high-risk, but that the classification changed its allowed actions.

---

## Decision 3: Put data lineage beside trust evidence, not inside prompt logs

**The decision.** Exhibit D requires a first-class data-source registry and lineage service, not only prompt input capture.

**Alternatives considered.** Store source names in prompt text. Attach provenance to eval records only. Let each domain agent define its own source metadata.

**Why not those.** Prompt text is not structured lineage. Eval records prove what went into a model call, but they do not prove vendor origin, contract reference, consent basis, jurisdictional permission, retention class, or source freshness. Domain-specific source metadata creates inconsistent Exhibit D answers across claims, underwriting, and fraud.

**What this looks like.** Add `DataSourceRecord` in the trust foundation only if it is pure, shared, stable, and dependency-free. Add `services/governance/data_lineage.py` to register and query source usage. Emit lineage-linked `TrustTraceRecord` events when data is accessed.

**The trade-off.** New trust type changes require discipline. Some source metadata may be sensitive and should be referenced by ID rather than copied into traces.

**The consequence.** Exhibit D becomes a join: agent identity + action + source record + trace event + decision outcome.

---

## Decision 4: Keep insurance-specific logic out of horizontal services

**The decision.** Claims, underwriting, and fraud logic should be vertical components or application-specific agents. Horizontal services should remain domain-agnostic.

**Alternatives considered.** Add claims-specific methods to authorization. Add underwriting-specific data checks to eval capture. Add fraud-ring concepts to the trust trace schema.

**Why not those.** Horizontal services are reused across use cases. Once a service knows what "bodily injury" or "term-life auto approval" means, the layer boundary is gone. The architecture tests exist to prevent exactly that style of coupling.

**What this looks like.** `AuthorizationService` receives `AgentFacts`, an action, and context. It does not know whether the action is claims, underwriting, or fraud. Insurance agents prepare context; horizontal services enforce generic controls and emit generic evidence.

**The trade-off.** Use-case code must translate domain facts into action names and policy context.

**The consequence.** The same evidence substrate can support P&C claims, life underwriting, fraud, and future insurance workflows without forking the governance layer.

---

## Decision 5: Use black box integrity for high-risk replay

**The decision.** High-risk workflows need append-only, integrity-checked execution recording.

**Alternatives considered.** Standard application logs. Prompt/response capture only. Human-written decision summaries.

**Why not those.** Standard logs are not designed for replay or tamper evidence. Prompt capture misses tool calls, plan changes, guardrail outcomes, and routing decisions. Human summaries are useful, but they are conclusions, not evidence.

**What this looks like.** `BlackBoxRecorder.record()` chains each event hash to the previous workflow hash. `export_for_compliance()` can join black box events with identity cards, audit trails, and phase decisions.

**The trade-off.** Storage and retention become governance questions. The carrier must decide what details belong in the event body and what should be stored as a reference.

**The consequence.** A claims or underwriting workflow can be replayed as a timeline with integrity status, not reconstructed from memory.

---

## Decision 6: Preserve causal fields before building a distributed bus

**The decision.** The architecture should standardize `event_id`, `source_agent_id`, and `causation_id` before adopting Kafka, Redis Streams, or another distributed transport.

**Alternatives considered.** Build a distributed event bus immediately. Let each future multi-agent flow define its own correlation scheme. Use only a workflow-level `trace_id`.

**Why not those.** A bus without causal semantics only moves ambiguity faster. Per-flow correlation produces inconsistent audit evidence. A single `trace_id` groups events, but it cannot explain which detector caused a fraud referral.

**What this looks like.** `TrustTraceRecord` v2 already carries the causal fields. Phase 3 can swap the transport while preserving the event envelope.

**The trade-off.** Some fields are underused until real multi-agent flows exist.

**The consequence.** The future fraud blackboard has an audit-ready event grammar before it has a distributed transport.

---

## Decision 7: Name gaps as PR-sized work, not architecture debt

**The decision.** The NAIC mapping should produce actionable gaps with owning layers and PR-sized implementation steps.

**Alternatives considered.** Mark the architecture "conceptually compliant." Keep a generic roadmap. Wait for a regulator or customer to request each artifact.

**Why not those.** Regulated AI work fails when gaps are vague. "Need better governance" does not tell an engineer where to put a module or which invariant it must satisfy.

**What this looks like.** [05_gaps_and_actionable_plan.md](05_gaps_and_actionable_plan.md) names each gap, severity, owning layer, concrete files, and a reviewable next action.

**The trade-off.** The gap list is more candid than a sales narrative.

**The consequence.** The framework becomes easier to harden. The work can move as small PRs rather than a broad compliance rewrite.
