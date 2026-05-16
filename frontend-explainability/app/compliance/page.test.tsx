// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ComplianceHomePage from "./page";

const {
  listAgentsMock,
  getGuardrailSummaryMock,
  getComplianceSummaryMock,
} = vi.hoisted(() => ({
  listAgentsMock: vi.fn(),
  getGuardrailSummaryMock: vi.fn(),
  getComplianceSummaryMock: vi.fn(),
}));

vi.mock("@/lib/composition", () => ({
  buildAdapters: () => ({
    apiUrl: "http://localhost:8001",
    explainabilityClient: {
      listAgents: listAgentsMock,
      getGuardrailSummary: getGuardrailSummaryMock,
      getComplianceSummary: getComplianceSummaryMock,
    },
  }),
}));

vi.mock("@/components/guardrails/ValidatorTable", () => ({
  ValidatorTable: () => <div data-testid="validator-table" />,
}));
vi.mock("@/components/guardrails/ActionDistributionPie", () => ({
  ActionDistributionPie: () => <div data-testid="action-distribution" />,
}));
vi.mock("@/components/guardrails/RecentFailuresTable", () => ({
  RecentFailuresTable: () => <div data-testid="recent-failures" />,
}));
vi.mock("@/components/compliance/IntegrityStatusTable", () => ({
  IntegrityStatusTable: () => <div data-testid="integrity-table" />,
}));
vi.mock("@/components/compliance/AgentSummaryGrid", () => ({
  AgentSummaryGrid: () => <div data-testid="agent-summary" />,
}));
vi.mock("@/components/compliance/ComplianceExportButtons", () => ({
  ComplianceExportButtons: () => <div data-testid="export-buttons" />,
}));

beforeEach(() => {
  listAgentsMock.mockReset();
  getGuardrailSummaryMock.mockReset();
  getComplianceSummaryMock.mockReset();

  listAgentsMock.mockResolvedValue([]);
  getGuardrailSummaryMock.mockResolvedValue({
    total_checks: 0,
    pass_count: 0,
    fail_count: 0,
    pass_rate: 0,
    fail_action_distribution: {},
    per_validator: [],
    recent_failures: [],
    trend_pass_rate_delta: 0,
  });
  getComplianceSummaryMock.mockResolvedValue({
    rows: [],
    generated_at: "2026-04-29T18:35:00.000Z",
    since: null,
    until: null,
  });
});

describe("/compliance page query propagation", () => {
  it("forwards since/until from searchParams to summary and guardrail calls", async () => {
    const node = await ComplianceHomePage({
      searchParams: Promise.resolve({
        since: "2026-04-01T00:00:00.000Z",
        until: "2026-05-01T00:00:00.000Z",
      }),
    });
    render(node);

    expect(getComplianceSummaryMock).toHaveBeenCalledTimes(1);
    expect(getGuardrailSummaryMock).toHaveBeenCalledTimes(1);
    expect(listAgentsMock).toHaveBeenCalledTimes(1);

    const summarySince = getComplianceSummaryMock.mock.calls[0]?.[0] as Date;
    const summaryUntil = getComplianceSummaryMock.mock.calls[0]?.[1] as Date;
    expect(summarySince.toISOString()).toBe("2026-04-01T00:00:00.000Z");
    expect(summaryUntil.toISOString()).toBe("2026-05-01T00:00:00.000Z");

    const guardSince = getGuardrailSummaryMock.mock.calls[0]?.[0] as Date;
    const guardUntil = getGuardrailSummaryMock.mock.calls[0]?.[1] as Date;
    expect(guardSince.toISOString()).toBe("2026-04-01T00:00:00.000Z");
    expect(guardUntil.toISOString()).toBe("2026-05-01T00:00:00.000Z");

    expect(screen.getByTestId("active-window").textContent).toContain(
      "Window: 2026-04-01T00:00:00.000Z",
    );
  });

  it("treats invalid/missing params as all-time and passes undefined bounds", async () => {
    const node = await ComplianceHomePage({
      searchParams: Promise.resolve({
        since: "not-a-date",
      }),
    });
    render(node);

    expect(getComplianceSummaryMock).toHaveBeenCalledWith(undefined, undefined);
    expect(getGuardrailSummaryMock).toHaveBeenCalledWith(undefined, undefined);
    expect(screen.getByTestId("active-window").textContent).toContain(
      "All-time view",
    );
  });
});
