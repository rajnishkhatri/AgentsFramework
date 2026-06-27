# pyrightconfig.json — rationale

Track A typecheck sensor (`make typecheck`).

- **`typeCheckingMode: basic`** is deliberate. A `standard`/`strict` pass on a
  LangGraph/LiteLLM codebase surfaces a large initial backlog and drowns the
  signal. Basic catches the high-value soundness issues (wrong arity, None
  access, type mismatches) without the noise.
- **Scope** is the core four-layer Python tree (`trust`, `services`,
  `components`, `orchestration`, `meta`). `frontend`/`middleware` are
  TypeScript-governed; `tests`/`spikes`/`research` are excluded as non-shipping.
- **Raising strictness:** tighten per-directory (e.g. `trust/` to `strict`)
  via `executionEnvironments` once `basic` stays green over time.

JSON has no comment syntax — pyright treats a `"//"` key as an unrecognized
setting and warns on every run — so this rationale lives here, not inline.
