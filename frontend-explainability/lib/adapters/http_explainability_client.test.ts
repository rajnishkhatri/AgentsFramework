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

// --- getGuardrailSummary — failure first (S2.1.1) ---

describe("HttpExplainabilityClient.getGuardrailSummary — failure paths", () => {
  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getGuardrailSummary()).rejects.toMatchObject({
      status: 500,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getGuardrailSummary()).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(200, { total_checks: "many" }),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getGuardrailSummary()).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getGuardrailSummary — acceptance", () => {
  it("returns parsed all-zero summary when there are no events", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(200, {
        total_checks: 0,
        pass_count: 0,
        fail_count: 0,
        pass_rate: 0,
        fail_action_distribution: {},
        per_validator: [],
        recent_failures: [],
        trend_pass_rate_delta: 0,
      }),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getGuardrailSummary();
    expect(result.total_checks).toBe(0);
    expect(result.per_validator).toEqual([]);
    expect(result.recent_failures).toEqual([]);
  });

  it("appends since/until query params when provided", async () => {
    const payload = {
      total_checks: 1,
      pass_count: 1,
      fail_count: 0,
      pass_rate: 1,
      fail_action_distribution: {},
      per_validator: [
        {
          name: "prompt_injection",
          total_checks: 1,
          pass_count: 1,
          fail_count: 0,
          pass_rate: 1,
        },
      ],
      recent_failures: [],
      trend_pass_rate_delta: 0,
    };
    const fetchMock = makeFetchStub(200, payload);
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const since = new Date("2026-04-01T00:00:00.000Z");
    const until = new Date("2026-05-01T00:00:00.000Z");
    const result = await client.getGuardrailSummary(since, until);
    expect(result.total_checks).toBe(1);
    expect(result.per_validator).toHaveLength(1);
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("since=2026-04-01");
    expect(calledUrl).toContain("until=2026-05-01");
  });
});

// --- listAgents / getAgentCard / getAgentAudit (S2.2.1) — failure first ---

const SAMPLE_CARD = {
  agent_id: "cli-agent",
  agent_name: "CLI Agent",
  owner: "ops",
  version: "1.0",
  description: "",
  capabilities: [
    { name: "shell.run", description: "", parameters: {} },
  ],
  policies: [
    { name: "never-rm-rf", description: "", rules: {} },
  ],
  status: "active",
  valid_until: null,
  parent_agent_id: null,
  signature_truncated: "aaaaaaaa…bbbbbbbb",
  signature_verified: true,
  signature_verification_status: "verified",
  created_at: "2026-04-01T00:00:00.000Z",
  updated_at: "2026-04-01T00:00:00.000Z",
};

const SAMPLE_AUDIT = {
  agent_id: "cli-agent",
  action: "register",
  performed_by: "bootstrap",
  timestamp: "2026-04-01T08:00:00.000Z",
  details: { status: "active" },
};

describe("HttpExplainabilityClient.listAgents — failure paths", () => {
  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.listAgents()).rejects.toMatchObject({ status: 500 });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.listAgents()).rejects.toMatchObject({ status: null });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, [{ agent_id: 12345 }]));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.listAgents()).rejects.toMatchObject({ status: null });
  });
});

describe("HttpExplainabilityClient.listAgents — acceptance", () => {
  it("returns parsed AgentCard[] on 200", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, [SAMPLE_CARD]));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.listAgents();
    expect(result).toHaveLength(1);
    expect(result[0]?.agent_id).toBe("cli-agent");
    expect(result[0]?.signature_verified).toBe(true);
  });
});

