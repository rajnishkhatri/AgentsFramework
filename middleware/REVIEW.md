# middleware/ — Reviewer Enforcement Map

> Thin enforcement map for the unified reviewer (Frontend Ring, credentialed
> BFF). Cites rule IDs from [`middleware/AGENTS.md`](AGENTS.md) and
> [`frontend/AGENTS.md`](../frontend/AGENTS.md); never restates prose.

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| F-R2 (SDK imports confined to middleware/adapters/) | middleware/AGENTS.md §Local essentials | LLM | warning | FD1 |
| BFF holds no cloud credentials (credentialed layer) | middleware/AGENTS.md §Local essentials | AST (`check_secrets_in_public_env`) | critical | FD3 |
| `trace_id` flows verbatim, never generated here | middleware/AGENTS.md §Local essentials | LLM | warning | FD1 |
