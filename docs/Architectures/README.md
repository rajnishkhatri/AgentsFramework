# Architecture Documents

This folder contains the canonical architectural decision records and design specifications for the AgentsFramework system — backend, adapter ring, and frontend. Each document is self-contained and self-explanatory.

---

## Documents

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

### `FRONTEND_ARCHITECTURE.md`

High-level view of the Frontend Ring — the cross-process outer ring that sits above `agent_ui_adapter/` and exposes the agent to a Next.js + CopilotKit browser application. Introduces the hybrid architectural lens (onion + hexagonal + concentric rings), the three composition roots (`frontend/lib/composition.ts`, `middleware/composition.py`, `agent_ui_adapter/server.py`), the five sub-package structure mirrored per process (`ports/`, `adapters/`, `wire/`, `translators/`, `transport/`), the end-to-end data-flow diagram from browser to the four-layer backend, the substrate-swap matrix showing V2-Frontier and V3-Dev-Tier as adapter-wiring variants of one architecture, the nine frontend-side architecture invariants (F-R1..F-R9), and the architecture test plan.

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

- `docs/contributing/AGENT_UI_ADAPTER_ADAPTERS_HANDBOOK.md` — step-by-step recipe for contributors adding a new concrete adapter.
- `docs/STYLE_GUIDE_LAYERING.md` — three-layer style guide that the Four-Layer Architecture extends.
- `docs/STYLE_GUIDE_PATTERNS.md` — design patterns catalog (H1–H7, V1–V6).
- `docs/STYLE_GUIDE_FRONTEND.md` — prescriptive frontend style guide (W/P/A/T/X/C/B/U/S/O rule families) covering Next.js 15 + React 19 + CopilotKit v2 + AG-UI + Zod + Tailwind v4/shadcn + WorkOS + LangGraph SDK; the canonical document for frontend code review.
- `docs/TRUST_FRAMEWORK_ARCHITECTURE.md` — seven-layer agent trust framework.
- `docs/plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md` — V2-Frontier substrate profile (GCP + CopilotKit + WorkOS + Mem0/Langfuse self-hosted).
- `docs/plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md` — V3-Dev-Tier substrate profile (free-tier substrates; same architecture as V2-Frontier).