describe("HttpExplainabilityClient.getAgentCard — failure paths", () => {
  it("throws status=404 on unknown agent", async () => {
    vi.stubGlobal("fetch", makeFetchStub(404, { detail: "Unknown agent" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getAgentCard("nope")).rejects.toMatchObject({
      status: 404,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getAgentCard("cli-agent")).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, { agent_id: "x" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getAgentCard("x")).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getAgentCard — acceptance", () => {
  it("URL-encodes the agent id", async () => {
    const fetchMock = makeFetchStub(200, SAMPLE_CARD);
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await client.getAgentCard("agent with space");
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("/api/v1/agents/agent%20with%20space");
  });
});

describe("HttpExplainabilityClient.getAgentAudit — failure paths", () => {
  it("throws status=404 on unknown agent", async () => {
    vi.stubGlobal("fetch", makeFetchStub(404, { detail: "Unknown agent" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getAgentAudit("nope")).rejects.toMatchObject({
      status: 404,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getAgentAudit("cli-agent")).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, [{ action: 12 }]));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getAgentAudit("x")).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getAgentAudit — acceptance", () => {
  it("returns [] when there are no audit entries", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, []));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getAgentAudit("cli-agent");
    expect(result).toEqual([]);
  });

  it("returns parsed AgentAuditEntry[] on 200", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, [SAMPLE_AUDIT]));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getAgentAudit("cli-agent");
    expect(result).toHaveLength(1);
    expect(result[0]?.action).toBe("register");
  });
});

// --- getWorkflowIntegrity (S3.1.1) — failure first ---

describe("HttpExplainabilityClient.getWorkflowIntegrity — failure paths", () => {
  it("throws status=404 on unknown workflow", async () => {
    vi.stubGlobal("fetch", makeFetchStub(404, { detail: "Unknown" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowIntegrity("wf-x")).rejects.toMatchObject({
      status: 404,
    });
  });

  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowIntegrity("wf-x")).rejects.toMatchObject({
      status: 500,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowIntegrity("wf-x")).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, { workflow_id: 12 }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowIntegrity("wf-x")).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getWorkflowIntegrity — acceptance", () => {
  it("returns parsed IntegrityReport on a tampered chain", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(200, {
        workflow_id: "wf-tamper",
        chain_valid: false,
        broken_at_event_id: "evt-2",
        expected_hash: "a".repeat(64),
        actual_hash: "b".repeat(64),
      }),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getWorkflowIntegrity("wf-tamper");
    expect(result.chain_valid).toBe(false);
    expect(result.broken_at_event_id).toBe("evt-2");
    expect(result.expected_hash).not.toEqual(result.actual_hash);
  });

  it("URL-encodes the workflow id", async () => {
    const fetchMock = makeFetchStub(200, {
      workflow_id: "wf x",
      chain_valid: true,
      broken_at_event_id: null,
      expected_hash: null,
      actual_hash: null,
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await client.getWorkflowIntegrity("wf x");
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("/api/v1/workflows/wf%20x/integrity");
  });
});

// --- getWorkflowCompliance (S3.1.2) — failure first ---

const SAMPLE_BUNDLE = {
  workflow_id: "wf-c",
  event_count: 0,
  hash_chain_valid: true,
  bundle_type: "compliance_audit",
  exported_at: null,
  events: [],
  identity_cards: {},
  audit_trails: {},
  phase_decisions: [],
  correlation_health: {
    has_trace_id: true,
    has_user_id: true,
    has_task_id: true,
    has_agent_id: true,
    missing_keys: [],
  },
  integrity: {
    workflow_id: "wf-c",
    chain_valid: true,
    broken_at_event_id: null,
    expected_hash: null,
    actual_hash: null,
  },
};

describe("HttpExplainabilityClient.getWorkflowCompliance — failure paths", () => {
  it("throws status=404 on unknown workflow", async () => {
    vi.stubGlobal("fetch", makeFetchStub(404, { detail: "Unknown" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowCompliance("wf-x")).rejects.toMatchObject({
      status: 404,
    });
  });

  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowCompliance("wf-x")).rejects.toMatchObject({
      status: 500,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowCompliance("wf-x")).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, { workflow_id: "wf-x" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getWorkflowCompliance("wf-x")).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getWorkflowCompliance — acceptance", () => {
  it("returns a parsed ComplianceBundle on a fully-correlated workflow", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, SAMPLE_BUNDLE));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getWorkflowCompliance("wf-c");
    expect(result.workflow_id).toBe("wf-c");
    expect(result.bundle_type).toBe("compliance_audit");
    expect(result.correlation_health.missing_keys).toEqual([]);
  });

  it("preserves missing_keys when the backend reports gaps", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetchStub(200, {
        ...SAMPLE_BUNDLE,
        correlation_health: {
          has_trace_id: true,
          has_user_id: false,
          has_task_id: true,
          has_agent_id: true,
          missing_keys: ["user_id"],
        },
      }),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getWorkflowCompliance("wf-c");
    expect(result.correlation_health.has_user_id).toBe(false);
    expect(result.correlation_health.missing_keys).toEqual(["user_id"]);
  });
});

// --- queryLogs (S4.3.1) — failure first ---

const SAMPLE_LOG = {
  concern: "guards",
  timestamp: "2026-04-26T08:00:00.000Z",
  logger: "services.guardrails",
  level: "INFO",
  message: "ok",
  raw: "raw line",
};

describe("HttpExplainabilityClient.queryLogs — failure paths", () => {
  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.queryLogs()).rejects.toMatchObject({ status: 500 });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.queryLogs()).rejects.toMatchObject({ status: null });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, [{ concern: 12 }]));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.queryLogs()).rejects.toMatchObject({ status: null });
  });
});

