/**
 * Port interface for the explainability backend (rule P1 — one interface per port).
 *
 * Implementations live in lib/adapters/. The composition root in lib/composition.ts
 * is the only place that selects a concrete implementation (rule C1).
 *
 * @throws {ExplainabilityClientError} on any transport or validation failure.
 */
import type {
  AgentAuditEntry,
  AgentCard,
  ComplianceBundle,
  ComplianceSummary,
  DashboardMetrics,
  DecisionRecord,
  GuardrailSummary,
  IntegrityReport,
  LogRow,
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
   * @param since  Inclusive lower bound on `started_at`.  When omitted, no
   *               lower bound is applied.
   * @param until  Exclusive upper bound on `started_at`.  When omitted, no
   *               upper bound is applied.
   * @throws {ExplainabilityClientError} status=null on network failure.
   * @throws {ExplainabilityClientError} status=500 on server error.
   * @throws {ExplainabilityClientError} status=null on Zod parse failure.
   */
  listWorkflows(since?: Date, until?: Date): Promise<WorkflowSummary[]>;

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
   * Contract drift note: returns `[]` for an unknown workflow id rather
   * than throwing 404, unlike `getWorkflowEvents` /
   * `getWorkflowIntegrity` / `getWorkflowCompliance`.  Phase logging is
   * best-effort and a missing decisions file is a normal state, so the
   * Decision Audit panel renders an empty list instead of erroring.  Use
   * `getWorkflowEvents` or `getWorkflowIntegrity` to assert workflow
   * existence explicitly when 404 semantics are required.
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

  /**
   * Returns the guardrail-monitor roll-up over the events in `[since, until)`.
   *
   * Returns the all-zero structure when no `guardrail_checked` events fall in
   * the range — never 404.  The trend field is the single-number delta vs the
   * immediately preceding window of equal length, or 0 when no prior window.
   *
   * @param since  Inclusive lower bound on the event timestamp.
   * @param until  Exclusive upper bound on the event timestamp.
   * @throws {ExplainabilityClientError} status=null on network or parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getGuardrailSummary(since?: Date, until?: Date): Promise<GuardrailSummary>;

  /**
   * Returns every registered agent as a read-only `AgentCard`.
   *
   * Returns `[]` when the backend has no registry wired in -- never 404.
   *
   * @throws {ExplainabilityClientError} status=null on network/parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  listAgents(): Promise<AgentCard[]>;

  /**
   * Returns the read-only identity card for `agentId`.
   *
   * @param agentId  The agent id.
   * @throws {ExplainabilityClientError} status=404 when the agent is unknown.
   * @throws {ExplainabilityClientError} status=null on network/parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getAgentCard(agentId: string): Promise<AgentCard>;

  /**
   * Returns the chronological audit trail for `agentId`.
   *
   * @param agentId  The agent id.
   * @throws {ExplainabilityClientError} status=404 when the agent is unknown.
   * @throws {ExplainabilityClientError} status=null on network/parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getAgentAudit(agentId: string): Promise<AgentAuditEntry[]>;

  /**
   * Returns the chain-integrity report for `wfId` (S3.1.1).
   *
   * `chain_valid=true` is the happy path; on a tampered chain the report
   * additionally exposes `broken_at_event_id` plus the expected and actual
   * hashes so the UI can highlight the break location explicitly.
   *
   * @param wfId  The workflow id.
   * @throws {ExplainabilityClientError} status=404 when the workflow id is unknown.
   * @throws {ExplainabilityClientError} status=null on network/parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getWorkflowIntegrity(wfId: string): Promise<IntegrityReport>;

  /**
   * Returns the four-pillar compliance bundle for `wfId` (S3.1.2).
   *
   * The bundle joins recording (events), identity (per-agent cards + audit
   * trails), and reasoning (phase decisions). The `correlation_health` block
   * surfaces missing correlation keys explicitly -- the UI should NEVER
   * silently omit a missing key.
   *
   * @param wfId  The workflow id.
   * @throws {ExplainabilityClientError} status=404 when the workflow id is unknown.
   * @throws {ExplainabilityClientError} status=null on network/parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getWorkflowCompliance(wfId: string): Promise<ComplianceBundle>;

  /**
   * Returns the batched compliance summary for the audit window
   * `[since, until)` (Sprint 3 review F3 fix).
   *
   * Replaces the previous per-row N+1 fan-out where the page called
   * `getWorkflowIntegrity` once per workflow.  One round-trip returns
   * every workflow + integrity row, plus the bounds the server actually
   * applied so the UI can render the audit window verbatim.
   *
   * Returns the empty-rows structure when no workflows are in range --
   * never 404.
   *
   * @param since  Inclusive lower bound on `started_at`.
   * @param until  Exclusive upper bound on `started_at`.
   * @throws {ExplainabilityClientError} status=null on network/parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  getComplianceSummary(
    since?: Date,
    until?: Date,
  ): Promise<ComplianceSummary>;

  /**
   * Returns recent rows from per-concern log files (S4.3.1).
   *
   * Returns the empty array when no rows match the filters -- never 404.
   *
   * @param params.concerns  Logger handler names from `logging.json`. When
   *                         omitted, every known concern is searched.
   * @param params.level     Optional level filter (`INFO`, `WARN`, `ERROR`).
   * @param params.search    Optional case-insensitive substring on `message`.
   * @param params.since     Inclusive lower bound on the row timestamp.
   * @param params.limit     Maximum number of rows returned (default 500).
   * @throws {ExplainabilityClientError} status=null on network/parse failure.
   * @throws {ExplainabilityClientError} status=5xx on server error.
   */
  queryLogs(params?: {
    concerns?: readonly string[] | undefined;
    level?: string | null | undefined;
    search?: string | null | undefined;
    since?: Date | undefined;
    limit?: number | undefined;
  }): Promise<LogRow[]>;
}
