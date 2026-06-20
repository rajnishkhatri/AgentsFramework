---
type: narrative
title: 'NAIC Gaps and Actionable Plan'
description: 'Purpose: Name the gap between the current workspace and a carrier-grade NAIC evidence program, then convert each gap into a PR-sized action.'
tags: [architecture]
---

# NAIC Gaps and Actionable Plan

**Purpose:** Name the gap between the current workspace and a carrier-grade NAIC evidence program, then convert each gap into a PR-sized action.

This is intentionally candid. The Four-Layer Architecture provides the substrate, but a regulated insurance deployment needs more than the substrate.

Severity key:

- **P0:** Needed before a carrier can safely expose this workflow to regulated production use.
- **P1:** Needed for strong NAIC response and enterprise governance readiness.
- **P2:** Useful hardening or reporting maturity.

---

## Gap Table

| ID | Gap | Severity | Owning layer | Concrete PR-sized action |
|---|---|---:|---|---|
| N-1 | Consumer disclosure and adverse-action surface | P0 | Horizontal Services + Frontend Ring | Add `services/governance/consumer_disclosure.py` with a pure disclosure event builder, then add a `middleware/adapters/disclosure_sender.py` adapter for carrier-specific delivery. |
| N-2 | Bias and disparate-impact testing | P0 | Meta-Layer | Add `meta/fairness_tester.py` that consumes eval/trace fixtures and emits `TrustTraceRecord(event_type="fairness_evaluated")`; start with mocked datasets and failure-path tests. |
| N-3 | Vendor agent attestation pipeline | P0 | Trust Foundation + Horizontal Services | Add a signed `vendor_attestation` shape only after a trust-schema plan; then add `services/governance/vendor_onboarding.py` to validate vendor evidence before registry insertion. |
| N-4 | Drift threshold to recertification trigger | P1 | Meta-Layer + Governance Services | Wire drift-threshold breach handling to a governance event consumer that emits `recertification_triggered`; keep orchestration out of the loop. |
| N-5 | ERM / ORSA risk register export | P1 | Meta-Layer | Add `meta/compliance_reporter.py` with `export_orsa_section()` projecting trace counts, high-risk inventory, incidents, and recertification status. |
| N-6 | Board-level dashboard projection | P1 | Meta-Layer | Add `meta/board_dashboard.py` that reads `TrustTraceRecord` JSONL and produces Exhibit A/B/C/D summaries with no runtime dependency on orchestration. |
| N-7 | Data source registry with third-party provenance | P0 | Trust Foundation + Horizontal Services | Add `DataSourceRecord` only if it satisfies trust-kernel criteria; add `services/governance/data_lineage.py` to record source access and contract/consent references. |
| N-8 | High-risk classification as runtime authorization | P0 | Trust Foundation + Authorization Service | Promote risk classification from unsigned metadata to signed policy/identity material and feed it into `AuthorizationService.evaluate()` for sensitive actions. |
| N-9 | Recertification on model version change | P1 | Governance Services | Add a lifecycle handler that detects `AgentFacts.version` change and emits/records recertification requirement before deployment. |
| N-10 | Employee training record linkage | P1 | Governance Services | Add `services/governance/training_registry.py` and store `owner_training_certification_ref` as unsigned operational metadata linked to owner accountability. |
| N-11 | Multi-state regulatory variation | P1 | Authorization + Policy Backend | Extend policy-evaluation context to carry `jurisdiction`, then add tests for state-specific data-source and adverse-action policy differences. |
| N-12 | Pyramid agent defense-in-depth parity | P0 | StructuredReasoning + Services | Wire output guardrail and per-tool authorization into `StructuredReasoning/orchestration/` using the same service boundaries as the main ReAct loop. |
| N-13 | SIU referral causality projection | P2 | Meta-Layer + Trace Sink | Add a read-model builder that groups fraud events by `trace_id`, `source_agent_id`, and `causation_id` to produce an SIU referral bundle. |
| N-14 | Retention and legal-hold policy for black box recordings | P1 | Governance Services + Storage Adapter | Add retention metadata and legal-hold references to compliance exports; avoid deleting or mutating the existing append-only trace format. |
| N-15 | Human review outcome feedback | P1 | Components + Governance Services | Add a structured event for human approve/reject/override outcomes so claims and underwriting feedback can be joined to original agent recommendations. |

