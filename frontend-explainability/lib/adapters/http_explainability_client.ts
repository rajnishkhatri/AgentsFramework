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
  DashboardMetricsSchema,
  DecisionRecordListSchema,
  WorkflowEventsSchema,
  WorkflowSummaryListSchema,
  type DashboardMetrics,
  type DecisionRecord,
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
   * GET /api/v1/workflows[?since=<iso>]
   *
   * @throws {ExplainabilityClientError} on network, HTTP, or parse error.
   */
  async listWorkflows(since?: Date): Promise<WorkflowSummary[]> {
    const url = new URL(`${this.baseUrl}/api/v1/workflows`);
    if (since !== undefined) {
      url.searchParams.set("since", since.toISOString());
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
