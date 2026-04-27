/**
 * Port interface for the explainability backend (rule P1 — one interface per port).
 *
 * Implementations live in lib/adapters/. The composition root in lib/composition.ts
 * is the only place that selects a concrete implementation (rule C1).
 *
 * @throws {ExplainabilityClientError} on any transport or validation failure.
 */
import type { WorkflowSummary } from "@/lib/wire/responses";

/** Typed errors raised by any ExplainabilityClient implementation (rule P4). */
export class ExplainabilityClientError extends Error {
  constructor(
    message: string,
    /** HTTP status code when available, otherwise null. */
    public readonly status: number | null,
  ) {
    super(message);
    this.name = "ExplainabilityClientError";
  }
}

/**
 * Behavioral contract for the explainability read API (rule P3).
 *
 * Every method must:
 *  - Return only wire-layer types from lib/wire/ (rule A4 enforced here via types).
 *  - Throw ExplainabilityClientError on transport failures, HTTP errors, or Zod parse errors.
 *  - Never perform caching, retries, or auth — those belong in the adapter or middleware.
 */
export interface ExplainabilityClient {
  /**
   * Returns all recorded workflows, newest first.
   *
   * @param since  When provided, excludes workflows older than this date.
   * @throws {ExplainabilityClientError} status=null on network failure.
   * @throws {ExplainabilityClientError} status=500 on server error.
   * @throws {ExplainabilityClientError} status=null on Zod parse failure.
   */
  listWorkflows(since?: Date): Promise<WorkflowSummary[]>;
}