describe("HttpExplainabilityClient.queryLogs — acceptance", () => {
  it("returns parsed LogRow[] on 200", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, [SAMPLE_LOG]));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.queryLogs();
    expect(result).toHaveLength(1);
    expect(result[0]?.concern).toBe("guards");
    expect(result[0]?.level).toBe("INFO");
  });

  it("appends every concern as a repeated query param", async () => {
    const fetchMock = makeFetchStub(200, []);
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await client.queryLogs({
      concerns: ["guards", "tools"],
      level: "ERROR",
      search: "boom",
      limit: 50,
    });
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("concerns=guards");
    expect(calledUrl).toContain("concerns=tools");
    expect(calledUrl).toContain("level=ERROR");
    expect(calledUrl).toContain("search=boom");
    expect(calledUrl).toContain("limit=50");
  });

  it("appends since as ISO string when provided", async () => {
    const fetchMock = makeFetchStub(200, []);
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await client.queryLogs({
      since: new Date("2026-04-01T00:00:00.000Z"),
    });
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("since=2026-04-01");
  });
});

// --- Phase 1 / 2: listWorkflows since+until + getComplianceSummary ---

describe("HttpExplainabilityClient.listWorkflows — range filter", () => {
  it("appends since AND until as ISO strings when provided", async () => {
    const fetchMock = makeFetchStub(200, []);
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await client.listWorkflows(
      new Date("2026-04-01T00:00:00.000Z"),
      new Date("2026-05-01T00:00:00.000Z"),
    );
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("since=2026-04-01");
    expect(calledUrl).toContain("until=2026-05-01");
  });
});

const SAMPLE_COMPLIANCE_SUMMARY = {
  rows: [
    {
      workflow: {
        workflow_id: "wf-clean",
        started_at: "2026-04-26T12:00:00.000Z",
        event_count: 4,
        status: "completed",
        primary_agent_id: "cli-agent",
      },
      integrity: {
        workflow_id: "wf-clean",
        chain_valid: true,
        broken_at_event_id: null,
        expected_hash: null,
        actual_hash: null,
      },
    },
  ],
  generated_at: "2026-04-26T14:00:00.000Z",
  since: null,
  until: null,
};

describe("HttpExplainabilityClient.getComplianceSummary — failure paths", () => {
  it("throws status=500 on server error", async () => {
    vi.stubGlobal("fetch", makeFetchStub(500, { detail: "boom" }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getComplianceSummary()).rejects.toMatchObject({
      status: 500,
    });
  });

  it("throws status=null on network rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getComplianceSummary()).rejects.toMatchObject({
      status: null,
    });
  });

  it("throws status=null when payload fails Zod parse", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, { rows: [] }));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await expect(client.getComplianceSummary()).rejects.toMatchObject({
      status: null,
    });
  });
});

describe("HttpExplainabilityClient.getComplianceSummary — acceptance", () => {
  it("returns parsed ComplianceSummary on 200", async () => {
    vi.stubGlobal("fetch", makeFetchStub(200, SAMPLE_COMPLIANCE_SUMMARY));
    const client = new HttpExplainabilityClient("http://localhost:8001");
    const result = await client.getComplianceSummary();
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0]?.workflow.workflow_id).toBe("wf-clean");
    expect(result.rows[0]?.integrity?.chain_valid).toBe(true);
  });

  it("appends both since and until when provided", async () => {
    const fetchMock = makeFetchStub(200, SAMPLE_COMPLIANCE_SUMMARY);
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpExplainabilityClient("http://localhost:8001");
    await client.getComplianceSummary(
      new Date("2026-04-01T00:00:00.000Z"),
      new Date("2026-05-01T00:00:00.000Z"),
    );
    const calledUrl = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(calledUrl).toContain("compliance/summary");
    expect(calledUrl).toContain("since=2026-04-01");
    expect(calledUrl).toContain("until=2026-05-01");
  });
});
