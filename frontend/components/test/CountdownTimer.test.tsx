/**
 * CountdownTimer — SSR structural tests (L1 jsdom; renderToStaticMarkup + JSDOM).
 *
 * The format/band logic is proven in format_clock.test.ts; here we assert the
 * view renders it faithfully with the right a11y contract: role="timer",
 * aria-live="off" (no per-second announcement), a text label (never color-only),
 * and a `data-state` band.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CountdownTimer } from "./CountdownTimer";

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("CountdownTimer", () => {
  it("renders mm:ss text for the remaining time", () => {
    const doc = dom(<CountdownTimer remainingMs={35 * 60_000} />);
    const el = doc.querySelector('[data-testid="test-timer"]')!;
    expect(el.textContent).toContain("35:00");
  });

  it("uses role=timer with aria-live off (no per-second announcement)", () => {
    const doc = dom(<CountdownTimer remainingMs={60_000} />);
    const el = doc.querySelector('[data-testid="test-timer"]')!;
    expect(el.getAttribute("role")).toBe("timer");
    expect(el.getAttribute("aria-live")).toBe("off");
  });

  it("carries a text aria-label so the signal is never color-only", () => {
    const doc = dom(<CountdownTimer remainingMs={90_000} sectionLabel="English" />);
    const el = doc.querySelector('[data-testid="test-timer"]')!;
    expect(el.getAttribute("aria-label")).toContain("English");
    expect(el.getAttribute("aria-label")).toContain("01:30");
  });

  it("exposes the urgency band via data-state (normal / warning / expired)", () => {
    const normal = dom(<CountdownTimer remainingMs={10 * 60_000} />);
    expect(normal.querySelector('[data-testid="test-timer"]')!.getAttribute("data-state")).toBe(
      "normal",
    );
    const warning = dom(<CountdownTimer remainingMs={60_000} />);
    expect(warning.querySelector('[data-testid="test-timer"]')!.getAttribute("data-state")).toBe(
      "warning",
    );
    const expired = dom(<CountdownTimer remainingMs={0} />);
    expect(expired.querySelector('[data-testid="test-timer"]')!.getAttribute("data-state")).toBe(
      "expired",
    );
  });
});
