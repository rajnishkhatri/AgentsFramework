# Architecture documents — bundle index

OKF bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md).

- [Agent planning and tool selection](AGENT_PLANNING_AND_TOOL_SELECTION.md) — The agent plans in two stages, both pure functions.
- [Agent UI Adapter — Adapters Deep Dive](AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md) — Scope: agent_ui_adapter/adapters/ and the rules governing it
- [Agent UI Adapter — Architecture Overview](AGENT_UI_ADAPTER_ARCHITECTURE.md) — Scope: agent_ui_adapter/ package
- [AWS Deployment Architecture](AWS_DEPLOYMENT_ARCHITECTURE.md) — Scope: Deployment topology, infrastructure mapping, and cloud-native service alignment for the LangGraph-based AgentsFramework ReAct agent on Amazon Web Services (AWS).
- [Azure Deployment Architecture](AZURE_DEPLOYMENT_ARCHITECTURE.md) — Scope: Deployment topology, infrastructure mapping, and cloud-native service alignment for the LangGraph-based AgentsFramework ReAct agent on Microsoft Azure.
- [Backend PR Review Checklists](BACKEND_PR_CHECKLISTS.md) — Scope: Reviewer aid for PRs touching the Python backend (trust/, services/, components/, orchestration/, meta/, StructuredReasoning/, agent_ui_adapter/).
- [Backend Solution Architecture](BACKEND_SOLUTION_ARCHITECTURE.md) — Scope: The Python backend of the AgentsFramework workspace — trust/, services/, components/, orchestration/, meta/, the StructuredReasoning/ mini-stack, and the agent_ui_adapter/
- [Cloud Provider Comparison — AWS / GCP / Azure](CLOUD_PROVIDER_COMPARISON.md) — Scope: Per-tier, list-price cost comparison and recommendation for deploying the AgentsFramework backend (per BACKEND_SOLUTION_ARCHITECTURE.md §3.3 and §5.5) on AWS, GCP, or Azure.
- [Deep Agent Loop Upgrade - SCQA Justification Guide](DEEP_AGENT_SCQA_IMPLEMENTATION_GUIDE.md) — This guide reframes the approved implementation plan using SCQA so researchers and architects can evaluate:
- [Four-Layer Architecture with Trust Foundation](FOUR_LAYER_ARCHITECTURE.md) — Analysis method: Feasibility integration of Trust Framework (L1 Identity) with Composable Layering Architecture
- [Frontend Architecture — Overview](FRONTEND_ARCHITECTURE.md) — Scope: the complete client-to-graph vertical slice
- [Frontend — Ports and Adapters Deep Dive](FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) — Scope: frontend/lib/ports/, frontend/lib/adapters/, middleware/ports/, middleware/adapters/
- [Frontend Port Deviations — V3-Dev-Tier (Canonical)](FRONTEND_PORT_DEVIATIONS_V3.md) — Status: Accepted (as of Sprint 3, V3-Dev-Tier).
- [Frontend — Wire and Translators Deep Dive](FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md) — Scope: frontend/lib/wire/, frontend/lib/trust-view/, frontend/lib/translators/, frontend/lib/transport/
- [GCP Deployment Architecture](GCP_DEPLOYMENT_ARCHITECTURE.md) — Scope: Deployment topology, infrastructure mapping, and cloud-native service alignment for the LangGraph-based AgentsFramework ReAct agent on Google Cloud Platform (GCP).
- [Guardrails Dimension Space](GUARDRAILS_DIMENSION_SPACE.md) — Status: Sprint 0 contract (frozen) | Documentation only — no runtime code, no ML in this sprint
- [Layer 1: Identity and Authentication -- Structured Analysis](LAYER1_IDENTITY_ANALYSIS.md) — Analysis method: Pyramid Principle with MECE decomposition
- [Planning Pipeline — End-to-End System Diagram](PLANNING_PIPELINE_SYSTEM_DIAGRAM.md) — Status: Operational companion to planning_pipeline_tiered_loops.design.md §B.
- [PLAYWRIGHT_TESTING_ARCHITECTURE](PLAYWRIGHT_TESTING_ARCHITECTURE.md) — 
- [Seven-Layer Agent Trust Framework -- High-Level Architecture](TRUST_FRAMEWORK_ARCHITECTURE.md) — Analysis method: Pyramid Principle with MECE decomposition
- [Notes on the AgentsFramework Architecture](agents_framework_architecture_notes.md) — Author: Rajnish Khatri
- [NAIC Narrative: Insurance Agentic AI Mapping to the Four-Layer Architecture](naic_insurance_mapping_gemni31.md) — Model: Gemini 3.1 Pro
- [NAIC Narrative Mapping: Overview and Thesis](naic_narrative/00_overview_and_thesis.md) — Purpose: A narrative companion to the compact NAIC mapping matrix.
- [Claims Triage Narrative](naic_narrative/01_claims_triage_narrative.md) — Scenario: A fictional carrier deploys a ClaimsTriageAgent for auto bodily-injury claims.
- [Underwriting Narrative](naic_narrative/02_underwriting_narrative.md) — Scenario: A fictional carrier deploys a TermLifeUnderwritingAgent for accelerated term-life underwriting with a $3M auto-approval ceiling.
- [Fraud Detection Narrative](naic_narrative/03_fraud_detection_narrative.md) — Scenario: A fictional carrier deploys a multi-agent fraud-ring detector across claims, policy, payment, and document evidence.
- [Architectural Decisions Forced by the NAIC Mapping](naic_narrative/04_architectural_decisions.md) — Purpose: Capture the architectural choices that turn NAIC-style questions into runtime evidence.
- [NAIC Gaps and Actionable Plan](naic_narrative/05_gaps_and_actionable_plan.md) — Purpose: Name the gap between the current workspace and a carrier-grade NAIC evidence program, then convert each gap into a PR-sized action.
- [NAIC Narrative: Insurance Agentic AI Mapping to the Four-Layer Architecture](naic_narrative_insurance_mapping_sonnet46.md) — Model: Claude Sonnet 4.6
- [NAIC AI Systems Evaluation Tool → Seven-Layer Trust Framework](naic_seven_layer_mapping_guide.md) — A mapping guide showing how the AgentsFramework repo implements NAIC regulatory readiness in code.
