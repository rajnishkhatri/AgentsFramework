/**
 * HTTP adapter for the explainability backend (rule A1, A4, A5, A9).
 *
 * @sdk fetch (built-in)  — the only file allowed to call fetch() or EventSource.
 *      zod ^3.0.0        — schema parsing via wire/ shapes only.
 *
 * Error-translation table (rule A5):
 *  - Network failure (fetch rejects)  → ExplainabilityClientError(message, null)
 *  - HTTP 4xx / 5xx                   → ExplainabilityClientError(detail, status)
 *  - Zod parse failure                → ExplainabilityClientError(zodMessage, null)
 *
 * Returns only types from lib/wire/ — never raw Response or JSON (rule A4).
 */
import { z } from "zod";
import {
  AgentAuditEntryListSchema,
  AgentCardListSchema,
  AgentCardSchema,
  ComplianceBundleSchema,
  ComplianceSummarySchema,
  DashboardMetricsSchema,
  DecisionRecordListSchema,
  GuardrailSummarySchema,
  IntegrityReportSchema,
  LogRowListSchema,
  WorkflowEventsSchema,
  WorkflowSummaryListSchema,
  type AgentAuditEntry,
  type AgentCard,
  type ComplianceBundle,
  type ComplianceSummary,
  type DashboardMetrics,
  type DecisionRecord,
  type GuardrailSummary,
  type IntegrityReport,
  type LogRow,
  type WorkflowEvents,
  type WorkflowSummary,
} from "@/lib/wire/responses";
import {
  type ExplainabilityClient,
  ExplainabilityClientError,
} from "@/lib/ports/explainability_client";

export class HttpExplainabilityClient implements ExplainabilityClient {
  constructor(private readonly baseUrl: string) {}

  /**
   * GET /api/v1/workflows[?since=<iso>&until=<iso>]
   *
   * @throws {ExplainabilityClientError} on network, HTTP, or parse error.
   */
  async listWorkflows(
    since?: Date,
    until?: Date,
  ): Promise<WorkflowSummary[]> {
    const url = new URL(`${this.baseUrl}/api/v1/workflows`);
    if (since !== undefined) {
      url.searchParams.set("since", since.toISOString());
    }
    if (until !== undefined) {
      url.searchParams.set("until", until.toISOString());
    }
    return this.requestJson(url, WorkflowSummaryListSchema);
  }

  /**
   * GET /api/v1/workflows/{wfId}/events
   *
   * @throws {ExplainabilityClientError} status=404 on unknown workflow id.
   * @throws {ExplainabilityClientError} status=null on network/parse error.
   */
  async getWorkflowEvents(wfId: string): Promise<WorkflowEvents> {
    const url = new URL(
      `${this.baseUrl}/api/v1/workflows/${encodeURIComponent(wfId)}/events`,
    );
    return this.requestJson(url, WorkflowEventsSchema);
  }

  /**
   * GET /api/v1/workflows/{wfId}/decisions
   *
   * @throws {ExplainabilityClientError} status=null on network/parse error.
   */
  async getWorkflowDecisions(wfId: string): Promise<DecisionRecord[]> {
    const url = new URL(
      `${this.baseUrl}/api/v1/workflows/${encodeURIComponent(wfId)}/decisions`,
    );
    return this.requestJson(url, DecisionRecordListSchema);
  }

  /**
   * GET /api/v1/dashboard/metrics[?since=<iso>&until=<iso>]
   *
   * @throws {ExplainabilityClientError} status=null on network/parse error.
   */
  async getDashboardMetrics(
    since?: Date,
    until?: Date,
  ): Promise<DashboardMetrics> {
    const url = new URL(`${this.baseUrl}/api/v1/dashboard/metrics`);
    if (since !== undefined) url.searchParams.set("since", since.toISOString());
    if (until !== undefined) url.searchParams.set("until", until.toISOString());
    return this.requestJson(url, DashboardMetricsSchema);
  }

  /**
   * GET /api/v1/guardrails/summary[?since=<iso>&until=<iso>]
   *
   * @throws {ExplainabilityClientError} status=null on network/parse error.
   */
  async getGuardrailSummary(
    since?: Date,
    until?: Date,
  ): Promise<GuardrailSummary> {
    const url = new URL(`${this.baseUrl}/api/v1/guardrails/summary`);
    if (since !== undefined) url.searchParams.set("since", since.toISOString());
    if (until !== undefined) url.searchParams.set("until", until.toISOString());
    return this.requestJson(url, GuardrailSummarySchema);
  }

  /** GET /api/v1/agents */
  async listAgents(): Promise<AgentCard[]> {
    const url = new URL(`${this.baseUrl}/api/v1/agents`);
    return this.requestJson(url, AgentCardListSchema);
  }

