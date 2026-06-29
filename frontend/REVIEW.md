# frontend/ — Reviewer Enforcement Map

> Thin enforcement map for the unified reviewer's **FD1–FD7** frontend
> dimensions (activated when the routed language is TS/TSX). Cites rule IDs from
> [`frontend/AGENTS.md`](AGENTS.md) and the canonical
> [`STYLE_GUIDE_FRONTEND.md`](../docs/style-guides/STYLE_GUIDE_FRONTEND.md);
> never restates prose. The TS deterministic predicates
> (`code_reviewer/frontend/tools.py`) run first and win.
>
> This map **supersedes** the legacy `prompts/codeReviewer/frontend/` and
> `prompts/codeReviewer/explainability_frontend/` prompt families — their FD
> content is cited here, not duplicated.

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| FD1 Layering (SDK imports only in adapters/) | frontend/AGENTS.md §Key invariants | LLM | warning | FD1 |
| FD2 Patterns | frontend/AGENTS.md §Review dimensions | LLM | note | FD2 |
| FD3 Security — CSP strict, no `'unsafe-inline'` | frontend/AGENTS.md §Key invariants | AST (`check_csp_strict`) | critical | FD3 |
| FD3 Security — iframe `sandbox="allow-scripts"` only | frontend/AGENTS.md §Key invariants | AST (`check_iframe_sandbox`) | critical | FD3 |
| FD3 Security — BFF holds no cloud credentials | frontend/AGENTS.md §Key invariants | AST (`check_secrets_in_public_env`) | critical | FD3 |
| FD3 Security — no JWT in browser storage | frontend/AGENTS.md §Key invariants | AST (`check_jwt_storage`) | critical | FD3 |
| FD4 Accessibility | frontend/AGENTS.md §Review dimensions | LLM | warning | FD4 |
| FD5 Performance & Streaming | frontend/AGENTS.md §Review dimensions | LLM | note | FD5 |
| FD6 Tests | frontend/AGENTS.md §Review dimensions | LLM | warning | FD6 |
| FD7 Anti-Patterns (auto-reject FE-AP-4/6/7/12/18/19) | frontend/AGENTS.md §Review dimensions | LLM | critical | FD7 |
| `trace_id` never generated in the browser | frontend/AGENTS.md §Key invariants | LLM | warning | FD1 |
