/**
 * UIRuntime -- vendor-neutral abstraction over the chat UI framework
 * (CopilotKit v2 in V3).
 *
 * Port rules: P1, P2, P3, P4, P5, P6.
 */

import type { ThreadState } from "../wire/agent_protocol";

/**
 * Opaque session handle returned by `UIRuntime.mount()`. The `handle` is
 * provider-internal; components must not introspect it.
 */
export type UIRuntimeSession = {
  readonly thread: ThreadState;
  readonly handle: unknown;
};

/**
 * Vendor-neutral abstraction over the chat UI framework.
 *
 * Owns the chat container, the `useFrontendTool` / `useComponent`
 * registration plumbing, and the `useThreadRuntime()` actions (stop,
 * regenerate, edit-and-resend).
 *
 * Behavioral contract:
 *   - `mount({ thread })` returns an opaque session handle; the React
 *     component layer treats it as `unknown` because mount details belong
 *     in the adapter.
 *   - `stop()`, `regenerate()`, `editAndResend(messageId, body)` correspond
 *     to F3 (stop / regenerate / edit-and-resend). All three call back into
 *     `AgentRuntimeClient.cancel()` and dispatch a fresh run as needed.
 *   - `stop()` is idempotent (A6).
 *
 * Error contract (P4):
 *   All four methods may surface the underlying `AgentRuntimeClient`
 *   error hierarchy when the adapter delegates to it: `AgentAuthError`,
 *   `AgentAuthorizationError`, `AgentRateLimitError`, `AgentServerError`,
 *   `AgentNetworkError`. Adapters MUST translate vendor SDK errors into
 *   one of those typed errors before they leave this surface (Rule A4 /
 *   F-R8) so consumers can switch on `instanceof` without depending on a
 *   vendor SDK.
 */
export interface UIRuntime {
  /**
   * Mount the chat surface for a thread.
   *
   * @throws AgentAuthError when the underlying runtime rejects the session token.
   * @throws AgentNetworkError when the runtime is unreachable.
   */
  mount(args: { thread: ThreadState }): Promise<UIRuntimeSession>;

  /**
   * Stop the in-flight run. Idempotent (A6) -- safe to call when no run
   * is active or when the run has already completed.
   *
   * @throws AgentNetworkError when the cancel call cannot reach the runtime.
   */
  stop(session: UIRuntimeSession): Promise<void>;

  /**
   * Regenerate the last assistant message. Implementations cancel the
   * current turn (if any) and dispatch a fresh run.
   *
   * @throws AgentAuthError when the underlying runtime rejects the session token.
   * @throws AgentRateLimitError when the runtime throttles the new run.
   * @throws AgentServerError when the runtime returns 5xx.
   * @throws AgentNetworkError when the runtime is unreachable.
   */
  regenerate(session: UIRuntimeSession): Promise<void>;

  /**
   * Edit a prior user message and resend; the assistant turn after it is
   * cancelled and re-issued.
   *
   * @throws AgentAuthError when the underlying runtime rejects the session token.
   * @throws AgentRateLimitError when the runtime throttles the new run.
   * @throws AgentServerError when the runtime returns 5xx.
   * @throws AgentNetworkError when the runtime is unreachable.
   */
  editAndResend(
    session: UIRuntimeSession,
    messageId: string,
    body: string,
  ): Promise<void>;
}
