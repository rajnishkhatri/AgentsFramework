---
type: narrative
title: 'NAIC Narrative Mapping: Overview and Thesis'
description: 'Purpose: A narrative companion to the compact NAIC mapping matrix.'
tags: [architecture]
---

# NAIC Narrative Mapping: Overview and Thesis

**Purpose:** A narrative companion to the compact NAIC mapping matrix. It explains how the NAIC AI Systems Evaluation Tool 4.0 and the December 2023 Model Bulletin translate into runtime artifacts in this workspace.

**Audience:** Insurance technology leaders, AI governance reviewers, carrier architecture teams, and regulators asking "show me" rather than "describe your process."

---

## The Governing Thought

The four NAIC exhibits are not four reports. They are four queries against one set of runtime artifacts.

The compact guide, [naic_seven_layer_mapping_guide.md](../naic_seven_layer_mapping_guide.md), already maps the NAIC exhibits to the seven-layer trust framework. This package takes the next step. It walks through three insurance scenarios and shows what evidence the [Four-Layer Architecture](../FOUR_LAYER_ARCHITECTURE.md), the governance services, and the trust kernel would emit as work happens.

The situation has changed since the first wave of AI governance decks. The NAIC AI Systems Evaluation Tool 4.0 frames the assessment as principle-based and tailorable. The December 2023 Model Bulletin asks insurers to maintain a documented AI System program across governance, risk controls, auditability, lifecycle coverage, vendor oversight, and unfair-trade-practice controls. A static spreadsheet can answer the first request once. Runtime evidence answers the second request continuously.

The complication is that agentic AI does not behave like a single model card. A claims agent plans, calls tools, changes parameters, delegates subtasks, and may route a decision to a human. An underwriting agent mixes internal policy, third-party data, signed identity, and authorization. A fraud detector may involve multiple agents coordinating through an event stream.

The question is: where does a carrier get defensible evidence for each NAIC exhibit without creating a parallel compliance bureaucracy?

The answer in this workspace is: identity, authorization, purpose, plan capture, black box recording, certification, and lifecycle governance all emit artifacts while the agent runs.

---

## The Four Exhibits as Runtime Queries

**Exhibit A - AI Inventory.** Query signed `AgentFacts` records, declared capabilities, policies, owner, version, lifecycle state, deployment age, and operational domain.

**Exhibit B - Governance.** Query lifecycle decisions, governance events, certification status, owner accountability, policy bindings, training references, vendor attestations, and board-level summaries.

**Exhibit C - High-Risk AI.** Query runtime authorization, risk classification, plan traces, guardrail outcomes, black box recordings, drift tests, compliance reviews, and recertification events.

**Exhibit D - Data.** Query recorded inputs, data source provenance, third-party source attestations, prompt/template versions, model tier, user/task identifiers, and lineage from source to decision.

The implementation substrate already has the start of that evidence model:

```37:52:trust/models.py
class AgentFacts(BaseModel):
    """The agent identity card -- central model of Layer 1."""

    agent_id: str
    agent_name: str
    owner: str
    version: str
    description: str = ""
    capabilities: list[Capability] = Field(default_factory=list)
    policies: list[Policy] = Field(default_factory=list)
    signed_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: IdentityStatus = IdentityStatus.ACTIVE
    valid_until: datetime | None = None
    parent_agent_id: str | None = None
    signature_hash: str = ""
```

```108:129:trust/models.py
class TrustTraceRecord(BaseModel):
    """Cross-layer trace event (schema_version=2).

    Spec: docs/Architectures/FOUR_LAYER_ARCHITECTURE.md lines 197-209. The shared schema
    that makes cross-layer queries possible across the seven trust layers.

    Schema version 2 adds three multi-agent fields (event_id,
    source_agent_id, causation_id) for event correlation and causal tracing.
    """

    schema_version: int = 2
    event_id: str
    source_agent_id: str | None = None
    causation_id: str | None = None
    timestamp: datetime
    trace_id: str
    agent_id: str
    layer: TraceLayer
    event_type: str
    details: dict[str, Any] = Field(default_factory=dict)
    outcome: TraceOutcome | None = None
```

Those two types are the carrier's evidence backbone: one says "who is allowed to act," the other says "what happened, under which layer, and with which outcome."

---

## Three Use Cases

| Use case | NAIC exhibits | Layer emphasis | Real-world pattern | Why it matters |
|---|---|---|---|---|
| Claims triage for auto bodily injury | A, B, C, D | L4 plan, L5 black box, L7 lifecycle | Claims intake copilots and fraud-aware triage tools | Claims is where explainability has the highest consumer-impact pressure. |
| Term-life underwriting with a $3M auto-approval ceiling | A, C, D | L1 identity, L2 authorization, L3 declared scope | Accelerated underwriting and lead-underwriting agents | Underwriting makes the data-lineage and unfair-discrimination question concrete. |
| Fraud-ring detection across claims and policies | B, C | L5 cross-agent correlation, Phase 3 blackboard | Network fraud analytics and synthetic/forged evidence detection | Fraud forces multi-agent evidence and causal traceability. |

Each use case is fictional, but each is anchored in production-shaped insurance patterns: claims GenAI, accelerated underwriting, and network fraud detection.

---

## Reader's Guide

Read this package in order if you want the full narrative:

1. [01_claims_triage_narrative.md](01_claims_triage_narrative.md) starts from a post-claim incident and shows how plan capture plus the black box produce Exhibit C evidence.
2. [02_underwriting_narrative.md](02_underwriting_narrative.md) follows a term-life underwriting agent through identity, authorization, declared scope, and data lineage.
3. [03_fraud_detection_narrative.md](03_fraud_detection_narrative.md) shows why multi-agent fraud detection needs `source_agent_id`, `causation_id`, and the blackboard pattern.
4. [04_architectural_decisions.md](04_architectural_decisions.md) captures the decisions this regulatory mapping forces.
5. [05_gaps_and_actionable_plan.md](05_gaps_and_actionable_plan.md) is the honest gap list: what exists today, what is specified, and what should be built next.

Read only [05_gaps_and_actionable_plan.md](05_gaps_and_actionable_plan.md) if you are turning this into PRs.

Read the compact [naic_seven_layer_mapping_guide.md](../naic_seven_layer_mapping_guide.md) first if you need interview talking points before the deeper story.

---

## What This Package Is Not

This is not a claim that the reference implementation is production-ready for a regulated carrier. It is a reference architecture and evidence model.

It is not legal advice. It translates public NAIC-style requirements into software architecture obligations.

It is not a replacement for model risk management. It shows where model risk artifacts should be emitted, stored, and joined to agent runtime evidence.

The strongest statement this package makes is narrower and more useful: a carrier should not wait until a regulator asks for Exhibit C to start collecting Exhibit C evidence. The runtime should be collecting it already.
