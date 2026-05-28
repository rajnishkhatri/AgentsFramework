// @vitest-environment happy-dom
/**
 * TimeSeriesChart — empty-state vs chart shell rendering.
 *
 * The Recharts ResponsiveContainer needs a width measurement that
 * happy-dom does not provide; we don't try to assert SVG output here.
 * Instead the test guards two contracts that matter for FD5:
 *   * No data renders the documented empty state.
 *   * Non-empty data renders the chart container under the same
 *     `aria-label` so screen readers can find it.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TimeSeriesChart } from "./TimeSeriesChart";
import type { TimeSeriesPoint } from "@/lib/wire/responses";

const SAMPLE: TimeSeriesPoint[] = [
  { bucket: "2026-04-26T08:00:00.000Z", value: 0.001 },
  { bucket: "2026-04-26T09:00:00.000Z", value: 0.002 },
];

describe("TimeSeriesChart — failure first", () => {
  it("renders the empty state when no data is supplied", () => {
    render(<TimeSeriesChart title="Cost" unit="USD" data={[]} />);
    expect(screen.getByText(/no data in the selected range/i)).toBeDefined();
  });
});

describe("TimeSeriesChart — acceptance", () => {
  it("renders a labelled section + unit caption when data is present", () => {
    const { container } = render(
      <TimeSeriesChart title="Cost" unit="USD" data={SAMPLE} />,
    );
    const section = container.querySelector('section[aria-label="Cost"]');
    expect(section).not.toBeNull();
    expect(section!.textContent).toContain("USD");
    // The empty-state message MUST NOT be rendered.
    expect(
      section!.textContent?.includes("No data in the selected range"),
    ).toBe(false);
  });
});
