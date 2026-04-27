// @vitest-environment happy-dom
/**
 * DecisionList — failure-first then phase grouping.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DecisionList } from "./DecisionList";
import type { DecisionRecord } from "@/lib/wire/responses";

const ROUTING: DecisionRecord = {
  workflow_id: "wf-x",
  phase: "routing",
  description: "picked gpt-4o",
  alternatives: ["gpt-4o-mini", "claude-3-opus"],
  rationale: "capable-for-planning",
  confidence: 0.85,
  timestamp: "2026-04-26T08:00:00.000Z",
};
const EVAL: DecisionRecord = {
  workflow_id: "wf-x",
  phase: "evaluation",
  description: "continue",
  alternatives: ["retry", "escalate"],
  rationale: "no errors",
  confidence: 0.95,
  timestamp: "2026-04-26T08:00:01.000Z",
};

describe("DecisionList — failure-first", () => {
  it("renders the empty state when decisions is []", () => {
    render(<DecisionList decisions={[]} />);
    expect(screen.getByRole("status", { name: /no decisions/i })).toBeDefined();
  });
});

describe("DecisionList — acceptance", () => {
  it("groups decisions under a phase heading", () => {
    render(<DecisionList decisions={[ROUTING, EVAL]} />);
    expect(screen.getByLabelText(/phase routing/i)).toBeDefined();
    expect(screen.getByLabelText(/phase evaluation/i)).toBeDefined();
    expect(screen.getByText(/picked gpt-4o/i)).toBeDefined();
    expect(screen.getByText(/^continue$/i)).toBeDefined();
  });

  it("renders one filter chip per workflow phase as a button (FD4.SEM)", () => {
    render(<DecisionList decisions={[ROUTING]} />);
    const buttons = screen.getAllByRole("button");
    const phaseButtons = buttons.filter(
      (btn) => btn.textContent && /^[a-z_]+$/.test(btn.textContent.trim()),
    );
    expect(phaseButtons.length).toBeGreaterThanOrEqual(9);
  });

  it("filter chips expose aria-pressed (FD4.LBL)", () => {
    render(<DecisionList decisions={[ROUTING]} />);
    const routing = screen.getByRole("button", { name: "routing" });
    expect(routing.getAttribute("aria-pressed")).toBe("false");
  });

  it("renders confidence as a <progress> with aria-valuenow", () => {
    const { container } = render(<DecisionList decisions={[ROUTING]} />);
    const progress = container.querySelector("progress");
    expect(progress).not.toBeNull();
    expect(progress!.getAttribute("aria-valuenow")).toBe("85");
    expect(progress!.getAttribute("aria-valuemax")).toBe("100");
  });

  it("rationale is hidden by default and exposed via aria-expanded toggle", () => {
    render(<DecisionList decisions={[ROUTING]} />);
    const toggle = screen.getByRole("button", { name: /show rationale/i });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("capable-for-planning")).toBeNull();
  });
});
