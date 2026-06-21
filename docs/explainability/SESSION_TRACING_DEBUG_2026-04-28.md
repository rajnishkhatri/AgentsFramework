---
type: session-recap
title: 'Session recap — End-to-end tracing and debugging (2026-04-28)'
description: 'This note captures what we ran, what broke, how we fixed it, and which files changed.'
tags: [explainability]
---

# Session recap — End-to-end tracing and debugging (2026-04-28)

This note captures what we ran, what broke, how we fixed it, and which files changed. It complements [END_TO_END_TRACING_GUIDE.md](END_TO_END_TRACING_GUIDE.md).

## Goal

Run the chat stack against real middleware: `frontend` (Next.js BFF) → `middleware` (`python -m middleware`) → LangGraph runtime → governance artifacts, then validate correlation and UI behavior.

## Environment prerequisites

Add to `.env` (values are examples; secrets must stay private):

- `AGENT_FACTS_SECRET` — HMAC signing key for `AgentFacts` JSON under `cache/agent_facts/`.
- `WORKOS_COOKIE_PASSWORD` — at least 32 characters; **not** from the WorkOS dashboard (local cookie encryption for AuthKit).
- `NEXT_PUBLIC_WORKOS_REDIRECT_URI` — must match the callback URL allowlisted in WorkOS (e.g. `http://localhost:3003/api/auth/callback` if the dev server uses port 3003).

WorkOS dashboard: register the **exact** redirect URI (scheme + host + port + path).

## Processes and ports


| Service       | Command                              | Port |
| ------------- | ------------------------------------ | ---- |
| Middleware    | `PORT_STRICT=1 python -m middleware` | 8000 |
| Chat frontend | `pnpm dev -p 3003` in `frontend/`    | 3003 |


Use `PORT_STRICT=1` so middleware does not silently bind to 8001 while the BFF still targets `http://localhost:8000`.

## Trace correlation patch

In `[agent_ui_adapter/adapters/runtime/langgraph_runtime.py](../../agent_ui_adapter/adapters/runtime/langgraph_runtime.py)`, `LangGraphRuntime.run()` now:

- Seeds graph input with `workflow_id`, `task_id`, and `registered_agent_id` so black-box and phase logs key off the same id as SSE `trace_id`.
- Passes `trace_id`, `user_id`, and `registered_agent_id` in LangGraph `configurable`.

## Issue 1 — Redirect URI landed on wrong port (Safari could not connect)

**Symptom:** After WorkOS login, browser opened `http://localhost:3000/api/auth/callback` while Next ran on **3003**.

**Cause:** A shell session had exported `NEXT_PUBLIC_WORKOS_REDIRECT_URI` from the repo root `.env` (port 3000) via `set -a && source .env`. Next.js gives **precedence to the process environment** over `frontend/.env.local`, so the built sign-in URL used port 3000.

**Fix:** Start `pnpm dev` in a shell where `NEXT_PUBLIC_WORKOS_REDIRECT_URI` is **unset**, or align root `.env` and `.env.local` to the same port. Prefer running the frontend without a conflicting exported variable.

## Issue 2 — Stale `AgentFacts` signatures (`verified: false`, no LLM)

**Symptom:** Middleware or CLI ran guardrail then stopped with ~0 steps / no main LLM; black-box showed `guardrail_checked` with `verified: false` for `agent_facts`.

**Cause:** `cache/agent_facts/<agent>.json` was signed under an older `AGENT_FACTS_SECRET` than the one in `.env`.

**Fix:** Remove stale `cli-agent.json` / `dev-agent.json` (and matching `*_audit.jsonl`) so bootstrap re-registers agents with the current secret, then restart middleware.

## Issue 3 — UI showed only `accept`, not the assistant answer

**Symptom:** Chat displayed the word `accept` instead of the model reply.

**Causes (both confirmed with logs):**

1. **SSE leak from internal LLM:** LangGraph `astream_events` emits `on_chat_model_`* for the input guardrail node (`guard_input`) as well as `call_llm`. Both streams were translated to AG-UI text events; the guardrail verdict (`accept`) appeared as the visible assistant message.
2. **Empty `task_input`:** Middleware passed `input=user_input` when messages were present but never merged `task_input`, so `AgentState.task_input` stayed empty for observability.

**Fixes:**

1. In `_translate_event`, **ignore** `on_chat_model_`* when `metadata.langgraph_node` is present and **not** `call_llm`. If `langgraph_node` is **missing** (unit-test fakes), events pass through unchanged.
2. Middleware always passes `input={**(user_input or {}), "task_input": task_input}` into `runtime.run()`.

Direct verification: `curl` to `POST /run/stream` showed deltas like `FINAL ANSWER: Four` with no leading `accept`.

## Tests added

- `[tests/agent_ui_adapter/adapters/runtime/test_langgraph_runtime.py](../../tests/agent_ui_adapter/adapters/runtime/test_langgraph_runtime.py)`: `test_filters_guard_input_when_langgraph_node_tagged`.

## Files touched in this session (high level)

- `[agent_ui_adapter/adapters/runtime/langgraph_runtime.py](../../agent_ui_adapter/adapters/runtime/langgraph_runtime.py)` — correlation seeding + guardrail SSE filter.
- `[middleware/__main__.py](../../middleware/__main__.py)` — always merge `task_input` into runtime input.
- `[frontend/app/api/auth/[...workos]/route.ts](../../frontend/app/api/auth/[...workos]/route.ts)` — temporary debug instrumentation removed after redirect diagnosis.
- `[tests/agent_ui_adapter/adapters/runtime/test_langgraph_runtime.py](../../tests/agent_ui_adapter/adapters/runtime/test_langgraph_runtime.py)` — regression test for filter behavior.

## Operational reminders

- Avoid `set -a && source .env` in the **same shell** that starts Next.js unless `NEXT_PUBLIC_`* values match the dev server port.
- After rotating `AGENT_FACTS_SECRET`, expect to delete cached `cache/agent_facts/*.json` for dev agents or implement automatic re-registration (planned follow-up).
- Optional: remove `WORKOS_CLAIM_TOKEN` from env if AuthKit logs `Failed to exchange WORKOS_CLAIM_TOKEN (401)`.

## Next steps (from earlier plan, not all implemented here)

- Wire optional `TrustTraceRecord` emission in middleware (`trace_emit`).
- Start `explainability_app` + `frontend-explainability` to browse traces/compliance UI.
- Long-term: `AgentFactsRegistry.reregister()` when signature verification fails on existing files (see separate plan).