  /**
   * GET /api/v1/agents/{agentId}
   *
   * @throws {ExplainabilityClientError} status=404 on unknown agent id.
   */
  async getAgentCard(agentId: string): Promise<AgentCard> {
    const url = new URL(
      `${this.baseUrl}/api/v1/agents/${encodeURIComponent(agentId)}`,
    );
    return this.requestJson(url, AgentCardSchema);
  }

  /**
   * GET /api/v1/agents/{agentId}/audit
   *
   * @throws {ExplainabilityClientError} status=404 on unknown agent id.
   */
  async getAgentAudit(agentId: string): Promise<AgentAuditEntry[]> {
    const url = new URL(
      `${this.baseUrl}/api/v1/agents/${encodeURIComponent(agentId)}/audit`,
    );
    return this.requestJson(url, AgentAuditEntryListSchema);
  }

  /**
   * GET /api/v1/workflows/{wfId}/integrity
   *
   * @throws {ExplainabilityClientError} status=404 on unknown workflow id.
   */
  async getWorkflowIntegrity(wfId: string): Promise<IntegrityReport> {
    const url = new URL(
      `${this.baseUrl}/api/v1/workflows/${encodeURIComponent(wfId)}/integrity`,
    );
    return this.requestJson(url, IntegrityReportSchema);
  }

  /**
   * GET /api/v1/workflows/{wfId}/compliance
   *
   * @throws {ExplainabilityClientError} status=404 on unknown workflow id.
   */
  async getWorkflowCompliance(wfId: string): Promise<ComplianceBundle> {
    const url = new URL(
      `${this.baseUrl}/api/v1/workflows/${encodeURIComponent(wfId)}/compliance`,
    );
    return this.requestJson(url, ComplianceBundleSchema);
  }

  /**
   * GET /api/v1/compliance/summary[?since=<iso>&until=<iso>]
   *
   * @throws {ExplainabilityClientError} status=null on network/parse error.
   */
  async getComplianceSummary(
    since?: Date,
    until?: Date,
  ): Promise<ComplianceSummary> {
    const url = new URL(`${this.baseUrl}/api/v1/compliance/summary`);
    if (since !== undefined) url.searchParams.set("since", since.toISOString());
    if (until !== undefined) url.searchParams.set("until", until.toISOString());
    return this.requestJson(url, ComplianceSummarySchema);
  }

  /**
   * GET /api/v1/logs[?concerns=...&level=...&search=...&since=...&limit=...]
   *
   * @throws {ExplainabilityClientError} status=null on network/parse error.
   */
  async queryLogs(params?: {
    concerns?: readonly string[] | undefined;
    level?: string | null | undefined;
    search?: string | null | undefined;
    since?: Date | undefined;
    limit?: number | undefined;
  }): Promise<LogRow[]> {
    const url = new URL(`${this.baseUrl}/api/v1/logs`);
    if (params?.concerns !== undefined) {
      for (const concern of params.concerns) {
        url.searchParams.append("concerns", concern);
      }
    }
    if (params?.level) url.searchParams.set("level", params.level);
    if (params?.search) url.searchParams.set("search", params.search);
    if (params?.since !== undefined) {
      url.searchParams.set("since", params.since.toISOString());
    }
    if (params?.limit !== undefined) {
      url.searchParams.set("limit", String(params.limit));
    }
    return this.requestJson(url, LogRowListSchema);
  }

  /**
   * Centralised request helper — applies the error-translation table:
   *  - Network failure (fetch rejects)  → ExplainabilityClientError(message, null)
   *  - HTTP 4xx / 5xx                   → ExplainabilityClientError(detail, status)
   *  - Body unreadable / Zod parse fail → ExplainabilityClientError(zodMessage, null)
   */
  private async requestJson<T>(url: URL, schema: z.ZodType<T>): Promise<T> {
    let res: Response;
    try {
      res = await fetch(url.toString());
    } catch (cause) {
      throw new ExplainabilityClientError(
        cause instanceof Error ? cause.message : "Network error",
        null,
      );
    }

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = (await res.json()) as { detail?: string };
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        // Body unreadable — keep the status-code message.
      }
      throw new ExplainabilityClientError(detail, res.status);
    }

    let raw: unknown;
    try {
      raw = await res.json();
    } catch (cause) {
      throw new ExplainabilityClientError(
        cause instanceof Error ? cause.message : "Failed to parse response body",
        null,
      );
    }

    const result = schema.safeParse(raw);
    if (!result.success) {
      throw new ExplainabilityClientError(result.error.message, null);
    }
    return result.data;
  }
}
