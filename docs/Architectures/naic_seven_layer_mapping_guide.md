# NAIC AI Systems Evaluation Tool → Seven-Layer Trust Framework

**A mapping guide showing how the AgentsFramework repo implements NAIC regulatory readiness in code.**

Repo: github.com/rajnishkhatri/AgentsFramework
Audience: Used as an interview reference and as a discussion artifact with Rob Jiang, Director, PwC P&C Insurance Operations & Technology.

---

## The headline

> Most carriers will treat the NAIC pilot as a survey to fill in. A few will treat it as a system to build. The seven-layer trust framework, implemented across a four-layer code architecture, gives a carrier the runtime artifacts that answer all four NAIC exhibits with evidence, not assertion.

For the deeper storytelling layer above this compact matrix, see [naic_narrative/00_overview_and_thesis.md](naic_narrative/00_overview_and_thesis.md). It walks through claims triage, term-life underwriting, and fraud-ring detection as concrete insurance agentic AI scenarios, then names architectural decisions and PR-sized gaps.

---

## The 4 NAIC exhibits in one paragraph each

**Exhibit A — AI Inventory.** Count and classify AI models by operational area: underwriting, claims, ratemaking, marketing. Flag models with direct consumer impact, material financial impact, or deployment within the last 12 months.

**Exhibit B — Governance.** Show your AI governance structure: board oversight, ERM and ORSA integration, unfair trade practices, data privacy, vendor standards, employee training, consumer disclosure.

**Exhibit C — High-Risk AI.** For each high-risk model, disclose name, type, origin (internal vs vendor), risk classification, testing protocols (drift, accuracy, discrimination), compliance review, and any regulatory actions.

**Exhibit D — Data.** Disclose data types feeding AI: credit scores, telematics, aerial imagery, social media, medical data. Flag each source as internal or third-party.

---

## The 7 trust layers in one line each

| Layer | Name | Function |
|-------|------|----------|
| 1 | Identity and Authentication | Cryptographic identity per agent, mTLS, signed registry |
| 2 | Authorization and Access Control | OAuth2, zero-trust, least privilege, OPA |
| 3 | Purpose and Policies | Declared intent and operational constraints |
| 4 | Task Planning and Explainability | Visible reasoning, tool selection, parameter logic |
| 5 | Observability and Traceability | Per-action logs with correlation IDs, replayable |
| 6 | Certification and Compliance | Structured evaluation, recertification gates |
| 7 | Governance and Lifecycle Management | Owner accountability, definition through retirement |

---

## The mapping matrix

P = primary mapping. S = secondary support. Blank = not material.

| | Exhibit A — Inventory | Exhibit B — Governance | Exhibit C — High-Risk | Exhibit D — Data |
|---|---|---|---|---|
| **L1 — Identity** | P | | S | S |
| **L2 — Authorization** | | S | P | S |
| **L3 — Purpose & Policy** | P | P | S | |
| **L4 — Task Planning** | | | P | |
| **L5 — Observability** | | S | P | P |
| **L6 — Certification** | | P | P | |
| **L7 — Governance** | S | P | | |

---

# Exhibit A — AI Inventory

## What the regulator wants

A defensible count of every AI system in production, classified by operational area, with consumer-impact and recency flags. Most carriers cannot produce this list from a single source today. They produce it by hand, from spreadsheets, after each regulatory request.

## Primary layer mappings

### Layer 3 — Purpose and Policies (PRIMARY)

This is where each agent declares what it does, in human-readable form, persistently stored in a registry. Inventory is a query against that registry.

**Repo evidence:** `trust/models.py` defines AgentFacts as a signed Pydantic type. AgentFacts records purpose, capability scope, owner, and policy bindings. The registry lives in `services/governance/`.

**Interview line:**
> "Exhibit A is a query, not a survey. Every agent in this framework registers its declared purpose at onboarding. The inventory is generated, not transcribed."

### Layer 1 — Identity and Authentication (PRIMARY)

Each agent has a unique cryptographic identity. That identity is the inventory key. No identity, no inventory entry. No inventory entry, no permission to run.

**Repo evidence:** `trust/models.py` defines Identity types. The trust kernel enforces signed identity as the precondition for any other action.

