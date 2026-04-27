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
import {
  WorkflowSummaryListSchema,
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

    const result = WorkflowSummaryListSchema.safeParse(raw);
    if (!result.success) {
      throw new ExplainabilityClientError(result.error.message, null);
    }
    return result.data;
  }
}
