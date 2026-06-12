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

import type {
  RunCreateRequest,
  TaskUnderstandingEditRequest,
} from "../wire/agent_protocol";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";

/**
 * Options for `streamRun`. A type alias, not an interface (P1: one
 * interface per port file). Aborting the signal closes the stream
 * client-side (the Phase 4 soft-gate "pause": the backend checkpoint
 * survives, so the run can resume via a new `streamRun` whose `input`
 * carries `_resume: true`).
 */
export type StreamRunOptions = {
  readonly signal?: AbortSignal;
};

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
  streamRun(
    req: RunCreateRequest,
    opts?: StreamRunOptions,
  ): AsyncIterable<UIRuntimeEvent>;

  /**
   * Cancel an in-flight run. Idempotent (A6). Resolves successfully even
   * if the run is already completed or never existed.
   *
   * @throws AgentNetworkError on transport failure
   */
  cancel(runId: string): Promise<void>;

  /**
   * Apply a user edit to the run's TaskUnderstanding artifact (Phase 4
   * soft-gate card). The `trace_id` in the request is echoed verbatim from
   * the `run_started` event (F-R7: never generated browser-side). The
   * caller pauses the stream first and resumes after this resolves.
   *
   * @throws AgentAuthError on 401
   * @throws AgentRuntimeError on any other non-2xx (the message carries
   *   the upstream detail, e.g. a 409 "run already completed")
   * @throws AgentNetworkError on transport failure
   */
  updateUnderstanding(
    threadId: string,
    req: TaskUnderstandingEditRequest,
  ): Promise<void>;
}