**Interview line:**
> "The identity layer is what makes the inventory complete by construction. You cannot run an agent without a signed identity, so you cannot have shadow AI."

## Secondary layer mappings

### Layer 7 — Governance and Lifecycle (SECONDARY)

Each inventory entry must link to an accountable owner. Lifecycle stage (definition, deployment, operations, decommissioning) determines which inventory category an agent belongs to. Recently-deployed agents are flagged automatically.

**Repo evidence:** `services/governance/phase_logger.py` tracks lifecycle stages. Phase logs are persisted to `cache/phase_logs/`.

---

# Exhibit B — Governance

## What the regulator wants

Evidence that AI governance is not theoretical. They want to see board reporting, ERM and ORSA integration, vendor standards, employee training records, consumer disclosure mechanisms, and clear accountability ownership.

## Primary layer mappings

### Layer 7 — Governance and Lifecycle Management (PRIMARY)

This is the direct match. Layer 7 in the framework is named after this regulatory category. Governance bodies, owner accountability, lifecycle stages, decommissioning protocols — all of these address Exhibit B requirements directly.

**Repo evidence:** Lifecycle stages are first-class in the framework (definition, design, onboarding, deployment, operations, certification, decommissioning). Each stage emits structured events.

**Interview line:**
> "The framework was designed with a lifecycle model that maps one-to-one to how a CRO would want to report AI governance to a board."

### Layer 6 — Certification and Compliance (PRIMARY)

Vendor standards, employee training requirements, and consumer disclosure all sit downstream of a certification process. Layer 6 is structured around UL and CSA precedents — standardized evaluation, recertification triggers, governance body oversight.

**Repo evidence:** Architecture invariants in `AGENTS.md` are enforced by `tests/architecture/`. The repo treats architectural compliance as testable. The same pattern extends to vendor agents — a vendor agent must pass the certification suite before onboarding.

**Interview line:**
> "Layer 6 is the most under-built part of carrier AI today. Most carriers treat certification as a one-time exercise. This framework treats it as a continuous gate."

### Layer 3 — Purpose and Policies (PRIMARY)

Governance starts with declared policy. A carrier cannot show board oversight of AI policy unless that policy is written, versioned, and bound to specific agents.

**Repo evidence:** `prompts/` contains all policy text as Jinja2 templates. Numeric thresholds live in `routing_config.py`. The repo separates "human intent" from "machine parameters" by design.

**Interview line:**
> "Policy is text. Thresholds are numbers. The meta-optimizer tunes numbers, humans write policy. That separation is the only way ERM oversight stays meaningful at scale."

## Secondary layer mappings

### Layer 5 — Observability and Traceability (SECONDARY)

Board reporting requires aggregate metrics. ERM integration requires event feeds. Both depend on Layer 5 telemetry.

**Repo evidence:** `logging.json` defines per-concern log handlers. Each service has its own logger. Logs go to `logs/prompts.log`, `logs/guards.log`, `logs/evals.log`, `logs/routing.log`.

---

# Exhibit C — High-Risk AI

## What the regulator wants

The deepest exhibit. Per-model disclosure for every high-risk system: name, type, origin, risk classification, testing protocols, compliance review history, regulatory actions. This is where most carriers will struggle most.

## Primary layer mappings

### Layer 4 — Task Planning and Explainability (PRIMARY)

The regulator asks how the model behaves under stress. Layer 4 captures the agent's reasoning trace — what it considered, what it selected, what it rejected. Without this layer, "testing protocols" is a black box.

**Repo evidence:** Task plans capture step sequence, tool selection rationale, parameter construction logic, and dependency graph. Stored alongside execution outcomes.

**Interview line:**
> "Drift and accuracy testing requires a baseline. The baseline lives in the task plan. Without a recorded plan, you cannot tell whether a model drifted or just got a different prompt."

### Layer 5 — Observability and Traceability (PRIMARY)

The Black Box recorder is the single strongest piece of Exhibit C evidence. Every LLM call is recorded with `user_id`, `task_id`, inputs, outputs, and decision trace.

