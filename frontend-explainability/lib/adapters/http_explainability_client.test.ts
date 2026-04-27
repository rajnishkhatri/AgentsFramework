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

// --- getWorkflowEvents — failure first ---

describe("HttpExplainabilityClient.getWorkflowEvents — failure paths", () => {
  it("throws status=404 when workflow id is unknown", async () => {
    vi.stubGlobal("fetch", makeFetchStub(404, { detail: "Unknown workflow" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowEvents("wf-x")).rejects.toMatchObject({
      status: 404,
    });
  });

  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowEvents("wf-x")).rejects.toMatchObject({
      status: 500,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowEvents("wf-x")).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(200, { workflow_id: "wf-x", event_count: "five" }),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowEvents("wf-x")).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getWorkflowEvents — acceptance", () => {
  it("returns parsed WorkflowEvents on 200", async () => {
    const fetchMock = makeFetchStub(200, {
      workflow_id: "wf-x",
      event_count: 1,
      hash_chain_valid: true,
      events: [
        {
          event_id: "e1",
          workflow_id: "wf-x",
          event_type: "task_started",
          timestamp: "2026-04-26T08:00:00+00:00",
          step: null,
          details: { task_input: "hello" },
          integrity_hash: "abc",
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getWorkflowEvents("wf x"); // tests URL encoding
    expect(result.workflow_id).toBe("wf-x");
    expect(result.hash_chain_valid).toBe(true);
    expect(result.events).toHaveLength(1);

    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("/api/v1/workflows/wf%20x/events");
  });
});

// --- getWorkflowDecisions — failure first ---

describe("HttpExplainabilityClient.getWorkflowDecisions — failure paths", () => {
  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowDecisions("wf-x")).rejects.toMatchObject({
      status: 500,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowDecisions("wf-x")).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, [{ phase: 12 }]));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowDecisions("wf-x")).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getWorkflowDecisions — acceptance", () => {
  it("returns [] when server returns empty list (not 404)", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, []));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getWorkflowDecisions("wf-x");
    expect(result).toEqual([]);
  });

  it("returns parsed DecisionRecord[] on 200", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(200, [
        {
          workflow_id: "wf-x",
          phase: "routing",
          description: "picked",
          alternatives: ["a", "b"],
          rationale: "because",
          confidence: 0.9,
          timestamp: "2026-04-26T08:00:00+00:00",
        },
      ]),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getWorkflowDecisions("wf-x");
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      phase: "routing",
      confidence: 0.9,
    });
  });
});

// --- getDashboardMetrics — failure first ---

describe("HttpExplainabilityClient.getDashboardMetrics — failure paths", () => {
  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getDashboardMetrics()).rejects.toMatchObject({
      status: 500,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getDashboardMetrics()).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, { total_runs: "five" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getDashboardMetrics()).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getDashboardMetrics — acceptance", () => {
  it("returns parsed DashboardMetrics with all-zero on empty", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(200, {
        total_runs: 0,
        p50_latency_ms: 0,
        p95_latency_ms: 0,
        total_cost_usd: 0,
        guardrail_pass_rate: 0,
        hash_chain_valid_count: 0,
        hash_chain_invalid_count: 0,
        time_series_cost: [],
        time_series_latency: [],
        time_series_tokens: [],
        model_distribution: {},
      }),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getDashboardMetrics();
    expect(result.total_runs).toBe(0);
    expect(result.model_distribution).toEqual({});
  });

  it("appends since/until query params when provided", async () => {
    const fetchMock = makeFetchStub(200, {
      total_runs: 0,
      p50_latency_ms: 0,
      p95_latency_ms: 0,
      total_cost_usd: 0,
      guardrail_pass_rate: 0,
      hash_chain_valid_count: 0,
      hash_chain_invalid_count: 0,
      time_series_cost: [],
      time_series_latency: [],
      time_series_tokens: [],
      model_distribution: {},
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const since = new Date("2026-04-01T00:00:00.000Z");
    const until = new Date("2026-05-01T00:00:00.000Z");
    await client.getDashboardMetrics(since, until);
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("since=2026-04-01");
    expect(calledUrl).toContain("until=2026-05-01");
  });
});
