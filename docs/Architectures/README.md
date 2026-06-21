# Architecture Documents

This folder contains the canonical architectural decision records and design specifications for the AgentsFramework system — backend, adapter ring, and frontend. Each document is self-contained and self-explanatory.

> **Start here for the backend:** `BACKEND_SOLUTION_ARCHITECTURE.md` — the indexed solution architecture covering trust kernel, services, components, orchestration, `StructuredReasoning/`, and the `agent_ui_adapter/` ring; includes current-state, target-state, gap analysis (G-1..G-12), and architectural invariants (I-1..I-14). The other documents in this folder are referenced from there as deep dives.

---

## Documents

### `BACKEND_SOLUTION_ARCHITECTURE.md`

The canonical "start here" backend solution architecture. Indexes every other backend doc in this folder and frames them as deep dives. Covers: governing thought + SCQA, 14 architectural invariants with enforcement status, three identity views (layered onion, hexagonal, concentric rings), the current state of all five backend layers plus the `StructuredReasoning/` peer mini-stack and the `agent_ui_adapter/` outer ring, five cross-cutting concerns (defense-in-depth security, trust-trace and governance feedback, observability, configuration surface, persistence/cache), the architecture-enforcement test catalog (10 test files), pattern applicability (H1–H7, V1–V6), anti-patterns (AP-1..AP-5, TAP-1..TAP-4), a 12-row gap analysis with severity and recommended actions (G-1..G-12), and seven target-state milestones with measurable success criteria. Includes mermaid diagrams for both the ReAct loop topology and the Pyramid loop topology (PR 1 walking-skeleton today, PR 2/PR 3 target). PR review checklists are split into a companion document.

**Audience:** Architects gating PRs against layer rules; external readers using it as an onboarding or design-review reference.

---

### `BACKEND_PR_CHECKLISTS.md`

Paste-into-PR review checklists for backend changes. Eight checklists: (1) placing a new module, (2) adding a new horizontal service, (3) adding a new vertical component, (4) adding a new orchestration node, (5) adding a new tool, (6) changing a trust kernel type (with re-signing flow), (7) adding a new adapter family, (8) always-on quick gate. Each checkbox row cites the invariant (I-x), pattern (Hx/Vx), or anti-pattern (AP-x/TAP-x) it guards. Includes a reviewer escalation matrix listing the stop-the-line patterns.

**Audience:** PR reviewers needing a verbatim paste-into-comment checklist.

---

### `FOUR_LAYER_ARCHITECTURE.md`

The foundational four-layer architecture specification: Trust Foundation (shared kernel of pure types and crypto), Horizontal Services (domain-agnostic infrastructure), Vertical Components (framework-agnostic domain logic), Orchestration Layer (topology-only thin wrappers), and Meta-Layer (offline governance and certification). Includes the hexagonal ports model, dependency rules table, dual state machine contract, runtime trust gate, governance feedback loops, and three-phase event-driven migration path.

**Audience:** Architects, service authors, anyone placing a new module in the project.

---

### `AGENT_UI_ADAPTER_ARCHITECTURE.md`

High-level view of how `agent_ui_adapter/` sits above the four-layer backend as the outer adapter ring, exposing the backend to AG-UI clients over SSE. Covers the five sub-packages (`ports/`, `adapters/`, `wire/`, `translators/`, `transport/`), the composition root (`server.py`), and the role of `adapters/runtime/` as the sole third-party SDK boundary. Includes a data-flow diagram, dependency summary table, and a phase progression overview.

**Audience:** Architects and code reviewers deciding whether a change belongs inside or outside `agent_ui_adapter/`.

---

### `AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md`

Exhaustive specification for `agent_ui_adapter/adapters/`. Covers the adapter grid, what belongs in `adapters/`, the full contents and anatomy of `adapters/runtime/` (`MockRuntime`, `LangGraphRuntime`), the formalized runtime translation contract (event mapping tables, trace-id propagation, error translation, cancellation semantics, trust-trace boundaries), the complete hexagonal dependency rules table, the conformance test bundle requirement, the composition root wiring pattern, the logging convention, the three-phase extension roadmap, and the relationship to the Four-Layer Architecture.

**Audience:** Maintainers of `adapters/runtime/` and future authors of new adapter families.

---

### `CLOUD_PROVIDER_COMPARISON.md`

