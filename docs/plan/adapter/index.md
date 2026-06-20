# Plan — adapter layer — bundle index

OKF bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md).

- [AGENT_UI_ADAPTER_PLAN.md — Implementation Spec for the Outermost Ring](AGENT_UI_ADAPTER_PLAN.md) — Three concentric contracts make either side of the stack swappable as a config change: AG-UI is the wire ring, one new Python Protocol (AgentRuntime) is the application ring,
- [Agent-UI Adapter Layer Plan v1.1](AGENT_UI_ADAPTER_PLAN_V1.1.md) — Replace the v1 §5 "what is NOT a port" table with a three-column version that records ground truth as of this evaluation.
- [Agent UI Adapter — Enhancements & Next Steps](NEXT_STEPS.md) — Priority: High — blocks production deployment.
- [AGENT_UI_ADAPTER_SPRINTS.md — Sprint Backlog and User Stories](sprints/AGENT_UI_ADAPTER_SPRINTS.md) — This document is the operational backlog.
- [IMPLEMENTATION_REVIEW.md — End-to-End Audit + Pyramid 8-Check](sprints/IMPLEMENTATION_REVIEW.md) — S1 exit: tests/architecture/test_service_isolation.py confirms no horizontal-to-horizontal imports.