---

## Implementation Order

Start with the gaps that reduce regulatory risk without touching signed trust types.

1. **N-2 fairness tester.** It can live in `meta/`, consume fixtures, and emit governance trace records without changing runtime behavior.
2. **N-1 consumer disclosure event builder.** Start with event construction and tests before adding delivery adapters.
3. **N-7 data lineage service.** Build the service interface and source-access events first; defer trust-kernel type changes until the schema is reviewed.
4. **N-8 high-risk authorization.** This is important but touches signed material, so it needs a separate plan and re-signing path.
5. **N-12 StructuredReasoning parity.** This closes a known defense-in-depth gap before the pyramid agent handles untrusted inputs.

---

## PR Sketches

### PR 1: Add Fairness Tester Skeleton

**Files:**

- `meta/fairness_tester.py`
- `tests/meta/test_fairness_tester.py`
- optional fixture under `tests/fixtures/fairness/`

**Acceptance criteria:**

- consumes deterministic fixture records;
- computes group-level acceptance-rate deltas;
- emits a `TrustTraceRecord`-shaped result;
- includes rejection tests for missing protected-group labels and insufficient sample size;
- performs no live LLM calls.

### PR 2: Add Consumer Disclosure Event Builder

**Files:**

- `services/governance/consumer_disclosure.py`
- `tests/services/governance/test_consumer_disclosure.py`

**Acceptance criteria:**

- builds a disclosure event from decision outcome, reason, trace ID, and consumer-facing explanation reference;
- does not send email/SMS/letters directly;
- records adverse-action cases distinctly from neutral routing cases;
- avoids storing protected health or financial details in the disclosure body.

### PR 3: Add Data Lineage Service

**Files:**

- `services/governance/data_lineage.py`
- `tests/services/governance/test_data_lineage.py`
- later: `trust/models.py` only after schema approval

**Acceptance criteria:**

- registers source IDs with source type, owner, contract reference, and jurisdiction scope;
- records source access by `agent_id`, `trace_id`, action, and purpose;
- rejects unregistered source usage;
- emits an Exhibit D export shape grouped by agent and workflow.

### PR 4: Promote High-Risk Classification Into Authorization

**Files:**

- `trust/models.py`
- `services/authorization_service.py`
- `tests/trust/`
- `tests/services/test_authorization_service.py`

**Acceptance criteria:**

- risk classification is part of signed or policy-bound material;
- sensitive actions can require human approval or deny based on risk class;
- existing identities have a documented re-signing/migration path;
- architecture tests still pass.

### PR 5: Add Human Review Outcome Feedback

**Files:**

- `components/` module for review outcome normalization;
- `services/governance/review_feedback.py`;
- tests under the owning layers.

**Acceptance criteria:**

- records human approval, rejection, override, and escalation outcomes;
- links outcome to original `trace_id` and recommendation event;
- emits aggregate metrics suitable for Exhibit C review.

---

## What Not to Build Yet

Do not build the distributed blackboard before there is a second real consumer. The [Four-Layer Architecture](../FOUR_LAYER_ARCHITECTURE.md) already names Phase 3; the right next step is preserving event semantics, not operating Kafka for a reference implementation.

Do not add insurance domain logic to `AuthorizationService`. Use action names, policy context, and policy backends. Keep claims and underwriting concepts in vertical code.

Do not broaden the trust kernel casually. `trust/` types must be pure, shared, stable, and dependency-free. Schema changes should be deliberate because signed fields affect authorization and migration.

---

## Definition of Done for NAIC Readiness

This package should be considered NAIC-ready only when the workspace can generate the following from stored artifacts:

- Exhibit A inventory from signed identities and lifecycle state;
- Exhibit B governance report from lifecycle, certification, training, vendor, and board projections;
- Exhibit C high-risk dossier from authorization, guardrails, plan capture, black box recordings, fairness/drift tests, and human review outcomes;
- Exhibit D data report from source registry, source-access traces, third-party provenance, contract references, and jurisdiction rules.

The current architecture supports the evidence pattern. The gap list names the remaining implementation work.
