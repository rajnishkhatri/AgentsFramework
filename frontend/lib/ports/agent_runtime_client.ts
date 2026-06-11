/**
 * AgentRuntimeClient -- vendor-neutral interface for the LangGraph runtime.
 *
 * V3 implementation: SelfHostedLangGraphDevClient.
 * V2 implementation: LangGraphPlatformSaaSClient.
 *
 * Port rules: P1 one-interface-per-file; P2 vendor-neutral name (no
 * "LangGraph" in the type); P4 typed errors via @throws; P6 imports only
 * from wire/ and trust-view/.
 *
 * Protocol note (eval-UI F1, 2026-06-11): the self-hosted middleware
 * exposes a single `POST /run/stream` whose response body IS the SSE
 * stream -- there is no create-then-stream-by-id pair. The port therefore
 * models the consumer's need directly: `streamRun(req)` starts the run
 * and yields its events. A future create/stream substrate (e.g. LangGraph
 * Platform SaaS) implements the same method by composing both calls
 * behind it.
 */

import type { RunCreateRequest } from "../wire/agent_protocol";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";

/**
 * Vendor-neutral runtime client for the LangGraph backend.
 *
 * Behavioral contract:
 *   - `streamRun(req)` opens the run and yields `UIRuntimeEvent` values.
 *     The stream ALWAYS terminates with a `run_completed` or `run_error`
 *     event (Runtime Contract §1); transport failures surface as
 *     `run_error` with the closed `error_type` enum, never as raw throws
 *     mid-iteration.
 *   - `cancel(runId)` is idempotent (A6) -- calling it twice for the same
 *     `run_id` is not an error and never throws if the run is already
 *     completed.
 *   - `trace_id` is always forwarded verbatim from the backend; this client
 *     MUST NEVER generate a `trace_id` browser-side (FE-AP-7 AUTO-REJECT).
 */
export interface AgentRuntimeClient {
  /**
   * Start a run and stream its UI-runtime events. Always terminates with
   * either a `run_completed` or `run_error` UIRuntimeEvent (Runtime
   * Contract §1).
   */
  streamRun(req: RunCreateRequest): AsyncIterable<UIRuntimeEvent>;

  /**
   * Cancel an in-flight run. Idempotent (A6). Resolves successfully even
   * if the run is already completed or never existed.
   *
   * @throws AgentNetworkError on transport failure
   */
  cancel(runId: string): Promise<void>;
}
