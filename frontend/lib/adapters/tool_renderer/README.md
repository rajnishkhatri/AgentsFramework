# `adapters/tool_renderer/` — ToolRendererRegistry family

Per Rule **A10**, every adapter family carries a one-page README declaring
the port it satisfies, current implementations, and the substrate-swap
trigger.

## Port

[`ToolRendererRegistry`](../../ports/tool_renderer_registry.ts) —
vendor-neutral, **synchronous** registry mapping tool names to renderer
factories. The sync return is a deliberate **P5 exception** (documented
both in the port JSDoc and in the conformance test) so the React tree
can resolve renderers at render time.

## Current implementations

| Profile | Adapter | SDK pin |
|---------|---------|---------|
| **V3-Dev-Tier** (default) | [`CopilotKitRegistryAdapter`](./copilotkit_registry_adapter.ts) | none in this file — the registry is SDK-free; `useFrontendTool(...)` calls happen inside [`adapters/ui_runtime/`](../ui_runtime/) |

## Wildcard fallback contract

`resolve(toolName)` returns the wildcard `*` renderer when no specific
renderer is registered, and a no-op when neither is present. `resolve()`
**never throws** so the chat surface always renders something.

## Logger

`frontend:adapter:tool_renderer` (Rule **A7 / O3**). Emitted lines:

| Event | Meta | When |
|-------|------|------|
| `tool renderer overwritten` | `tool_name` | a second `register(name, ...)` replaces a previous registration |

Renderer resolutions are **not** logged (one log line per render would
be unacceptable on the hot path).

## Substrate swap trigger

| When | Swap to | How |
|------|---------|-----|
| Move off CopilotKit (e.g. assistant-ui per V1 fallback) | new registry adapter that wraps the alternative chat framework's renderer hooks | new adapter file + composition selector update; the port stays the same so `frontend/components/tools/*` does not change (**F3**) |

## Tests

- [`copilotkit_registry_adapter.test.ts`](./copilotkit_registry_adapter.test.ts) —
  wildcard fallback, specific-wins-wildcard precedence, idempotent
  overwrite semantics, never-throws guarantee on empty registry.
