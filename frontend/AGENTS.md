# frontend/ + middleware/ — Frontend Ring

> Nested guide for the Frontend Ring (`frontend/` and `middleware/`). Loads when
> Claude reads a file in either subtree. The canonical, authoritative document is
> the frontend style guide (linked below); this file is the on-disk entry point.

## Canonical document

@../docs/style-guides/STYLE_GUIDE_FRONTEND.md is the canonical frontend code-review
document. It mirrors the backend layering/patterns guides for the Frontend Ring
(Next.js 15 + React 19 + CopilotKit v2 + AG-UI + Zod + Tailwind v4/shadcn +
WorkOS + LangGraph SDK), defines the numbered rule families (F, W, P, A, T, X, C,
B, U, S, O), and includes paste-into-PR checklists for adapter, UI-component, and
wire/translator reviews.

## Key invariants

- **SDK imports** (CopilotKit, WorkOS, LangGraph SDK, Mem0, Langfuse, Drizzle)
  appear **only** in `frontend/lib/adapters/` or `middleware/adapters/`. No SDK
  type escapes past the adapter boundary.
- `frontend/lib/wire/` and `frontend/lib/trust-view/` are **pure Zod kernels**
  with zero outward dependencies.
- **`trace_id`** originates in the Python runtime adapter and flows verbatim
  through every layer — the browser **never** generates one.
- **BFF holds no cloud credentials.** All credential-bearing calls flow through
  `middleware/`. (The BFF runs on **Cloud Run** — `agent-frontend` — as of
  2026-06-18; Cloudflare was removed.)
- Strict **CSP with a per-request nonce**; no `'unsafe-inline'`. Generative-UI
  iframes use `sandbox="allow-scripts"` only.

## Review dimensions + auto-rejects

The frontend reviewer (`prompts/codeReviewer/frontend/`) encodes the §23 review
checklists as seven dimensions: **FD1** Layering, **FD2** Patterns, **FD3**
Security, **FD4** Accessibility, **FD5** Performance & Streaming, **FD6** Tests,
**FD7** Anti-Patterns. It **auto-rejects** on the security/trust-critical
anti-patterns FE-AP-4, FE-AP-6, FE-AP-7, FE-AP-12, FE-AP-18, FE-AP-19.

## Deep-dive references

- @../docs/Architectures/FRONTEND_ARCHITECTURE.md
- @../docs/Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md
- @../docs/Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md
