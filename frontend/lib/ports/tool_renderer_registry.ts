/**
 * ToolRendererRegistry -- vendor-neutral registry for tool-call UI cards.
 *
 * V3 implementation wraps CopilotKit `useFrontendTool` (Static AG-UI) and
 * `useComponent` (Open AG-UI). The registry is consulted once per tool name
 * to obtain the React renderer that should display the tool's input/output
 * card.
 *
 * Port rules: P1, P2, P3, **P5 sync exception** (justified below), P6.
 */

import type { ToolCallRendererRequest } from "../wire/ui_runtime_events";

/**
 * Function signature for a tool renderer. To keep the port adapter-neutral,
 * the return type is `unknown` -- the V3 CopilotKit adapter narrows it to
 * `React.ReactNode` at the boundary.
 */
export type ToolRenderer = (req: ToolCallRendererRequest) => unknown;

/**
 * Vendor-neutral registry for tool-call UI cards.
 *
 * Behavioral contract:
 *   - **P5 exception**: lookups are SYNCHRONOUS by design. Renderer
 *     resolution happens at React render time and an async lookup would
 *     block the chat surface. Registrations happen once at composition time
 *     and are immutable thereafter.
 *   - Unknown tool names resolve to the registered fallback renderer
 *     (typically a generic JSON viewer); `resolve` never throws.
 *   - `register("*", fn)` sets the wildcard fallback.
 */
export interface ToolRendererRegistry {
  /**
   * Register a renderer for a specific tool name. Idempotent: re-registering
   * the same name overwrites the previous renderer.
   */
  register(toolName: string, renderer: ToolRenderer): void;

  /**
   * Resolve a renderer. Synchronous render-time lookup (P5 exception).
   * Falls back to the registered `*` (wildcard) renderer when the name is
   * unknown.
   */
  resolve(toolName: string): ToolRenderer;
}
