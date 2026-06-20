# Plan — services layer — bundle index

OKF bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md).

- [AUTHORIZATION_SERVICE_PLAN.md — `services/authorization_service.py` Implementation Plan](AUTHORIZATION_SERVICE_PLAN.md) — Given an AgentFacts (the agent's identity card), an action (the operation requested), and a context (free-form details: tool name, args, target resource), returns a PolicyDecision
- [LONG_TERM_MEMORY_PLAN.md — `services/long_term_memory.py` Implementation Plan](LONG_TERM_MEMORY_PLAN.md) — A horizontal store/recall service for per-user long-term memory: facts about the user that should persist across sessions and runs.
- [TRACE_SERVICE_PLAN.md — `services/trace_service.py` Implementation Plan](TRACE_SERVICE_PLAN.md) — A horizontal emit + route service for TrustTraceRecord events.
