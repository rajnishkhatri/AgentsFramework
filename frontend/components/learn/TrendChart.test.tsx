/**
 * TrendChart — FR-9 / FR-2 UI (Epic F).
 * Repo convention: renderToStaticMarkup + JSDOM (no @testing-library/react).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TrendChart } from "./TrendChart";
import type { TrendPoint } from "@/lib/translators/progress_screen_vm";

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

const TWO: readonly TrendPoint[] = [
  { atISO: "2026-07-08T10:00:00.000Z", accuracyPct: 40 },
  { atISO: "2026-07-12T10:00:00.000Z", accuracyPct: 80 },
];

describe("TrendChart — FR-9 / FR-2", () => {
  it("renders_polyline_and_a11y_fallback for ≥2 points", () => {
    const doc = dom(<TrendChart points={TWO} />);
    const svg = doc.querySelector('[data-testid="trend-chart"] svg');
    expect(svg).not.toBeNull();
    const polyline = svg!.querySelector("polyline");
    expect(polyline).not.toBeNull();
    expect(polyline!.getAttribute("points")).toBeTruthy();
    // Theme token stroke (CSP-safe class / attribute, not dynamic nonce style).
    const stroke = polyline!.getAttribute("stroke") ?? "";
    expect(stroke).toMatch(/var\(--color-accent\)|--color-accent/);
    // Per-point markers (non-color signal).
    expect(svg!.querySelectorAll("circle").length).toBe(2);
    // a11y fallback
    const fallback =
      doc.querySelector('[data-testid="trend-chart-a11y"]') ??
      doc.querySelector(".sr-only");
    expect(fallback).not.toBeNull();
    expect(fallback!.textContent ?? "").toMatch(/accuracy|40|80/i);
  });

  it("no_line_for_empty_points (FR-1 UI)", () => {
    const doc = dom(<TrendChart points={[]} />);
    expect(doc.querySelector("polyline")).toBeNull();
    expect(doc.querySelector('[data-testid="trend-chart-empty"]')).not.toBeNull();
  });

  it("no_line_for_single_point (FR-2 UI)", () => {
    const doc = dom(
      <TrendChart
        points={[{ atISO: "2026-07-10T10:00:00.000Z", accuracyPct: 75 }]}
      />,
    );
    expect(doc.querySelector("polyline")).toBeNull();
    // Single marker ok; no slope.
    expect(doc.querySelectorAll("circle").length).toBeLessThanOrEqual(1);
  });
});
