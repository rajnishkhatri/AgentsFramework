# `adapters/ui_runtime/` — UIRuntime family

Per Rule **A10**, every adapter family carries a one-page README declaring
the port it satisfies, current implementations, and the substrate-swap
trigger.

## Port

[`UIRuntime`](../../ports/ui_runtime.ts) — vendor-neutral abstraction
over the chat UI framework. Owns `mount` / `stop` / `regenerate` /
`editAndResend` (the F3 toolbar actions) and the
`useFrontendTool` / `useComponent` plumbing.

## Current implementations

| Profile | Adapter | SDK pin |
|---------|---------|---------|
| **V3-Dev-Tier** (default) | [`CopilotKitUIRuntime`](./copilotkit_ui_runtime.ts) | `@copilotkit/react-core ^v2`, `@copilotkit/react-ui ^v2` (provider mounted from the composition root) |

The headless `mount`/`stop`/`regenerate`/`editAndResend` plumbing in
this file is unit-testable in node without React. The React provider
(`<CopilotKit runtimeUrl=...>`) is mounted by the app shell using a
sibling helper so the SDK package is referenced at exactly one site.

## Logger

`frontend:adapter:ui_runtime` (Rule **A7 / O3**). Emitted lines:

| Event | Meta | When |
|-------|------|------|
| `stop` | `run_id`, `thread_id` | toolbar Stop pressed (only when an active run exists) |
| `regenerate` | `thread_id` | toolbar Regenerate pressed |
| `editAndResend` | `thread_id`, `message_id` | toolbar Edit-and-Resend pressed |

`message_id` is opaque (UUID) — not PII. Body text and message content
are **never** logged (Rule **O2**).

## Error translation table (Rule A5)

All four methods may surface the underlying `AgentRuntimeClient` error
hierarchy when the adapter delegates to it:

| Method | Possible errors |
|--------|----------------|
| `mount()` | `AgentAuthError`, `AgentNetworkError` (future provider bootstrap) |
| `stop()` | `AgentAuthError` (cancel rejected); network failures swallowed by the runtime adapter (A6) |
| `regenerate()` | full `AgentRuntimeClient` hierarchy (Auth / Authorization / RateLimit / Server / Network) |
| `editAndResend()` | same as `regenerate()` |

Adapters MUST translate vendor SDK errors into one of those typed
errors before they leave this surface (Rule **A4 / F-R8**) so consumers
can switch on `instanceof` without depending on a vendor SDK.

## Substrate swap trigger

| When | Swap to | How |
|------|---------|-----|
| Move off CopilotKit (e.g. assistant-ui per V1 fallback) | new `UIRuntime` impl wrapping the alternative chat framework | new adapter file + composition selector update; no `ports/` changes (**F3**) |

## Tests

- [`copilotkit_ui_runtime.test.ts`](./copilotkit_ui_runtime.test.ts) —
  port conformance, `stop()` idempotency (A6), `mount` returns a typed
  session handle.