Per-tier list-price cost comparison and recommendation for deploying the backend on AWS, GCP, or Azure. Covers three workload tiers anchored to concrete numbers (Tier A dev / ~5 devs, Tier B small-prod / ~10–20 SSE peak, Tier C scale / ~200 SSE peak with multi-region active-passive Postgres), a per-tier recommendation table with monthly cost bands, per-tier line-item cost models (compute + data + network + observability + secrets) for each cloud, a lock-in / portability summary mapping the four code refactors from each per-cloud architecture's §6 against invariant I-9 (SDK isolation in `agent_ui_adapter/adapters/runtime/`), a decision-criteria flowchart, and seven open questions a team needs to resolve before committing (live workload measurement, NFS strategy on GCP, commit-discount posture, cross-region geography, LLM token share, Aurora/AlloyDB upgrades, WAF/DDoS posture for Azure). Cost numbers are list-price only and surface the dominant Tier-C caveat: 1y/3y commit discounts close ~75% of the inter-cloud spread, and LLM token spend dwarfs the IaaS bill by an order of magnitude. Projects the three pyramids in `docs/analysis/CLOUD_COMPARISON_PYRAMID_ANALYSIS.md` (the planning artifact); cites `AWS_DEPLOYMENT_ARCHITECTURE.md`, `GCP_DEPLOYMENT_ARCHITECTURE.md`, and `AZURE_DEPLOYMENT_ARCHITECTURE.md` as inputs.

**Audience:** Architects, FinOps leads, and engineering managers deciding which cloud to deploy on.

---

### `naic_narrative/`

Narrative deep-dive package mapping the NAIC AI Systems Evaluation Tool 4.0 and December 2023 Model Bulletin to the Four-Layer Architecture and governance controls. Starts with `naic_narrative/00_overview_and_thesis.md`, then walks through three insurance agentic AI use cases: claims triage, term-life underwriting, and fraud-ring detection. Includes SCQA-style architectural decisions and a PR-sized gap/action plan for NAIC readiness. This is the deeper storytelling layer above `naic_seven_layer_mapping_guide.md`.

**Audience:** Insurance technology leaders, AI governance reviewers, carrier architects, and interview or client-review readers who need to see how runtime artifacts answer NAIC Exhibit A/B/C/D.

---

### `FRONTEND_ARCHITECTURE.md`

High-level view of the Frontend Ring — the cross-process outer ring that sits above `agent_ui_adapter/` and exposes the agent to a Next.js + CopilotKit browser application. Introduces the hybrid architectural lens (onion + hexagonal + concentric rings), the four composition roots (`frontend/lib/composition.ts`, `frontend/lib/composition_browser.ts`, `middleware/composition.py`, `agent_ui_adapter/server.py`), the five sub-package structure mirrored per process (`ports/`, `adapters/`, `wire/`, `translators/`, `transport/`), the end-to-end data-flow diagram from browser to the four-layer backend, the substrate-swap matrix showing V2-Frontier and V3-Dev-Tier as adapter-wiring variants of one architecture, the nine frontend-side architecture invariants (F-R1..F-R9), and the architecture test plan.

**Audience:** Architects and all engineers placing a new module anywhere in `frontend/`, `middleware/`, or any future cross-process ring.

---

### `FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md`

Exhaustive specification for `frontend/lib/ports/`, `frontend/lib/adapters/`, `middleware/ports/`, and `middleware/adapters/`. Covers the eight driven ports (`AgentRuntimeClient`, `AuthProvider`, `ThreadStore`, `MemoryClient`, `TelemetrySink`, `FeatureFlagProvider`, `ToolRendererRegistry`, `UIRuntime`) with per-port interface signatures, behavioral contracts, and conformance test sketches; the full adapter grid with named-but-empty slots; per-adapter specifications for every V2/V3 concrete implementation (constructor parameters, SDK version pins, translation contracts, error translation, idempotency, trust-trace boundaries); the hexagonal dependency rules table; the composition-root wiring pattern (TypeScript + Python skeletons); the conformance test bundle requirement; the logging convention; and the three-phase extension roadmap.

**Audience:** Maintainers of any adapter family and future authors of new concrete adapters or new port interfaces.

> **Important:** §4.1, §4.2, §4.3 of this document describe the Sprint 0 spec. The Sprint 3 (V3-Dev-Tier) implementation deviates deliberately — see `FRONTEND_PORT_DEVIATIONS_V3.md` for the canonical signatures.

