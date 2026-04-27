/**
 * Port interface for the explainability backend (rule P1 — one interface per port).
 *
 * Implementations live in lib/adapters/. The composition root in lib/composition.ts
 * is the only place that selects a concrete implementation (rule C1).
 *
 * @throws {ExplainabilityClientError} on any transport or validation failure.
 */
import type {
  DashboardMetrics,
  DecisionRecord,
  WorkflowEvents,
  WorkflowSummary,
} from "@/lib/wire/responses";

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

  /**
   * Returns the full event timeline for a workflow with hash-chain status.
   *
   * @param wfId  The workflow id.
   * @throws {ExplainabilityClientError} status=404 when the workflow id is unknown.
   * @throws {ExplainabilityClientError} status=null on network or parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getWorkflowEvents(wfId: string): Promise<WorkflowEvents>;

  /**
   * Returns the chronological decision log for a workflow.
   *
   * Returns an empty array when the workflow recorded no decisions — never 404.
   *
   * @param wfId  The workflow id.
   * @throws {ExplainabilityClientError} status=null on network or parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getWorkflowDecisions(wfId: string): Promise<DecisionRecord[]>;

  /**
   * Returns aggregated dashboard KPIs over the workflows in `[since, until)`.
   *
   * Returns the all-zero structure when no workflows are in range — never 404.
   *
   * @param since  Inclusive lower bound on `started_at`.
   * @param until  Exclusive upper bound on `started_at`.
   * @throws {ExplainabilityClientError} status=null on network or parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getDashboardMetrics(since?: Date, until?: Date): Promise<DashboardMetrics>;
}
