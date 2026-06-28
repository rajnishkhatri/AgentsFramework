# middleware/ — Frontend Ring (credentialed BFF middleware)

> Nested guide. `middleware/` is part of the **Frontend Ring**. The full ring
> guide and canonical style guide live in `frontend/AGENTS.md` — read that for
> the F/W/P/A/T/X/C/B/U/S/O rule families and the security invariants.

## Local essentials

- **SDK imports confined to `middleware/adapters/`** — WorkOS JWT verification,
  Mem0 long-term memory, Langfuse telemetry SDKs live behind the adapter
  boundary (rule F-R2 / A1). No SDK type escapes past `adapters/`.
- **This is the credentialed layer.** All credential-bearing calls the BFF can't
  make flow through here. The BFF (`agent-frontend`, Cloud Run) holds no cloud
  credentials.
- `trace_id` flows verbatim from the Python runtime adapter — never generated here.

See `frontend/AGENTS.md` and @../docs/style-guides/STYLE_GUIDE_FRONTEND.md.
