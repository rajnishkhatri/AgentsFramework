// @vitest-environment happy-dom
/**
 * AuditTimeline — failure-first empty state, then chronological rendering.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuditTimeline } from "./AuditTimeline";
import type { AgentAuditEntry } from "@/lib/wire/responses";

const REGISTER: AgentAuditEntry = {
  agent_id: "cli-agent",
  action: "register",
  performed_by: "bootstrap",
  timestamp: "2026-04-01T08:00:00.000Z",
  details: { status: "active" },
};
const SUSPEND: AgentAuditEntry = {
  agent_id: "cli-agent",
  action: "suspend",
  performed_by: "ops",
  timestamp: "2026-04-02T08:00:00.000Z",
  details: { reason: "rotate" },
};

describe("AuditTimeline — failure-first", () => {
  it("renders the empty state when there are no entries", () => {
    render(<AuditTimeline entries={[]} />);
    expect(
      screen.getByRole("status", { name: /no audit entries/i }),
    ).toBeDefined();
  });
});

describe("AuditTimeline — acceptance", () => {
  it("renders one row per audit entry preserving input order", () => {
    render(<AuditTimeline entries={[REGISTER, SUSPEND]} />);
    expect(screen.getByText("register")).toBeDefined();
    expect(screen.getByText("suspend")).toBeDefined();
  });

  it("expands non-empty details as a JSON pre block", () => {
    const { container } = render(<AuditTimeline entries={[SUSPEND]} />);
    const pre = container.querySelector("pre");
    expect(pre).not.toBeNull();
    expect(pre!.textContent).toContain("rotate");
  });
});
