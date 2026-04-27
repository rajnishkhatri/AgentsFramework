# `adapters/runtime/` — AgentRuntimeClient family

Per Rule **A10**, every adapter family carries a one-page README declaring
the port it satisfies, current implementations, and the substrate-swap
trigger.

## Port

[`AgentRuntimeClient`](../../ports/agent_runtime_client.ts) —
vendor-neutral runtime for the LangGraph backend. Yields wire shapes
(`RunStateView`, `UIRuntimeEvent`); never exposes vendor types past the
boundary (Rule **A4 / F-R8**).

## Current implementations

| Profile | Adapter | SDK pin |
|---------|---------|---------|
| **V3-Dev-Tier** (default) | [`SelfHostedLangGraphDevClient`](./self_hosted_langgraph_dev_client.ts) | none — speaks AG-UI Agent Protocol over plain HTTP/SSE so the LangGraph SDK never lands in browser bundles |
| V2-Frontier (graduation) | `LangGraphPlatformSaaSClient` (not yet implemented) | `@langchain/langgraph-sdk ^0.0.x` (server-side only) |

## Layering note (Rule A3)

This adapter family **does not** import from `transport/` or
`translators/`. The composition root assembles the SSE transport
(`connectSSE`) and the AG-UI → UIRuntime translator (`agUiToUiRuntime`)
into a single `openUIRuntimeStream(runId)` factory and injects it via
constructor options. The architecture test in
[`tests/architecture/test_frontend_layering.test.ts`](../../../tests/architecture/test_frontend_layering.test.ts)
catches regressions automatically (planted-violation guard).

## Logger

`frontend:adapter:runtime` (Rule **A7 / O3**). Emitted lines:

| Event | Meta | When |
|-------|------|------|
| `createRun fetch rejected` | `error_type=network_error` | upstream `fetch()` rejected before status |
| `createRun auth rejected` | `status_code=401` | upstream returned 401 |
| `createRun authorization rejected` | `status_code=403` | upstream returned 403 |
| `createRun rate-limited` | `status_code=429` | upstream returned 429 |
| `createRun upstream 5xx` | `status_code=5xx` | upstream returned ≥ 500 |

`cancel()` is intentionally silent on failure — it is idempotent (Rule
**A6**) and any real failure is observable via the SSE error event.

## Error translation table (Rule A5)

| HTTP / network condition | Typed error |
|---------------------------|-------------|
| `401` | [`AgentAuthError`](./errors.ts) |
| `403` | [`AgentAuthorizationError`](./errors.ts) |
| `429` | [`AgentRateLimitError`](./errors.ts) |
| `5xx` | [`AgentServerError`](./errors.ts) |
| `fetch` reject / abort | [`AgentNetworkError`](./errors.ts) |

## `trace_id` policy

`trace_id` is forwarded verbatim from the backend SSE stream; the adapter
**never** generates one (FE-AP-7 **AUTO-REJECT**). For transport-level
failures (parse error, heartbeat timeout) where no real `trace_id` is
available, the composition's `openUIRuntimeStream` synthesizes a
documented sentinel `"no-trace"` rather than minting a UUID.

## Substrate swap trigger

| When | Swap to | How |
|------|---------|-----|
| Self-hosted runtime > 100K nodes/mo | `LangGraphPlatformSaaSClient` (V2 SaaS) | new adapter file + composition selector update; no other files change (**F3**) |

## Tests

- [`self_hosted_langgraph_dev_client.test.ts`](./self_hosted_langgraph_dev_client.test.ts) —
  failure-paths-first (401/403/429/5xx/network) per Rule **FD6.ADAPTER**,
  then port conformance and the new injection-seam tests for
  `openUIRuntimeStream`.
