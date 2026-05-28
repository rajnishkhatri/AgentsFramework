// @vitest-environment happy-dom
/**
 * RecentFailuresTable — failure-first empty state, then linked-row rendering.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RecentFailuresTable } from "./RecentFailuresTable";
import type { GuardrailFailure } from "@/lib/wire/responses";

const FAILURE: GuardrailFailure = {
  workflow_id: "wf-bad",
  validator: "output_pii_scan",
  fail_action: "reject",
  timestamp: "2026-04-26T09:00:00.000Z",
};

describe("RecentFailuresTable — failure-first", () => {
  it("renders the empty state when there are no failures", () => {
    render(<RecentFailuresTable failures={[]} />);
    expect(
      screen.getByRole("status", { name: /no recent failures/i }),
    ).toBeDefined();
  });
});

describe("RecentFailuresTable — acceptance", () => {
  it("links each row's workflow to /traces/[wf_id]", () => {
    render(<RecentFailuresTable failures={[FAILURE]} />);
    const link = screen.getByRole("link", { name: /wf-bad/i });
    expect(link.getAttribute("href")).toBe("/traces/wf-bad");
  });

  it("shows '—' when fail_action is null", () => {
    render(
      <RecentFailuresTable
        failures={[{ ...FAILURE, fail_action: null }]}
      />,
    );
    expect(screen.getByText("—")).toBeDefined();
  });
});
