/**
 * AgentRuntimeClient -- vendor-neutral interface for the LangGraph runtime.
 *
 * V3 implementation: SelfHostedLangGraphDevClient.
 * V2 implementation: LangGraphPlatformSaaSClient.
 *
 * Port rules: P1 one-interface-per-file; P2 vendor-neutral name (no
 * "LangGraph" in the type); P4 typed errors via @throws; P6 imports only
 * from wire/ and trust-view/.
 */

import type {
  RunCreateRequest,
  RunStateView,
} from "../wire/agent_protocol";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";

/**
 * Vendor-neutral runtime client for the LangGraph backend.
 *
 * Behavioral contract:
 *   - `createRun(req)` returns a `RunStateView` with `status: "running"` and
 *     never blocks on first event delivery (the SSE stream is the source of
 *     truth for run progress).
 *   - `streamRun(runId)` yields `UIRuntimeEvent` values until either a
 *     `run_completed` or `run_error` event is observed (Runtime Contract §1:
 *     terminal event always emitted).
 *   - `cancel(runId)` is idempotent (A6) -- calling it twice for the same
 *     `run_id` is not an error and never throws if the run is already
 *     completed.
 *   - `trace_id` is always forwarded verbatim from the backend; this client
 *     MUST NEVER generate a `trace_id` browser-side (FE-AP-7 AUTO-REJECT).
 *   - The SSE client (`transport/sse_client.ts`) handles `Last-Event-ID`
 *     resumption transparently behind `streamRun`.
 */
export interface AgentRuntimeClient {
  /**
   * Open a new run. Returns the initial `RunStateView` once the backend
   * accepts the request.
   *
   * @throws AgentAuthError on HTTP 401
   * @throws AgentAuthorizationError on HTTP 403
   * @throws AgentRateLimitError on HTTP 429
   * @throws AgentServerError on HTTP 5xx
   * @throws AgentNetworkError on transport failure / timeout
   */
  createRun(req: RunCreateRequest): Promise<RunStateView>;

  /**
   * Stream UI-runtime events for a run. Always terminates with either a
   * `run_completed` or `run_error` UIRuntimeEvent (Runtime Contract §1).
   * The async iterable is responsible for `Last-Event-ID` resumption when
   * the underlying transport drops (X3).
   */
  streamRun(runId: string): AsyncIterable<UIRuntimeEvent>;

  /**
   * Cancel an in-flight run. Idempotent (A6). Resolves successfully even
   * if the run is already completed or never existed.
   *
   * @throws AgentNetworkError on transport failure
   */
  cancel(runId: string): Promise<void>;
}