---

### `FRONTEND_PORT_DEVIATIONS_V3.md`

Canonical Sprint-3 (V3-Dev-Tier) refinements to three ports: `AgentRuntimeClient` (split `stream()` into `createRun()` + `streamRun()`; remove `getState()` — moved to `ThreadStore`), `AuthProvider` (remove `signIn()` — replaced by redirect-based flow; return `IdentityClaim` instead of `Session` — closes a token-leak surface), and `ThreadStore` (every method takes `IdentityClaim` for defense-in-depth ownership scoping; collapse `update()` → `rename()`, drop `delete()` since `archive()` already soft-deletes, defer `getMessages()` until message volume justifies a separate table). For each port: original spec, implemented signature, per-row delta with rationale, preserved invariants (F-R3, F-R8, A4, FE-AP-7, FE-AP-18), and a forward-looking trigger table for when (if ever) to revisit. Promotes the implemented surface to canonical for V3-Dev-Tier.

**Audience:** Architects and code reviewers comparing the implemented `frontend/lib/ports/` to the original deep-dive spec.

---

### `FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md`

Exhaustive specification for `frontend/lib/wire/`, `frontend/lib/trust-view/`, `frontend/lib/translators/`, and `frontend/lib/transport/`. Covers the two TypeScript shared kernels (`wire/` mirroring `agent_ui_adapter/wire/`; `trust-view/` providing read-only identity shapes); all four `wire/` modules with full Zod schema definitions; the `trust-view/` boundary rules (what is and is not permitted in the frontend trust kernel); the four pure-function translator modules with input-to-output tables; the SSE client (`sse_client.ts`) and BFF proxy (`edge_proxy.ts`) with cross-substrate notes for Cloudflare; the wire-schema drift detection CI mechanism (Python JSON Schema export vs hand-authored Zod schemas); the complete AG-UI event translation contract table; and trust-trace propagation rules across the full browser-to-backend path.

**Audience:** Engineers working on SSE transport, wire schema changes, translator logic, or the TypeScript shared kernels.

---

## See Also

- `docs/analysis/CLOUD_COMPARISON_PYRAMID_ANALYSIS.md` — the Pyramid-Analysis planning artifact behind `CLOUD_PROVIDER_COMPARISON.md`. Three pyramids (one per workload tier) with evidence tables citing public pricing pages, eight-check validation logs, and the SCQA framing-notes appendix.
- `docs/contributing/AGENT_UI_ADAPTER_ADAPTERS_HANDBOOK.md` — step-by-step recipe for contributors adding a new concrete adapter.
- `docs/style-guides/STYLE_GUIDE_LAYERING.md` — three-layer style guide that the Four-Layer Architecture extends.
- `docs/style-guides/STYLE_GUIDE_PATTERNS.md` — design patterns catalog (H1–H7, V1–V6).
- `docs/style-guides/STYLE_GUIDE_FRONTEND.md` — prescriptive frontend style guide (W/P/A/T/X/C/B/U/S/O rule families) covering Next.js 15 + React 19 + CopilotKit v2 + AG-UI + Zod + Tailwind v4/shadcn + WorkOS + LangGraph SDK; the canonical document for frontend code review.
- `docs/Architectures/TRUST_FRAMEWORK_ARCHITECTURE.md` — seven-layer agent trust framework.
- `docs/Architectures/naic_narrative/00_overview_and_thesis.md` — narrative NAIC deep dive connecting Exhibit A/B/C/D to claims, underwriting, fraud, runtime trace evidence, and the Four-Layer Architecture.
- `docs/Architectures/naic_narrative_insurance_mapping_sonnet46.md` — single-file consolidated edition of the full NAIC narrative package (§0 overview, §1 claims triage, §2 underwriting, §3 fraud detection, §4 seven architectural decisions, §5 fifteen-gap actionable plan, §6 cross-reference index). Use this for sharing or printing; use the `naic_narrative/` folder for per-section editing.
- `docs/plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md` — V2-Frontier substrate profile (GCP + CopilotKit + WorkOS + Mem0/Langfuse self-hosted).
- `docs/plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md` — V3-Dev-Tier substrate profile (free-tier substrates; same architecture as V2-Frontier).