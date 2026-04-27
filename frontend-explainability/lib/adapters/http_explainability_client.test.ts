/**
 * Adapter tests for HttpExplainabilityClient.
 *
 * TDD order per rule FD6.ADAPTER: 404, 500, network timeout, Zod parse error → happy path.
 * Uses vi.stubGlobal('fetch', ...) — no actual HTTP calls.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { HttpExplainabilityClient } from "./http_explainability_client";
import { ExplainabilityClientError } from "@/lib/ports/explainability_client";

function makeFetchStub(status: number, body: unknown): typeof fetch {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HttpExplainabilityClient.listWorkflows — failure paths", () => {
  it("throws ExplainabilityClientError with status 404 when server returns 404", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(404, { detail: "Not found" }),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.listWorkflows()).rejects.toThrow(ExplainabilityClientError);
    await expect(client.listWorkflows()).rejects.toMatchObject({ status: 404 });
  });

  it("throws ExplainabilityClientError with status 500 when server returns 500", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(500, { detail: "Internal server error" }),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.listWorkflows()).rejects.toThrow(ExplainabilityClientError);
    await expect(client.listWorkflows()).rejects.toMatchObject({ status: 500 });
  });

  it("throws ExplainabilityClientError with status null on network timeout/rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Network connection refused")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.listWorkflows()).rejects.toThrow(ExplainabilityClientError);
    await expect(client.listWorkflows()).rejects.toMatchObject({ status: null });
  });

  it("throws ExplainabilityClientError with status null when response fails Zod parse", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(200, [{ workflow_id: 12345 }]), // workflow_id must be string
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.listWorkflows()).rejects.toThrow(ExplainabilityClientError);
    await expect(client.listWorkflows()).rejects.toMatchObject({ status: null });
  });
});

describe("HttpExplainabilityClient.listWorkflows — acceptance", () => {
  it("returns parsed WorkflowSummary[] on a 200 response", async () => {
    const now = new Date().toISOString();
    const payload = [
      {
        workflow_id: "wf-abc",
        started_at: now,
        event_count: 5,
        status: "completed",
        primary_agent_id: "agent-1",
      },
    ];
    vi.stubGlobal("fetch", makeFetchStub(200, payload));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.listWorkflows();
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ workflow_id: "wf-abc", event_count: 5 });
  });

  it("appends since query-param to the URL when provided", async () => {
    const payload: unknown[] = [];
    const fetchMock = makeFetchStub(200, payload);
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const since = new Date("2026-01-01T00:00:00.000Z");
    await client.listWorkflows(since);
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("since=2026-01-01T00%3A00%3A00.000Z");
  });
});
