// @vitest-environment happy-dom
/**
 * WorkflowsTable component tests.
 *
 * TDD order per sprint board: failure-first (empty state) before acceptance (rows).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WorkflowsTable } from "./WorkflowsTable";
import type { WorkflowSummary } from "@/lib/wire/responses";

const SAMPLE_WORKFLOW: WorkflowSummary = {
  workflow_id: "wf-test-001",
  started_at: "2026-04-27T12:00:00.000Z",
  event_count: 8,
  status: "completed",
  primary_agent_id: "agent-cli",
};

describe("WorkflowsTable — failure-first", () => {
  it("renders the empty state when workflows array is empty", () => {
    render(<WorkflowsTable workflows={[]} />);
    expect(
      screen.getByRole("status", { name: /no workflows/i }),
    ).toBeDefined();
    expect(screen.getByText(/no workflows recorded yet/i)).toBeDefined();
  });

  it("does not render a table element when workflows is empty", () => {
    const { container } = render(<WorkflowsTable workflows={[]} />);
    expect(container.querySelector("table")).toBeNull();
  });
});

describe("WorkflowsTable — acceptance", () => {
  it("renders a table with the five required columns", () => {
    render(<WorkflowsTable workflows={[SAMPLE_WORKFLOW]} />);
    expect(screen.getByText(/workflow id/i)).toBeDefined();
    expect(screen.getByText(/started/i)).toBeDefined();
    expect(screen.getByText(/status/i)).toBeDefined();
    expect(screen.getByText(/events/i)).toBeDefined();
    expect(screen.getByText(/primary agent/i)).toBeDefined();
  });

  it("renders the workflow_id as a link to /traces/[wf_id]", () => {
    render(<WorkflowsTable workflows={[SAMPLE_WORKFLOW]} />);
    const link = screen.getByRole("link", { name: /wf-test-001/i });
    expect(link).toBeDefined();
    expect((link as HTMLAnchorElement).href).toContain("/traces/wf-test-001");
  });

  it("renders all five columns for a complete workflow row", () => {
    render(<WorkflowsTable workflows={[SAMPLE_WORKFLOW]} />);
    expect(screen.getByText("wf-test-001")).toBeDefined();
    expect(screen.getByText("completed")).toBeDefined();
    expect(screen.getByText("8")).toBeDefined();
    expect(screen.getByText("agent-cli")).toBeDefined();
  });

  it("renders dash for null primary_agent_id", () => {
    const wf: WorkflowSummary = { ...SAMPLE_WORKFLOW, primary_agent_id: null };
    render(<WorkflowsTable workflows={[wf]} />);
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it("renders multiple rows when multiple workflows are provided", () => {
    const wf2: WorkflowSummary = {
      ...SAMPLE_WORKFLOW,
      workflow_id: "wf-test-002",
      status: "in_progress",
    };
    render(<WorkflowsTable workflows={[SAMPLE_WORKFLOW, wf2]} />);
    expect(screen.getByText("wf-test-001")).toBeDefined();
    expect(screen.getByText("wf-test-002")).toBeDefined();
  });
});
