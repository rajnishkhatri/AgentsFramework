// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ComplianceDeepDivePage from "./page";
import { ExplainabilityClientError } from "@/lib/ports/explainability_client";

const { getWorkflowComplianceMock, notFoundMock } = vi.hoisted(() => ({
  getWorkflowComplianceMock: vi.fn(),
  notFoundMock: vi.fn(),
}));

vi.mock("@/lib/composition", () => ({
  buildAdapters: () => ({
    explainabilityClient: {
      getWorkflowCompliance: getWorkflowComplianceMock,
    },
  }),
}));

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
}));

vi.mock("@/components/compliance/CorrelationHealthBadge", () => ({
  CorrelationHealthBadge: () => <div data-testid="correlation-badge" />,
}));

vi.mock("@/components/compliance/WorkflowDeepDive", () => ({
  WorkflowDeepDive: () => <div data-testid="workflow-deep-dive" />,
}));

beforeEach(() => {
  getWorkflowComplianceMock.mockReset();
  notFoundMock.mockReset();
});

describe("/compliance/[wf_id] page", () => {
  it("renders deep dive layout for a known workflow", async () => {
    getWorkflowComplianceMock.mockResolvedValue({
      workflow_id: "wf-known",
      event_count: 1,
      hash_chain_valid: true,
      bundle_type: "compliance_audit",
      exported_at: "2026-04-29T18:35:00.000Z",
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
        workflow_id: "wf-known",
        chain_valid: true,
        broken_at_event_id: null,
        expected_hash: null,
        actual_hash: null,
      },
    });

    const node = await ComplianceDeepDivePage({
      params: Promise.resolve({ wf_id: "wf-known" }),
    });
    render(node);

    expect(getWorkflowComplianceMock).toHaveBeenCalledWith("wf-known");
    expect(screen.getByText("wf-known")).toBeTruthy();
    expect(screen.getByTestId("correlation-badge")).toBeTruthy();
    expect(screen.getByTestId("workflow-deep-dive")).toBeTruthy();
  });

  it("calls notFound for a 404 from getWorkflowCompliance", async () => {
    getWorkflowComplianceMock.mockRejectedValue(
      new ExplainabilityClientError("missing", 404),
    );
    notFoundMock.mockImplementation(() => {
      throw new Error("NOT_FOUND_TRIGGERED");
    });

    await expect(
      ComplianceDeepDivePage({
        params: Promise.resolve({ wf_id: "wf-missing" }),
      }),
    ).rejects.toThrow("NOT_FOUND_TRIGGERED");

    expect(notFoundMock).toHaveBeenCalledTimes(1);
  });
});
