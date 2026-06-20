# Plan — frontend layer — bundle index

OKF bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md).

- [FRONTEND_PLAN.md — Web Chat UI for the ReAct Agent](FRONTEND_PLAN.md) — Ship a Claude-style web chat for the existing LangGraph ReAct agent — Next.js 15 (App Router) on Vercel with Tailwind + shadcn/ui, talking over Server-Sent Events to a new FastAPI
- [FRONTEND_PLAN_V1.md — Web Chat UI for the ReAct Agent (revision 2)](FRONTEND_PLAN_V1.md) — Ship a Claude-style web chat for the existing LangGraph ReAct agent — Next.js 15 (App Router) on Vercel with assistant-ui (shadcn/ui primitives) and Auth.js Cognito provider,
- [FRONTEND_PLAN_V2_FRONTIER.md — Competing alternative to FRONTEND_PLAN_V1.md](FRONTEND_PLAN_V2_FRONTIER.md) — Ship a Claude-Artifacts-class web chat for the existing LangGraph ReAct agent — Next.js 15 (App Router) on Vercel with CopilotKit v2 (AG-UI Protocol) for generative UI from day 1,
- [FRONTEND_PLAN_V3_DEV_TIER.md — Cheapest viable path to V2-Frontier](FRONTEND_PLAN_V3_DEV_TIER.md) — Ship the same Claude-Artifacts-class web chat as V2-Frontier — Next.js 15 (App Router) + CopilotKit v2 (AG-UI Protocol) for generative UI from day 1, talking over Server-Sent
- [Sprint 0 — Decisions Locked + Spike Validation (Runbook)](SPRINT_0_RUNBOOK.md) — This is the executable companion to Sprint 0 of the sprint board.
- [Frontend Sprint Board](SPRINT_BOARD.md) — Goal: Lock decisions, validate all four critical integration hypotheses before committing to implementation.
- [SPIKE_A — CopilotKit + AG-UI integration](spike_reports/SPIKE_A.md) — All three CopilotKit v2 hook patterns the V3 plan depends on (frontend tools / generative UI / live state) work end-to-end on a Next.js 16 + React 19 + Tailwind 4 stack against
- [SPIKE_B — Self-hosted LangGraph Developer in FastAPI](spike_reports/SPIKE_B.md) — The two hypotheses Spike B was meant to retire are already retired by the
- [SPIKE_C — Mem0 Cloud Hobby latency validation](spike_reports/SPIKE_C.md) — Both search() and add() were 2–3× over the H5 budget across all
- [SPIKE_C — Alternatives research](spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md) — Why:
- [SPIKE_D — Langfuse Cloud Hobby SDK + traced run](spike_reports/SPIKE_D.md) — The user opted not to provision a Langfuse Cloud account for v1.
