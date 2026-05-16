// @vitest-environment happy-dom
/**
 * IntegrityStatusTable — failure-first empty state, then "all valid" and
 * "one tampered" snapshots (S3.2.1 AC).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { IntegrityStatusTable, type IntegrityRow } from "./IntegrityStatusTable";
import type { IntegrityReport, WorkflowSummary } from "@/lib/wire/responses";

function makeWorkflow(id: string): WorkflowSummary {
  return {
    workflow_id: id,
    started_at: "2026-04-26T08:00:00.000Z",
    event_count: 5,
    status: "completed",
    primary_agent_id: "cli-agent",
  };
}

function valid(id: string): IntegrityReport {
  return {
    workflow_id: id,
    chain_valid: true,
    broken_at_event_id: null,
    expected_hash: null,
    actual_hash: null,
  };
}

function tampered(id: string, eventId: string): IntegrityReport {
  return {
    workflow_id: id,
    chain_valid: false,
    broken_at_event_id: eventId,
    expected_hash: "a".repeat(64),
    actual_hash: "b".repeat(64),
  };
}

describe("IntegrityStatusTable — failure-first", () => {
  it("renders the empty state when there are no workflows", () => {
    render(<IntegrityStatusTable rows={[]} />);
    expect(screen.getByRole("status", { name: /no workflows/i })).toBeDefined();
  });
});

describe("IntegrityStatusTable — acceptance snapshots", () => {
  it('renders the "all valid" state -- every row tagged data-chain-valid="true"', () => {
    const rows: IntegrityRow[] = [
      { workflow: makeWorkflow("wf-a"), report: valid("wf-a") },
      { workflow: makeWorkflow("wf-b"), report: valid("wf-b") },
    ];
    const { container } = render(<IntegrityStatusTable rows={rows} />);
    const allRows = container.querySelectorAll("tbody tr");
    expect(allRows).toHaveLength(2);
    for (const tr of allRows) {
      expect(tr.getAttribute("data-chain-valid")).toBe("true");
    }
    expect(screen.getAllByText("valid")).toHaveLength(2);
  });

  it('renders the "one tampered" state -- failed row tagged data-chain-valid="false" + break id surfaced', () => {
    const rows: IntegrityRow[] = [
      { workflow: makeWorkflow("wf-clean"), report: valid("wf-clean") },
      {
        workflow: makeWorkflow("wf-tamper"),
        report: tampered("wf-tamper", "evt-2"),
      },
    ];
    const { container } = render(<IntegrityStatusTable rows={rows} />);
    const cleanRow = container.querySelector('[data-chain-valid="true"]');
    const tamperedRow = container.querySelector('[data-chain-valid="false"]');
    expect(cleanRow).not.toBeNull();
    expect(tamperedRow).not.toBeNull();
    expect(tamperedRow!.textContent).toContain("evt-2");
    expect(screen.getByText("tampered")).toBeDefined();
  });

  it('renders the "no integrity available" state with chainValid=null tag', () => {
    const rows: IntegrityRow[] = [
      { workflow: makeWorkflow("wf-x"), report: null },
    ];
    const { container } = render(<IntegrityStatusTable rows={rows} />);
    const tr = container.querySelector("tbody tr");
    expect(tr).not.toBeNull();
    expect(tr!.getAttribute("data-chain-valid")).toBe("null");
    expect(screen.getByText("unknown")).toBeDefined();
  });
});
