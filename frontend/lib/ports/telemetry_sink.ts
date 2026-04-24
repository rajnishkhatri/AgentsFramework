/**
 * TelemetrySink -- vendor-neutral observability port.
 *
 * V3 implementation: LangfuseCloudHobbyAdapter.
 * V2 implementation: SelfHostedLangfuseAdapter.
 *
 * Port rules: P1, P2, P3, P5 (async by default), P6.
 */

/**
 * One telemetry event in flight to the sink.
 */
export type TelemetryEvent = {
  readonly trace_id: string;
  readonly name: string;
  readonly attributes: Readonly<Record<string, unknown>>;
  readonly level?: "info" | "warn" | "error";
};

/**
 * Vendor-neutral observability port.
 *
 * Behavioral contract:
 *   - `log(event)` MUST swallow failures silently (O1) -- telemetry must
 *     never block SSE delivery or render.
 *   - `trace_id` is non-optional on every event (O4 / F-R7).
 *   - Sink implementations may batch internally; from the caller's view
 *     `log` returns once the event is queued, not flushed.
 */
export interface TelemetrySink {
  /**
   * Queue a telemetry event. Resolves once queued. NEVER throws (O1) --
   * implementations log to a per-family logger and continue.
   */
  log(event: TelemetryEvent): Promise<void>;
}