**Repo evidence:** `services/governance/black_box.py` is the recorder. Recordings persist to `cache/black_box_recordings/`. Every call is replayable.

**Interview line:**
> "Black Box recordings produce the testing protocol evidence Exhibit C asks for. We do not generate evidence on request — we accumulate it continuously and query it when asked."

### Layer 2 — Authorization and Access Control (PRIMARY)

Risk classification is enforced through privilege scope. A high-risk model has elevated authorization. A low-risk model has constrained authorization. The classification is not metadata — it is runtime.

**Repo evidence:** OAuth2 and OPA policies are referenced in the trust framework. Tool registry in `services/tools/` includes per-tool allowlists.

**Interview line:**
> "Risk classification only matters if it changes what the model is allowed to do. In this framework, high-risk classification triggers stricter guardrails and higher-tier human review automatically."

## Secondary layer mappings

### Layer 1 — Identity (SECONDARY)

Vendor versus internal origin is an identity attestation question. Vendor agents carry signed proofs of origin. Internal agents are issued credentials from the internal CA.

### Layer 6 — Certification (SECONDARY)

Compliance review history is a certification artifact. Each certification cycle produces a record. Drift triggers re-certification.

---

# Exhibit D — Data

## What the regulator wants

Lineage. For every AI system, what data flows in, from where, and whether the source is internal or third-party. The implicit concern is unfair discrimination from proxy variables (credit scores correlating with protected class, telematics correlating with neighborhood, social media correlating with race).

## Primary layer mappings

### Layer 5 — Observability and Traceability (PRIMARY)

Data lineage is a traceability problem. Every input to every agent call is recorded with provenance metadata.

**Repo evidence:** Eval capture records every LLM call with `user_id`, `task_id`, prompt template version, model tier, and input source. Replayable from `cache/black_box_recordings/`.

**Interview line:**
> "Exhibit D is essentially asking for a join across the recording layer and the source-registry layer. Both already exist."

## Secondary layer mappings

### Layer 1 — Identity (SECONDARY)

Third-party data sources require attestation. A telematics vendor's data feed has a signed identity. That identity links the data to the contract, the privacy review, and the data sharing agreement.

### Layer 2 — Authorization (SECONDARY)

Access to specific data sources is governed by zero-trust policy. An agent that should not see medical data cannot, regardless of prompt. The denial is enforced at the runtime, not the prompt.

---

## Cross-cutting talking points

Use these only if the conversation invites them.

### "What is the one thing that surprises carriers when they start this work?"

> "Most discover that their inventory and their reality do not match. The agents in production are not the agents in the registry. The seven-layer framework makes that impossible by construction — no identity, no run."

### "Where is the biggest gap between what carriers have and what NAIC will ask for?"

> "Exhibit C. Most carriers can do AI inventory and can describe their governance committee. Few can produce per-model drift and accuracy evidence on demand. That is a Layer 5 and Layer 4 problem combined."

### "What is the operating-model implication?"

> "Every carrier will need an Agent Owner role. Each agent in inventory needs a named accountable owner with budget, authority, and a reporting line. Layer 7 of the framework requires this — it is not optional infrastructure."

### "How does this compare to model risk management in banking?"

> "It is the same pattern with different vocabulary. SR 11-7 in banking covers model validation, monitoring, and governance. NAIC is essentially establishing parallel discipline for insurance. Carriers that copy the bank pattern will be ahead."

---

## Three lines to deliver verbatim if the moment lands

1. **"The four NAIC exhibits are not four reports. They are four queries against one set of runtime artifacts. The artifacts have to exist first."**

2. **"A governance framework that lives in PowerPoint cannot answer Exhibit C. A governance framework that lives in code can."**

3. **"This is what model risk management looks like when it is built into the runtime instead of bolted on after the fact."**

---

## Closing context for Rob

The conversation Rob is moderating at Insurance Innovators 2026 is titled "Designing a trusted and scalable agentic carrier." This guide is one possible answer to that question. The seven-layer framework gives the design. The four-layer code architecture gives the scaling discipline. The NAIC mapping shows the regulatory readiness.

That is the trio you can offer PwC: a thinking framework, a working reference implementation, and a regulator-ready translation. Few candidates bring all three.
