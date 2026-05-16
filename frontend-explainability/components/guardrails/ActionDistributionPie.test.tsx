// @vitest-environment happy-dom
/**
 * ActionDistributionPie — empty-state vs chart shell rendering, plus a
 * regression sentry for hardcoded hex colours (Sprint 1 review P2.2).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ActionDistributionPie } from "./ActionDistributionPie";
import { readFileSync } from "fs";
import { resolve } from "path";

describe("ActionDistributionPie — empty state", () => {
  it("renders the no-rejections message when slices is empty", () => {
    render(<ActionDistributionPie slices={[]} />);
    expect(
      screen.getByText(/no guardrail rejections in this window/i),
    ).toBeDefined();
  });
});

describe("ActionDistributionPie — style sentry", () => {
  it("never falls back to hardcoded hex colors (token-only)", () => {
    const file = resolve(__dirname, "./ActionDistributionPie.tsx");
    const content = readFileSync(file, "utf-8");
    // Exclude any hex sequence inside CSS variable fallbacks.
    expect(content).not.toMatch(/#[0-9a-fA-F]{3,6}\b/);
  });
});
