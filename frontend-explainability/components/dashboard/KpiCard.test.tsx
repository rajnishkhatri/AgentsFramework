// @vitest-environment happy-dom
/**
 * KpiCard rendering tests — one snapshot per tone, plus a failure-first
 * caption-omission case.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiCard, type KpiTone } from "./KpiCard";

describe("KpiCard — failure-first", () => {
  it("renders without a caption when one is not provided", () => {
    render(<KpiCard label="Total Runs" value="0" tone="neutral" />);
    expect(screen.getByText("Total Runs")).toBeDefined();
    expect(screen.getByText("0")).toBeDefined();
  });
});

describe("KpiCard — acceptance per tone", () => {
  const tones: KpiTone[] = ["green", "amber", "red", "neutral"];
  it.each(tones)("renders the %s tone via data-tone attribute", (tone) => {
    const { container } = render(
      <KpiCard label={`KPI ${tone}`} value="42" tone={tone} caption="caption" />,
    );
    const card = container.querySelector(`[data-tone="${tone}"]`);
    expect(card).not.toBeNull();
    expect(card!.getAttribute("aria-label")).toBe(`KPI ${tone}`);
  });
});
