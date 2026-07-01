/**
 * Phase 1.1 — surface classification (FR-J1/J2/J3, L1 deterministic, TAP-1).
 *
 * The width→surface decision is pure domain logic (F-R1), so it is exercised in
 * node with no React and no matchMedia. The `useSurface` hook (in use_surface.ts)
 * is a thin client wrapper over this classifier; the boundaries live here.
 */

import { describe, expect, it } from "vitest";
import { surfaceForWidth } from "./use_surface";

describe("surfaceForWidth — width to device surface (FR-J boundaries)", () => {
  it("classifies iPhone at/below 393pt (FR-J2) and up to the phone ceiling", () => {
    expect(surfaceForWidth(320)).toBe("iphone");
    expect(surfaceForWidth(393)).toBe("iphone"); // the FR-J2 iPhone width
    expect(surfaceForWidth(480)).toBe("iphone"); // phone ceiling (inclusive)
  });

  it("classifies iPad between the phone ceiling and the desktop floor (FR-J3)", () => {
    expect(surfaceForWidth(481)).toBe("ipad");
    expect(surfaceForWidth(768)).toBe("ipad");
    expect(surfaceForWidth(1024)).toBe("ipad"); // 11" landscape (inclusive)
  });

  it("classifies desktop above the iPad ceiling (FR-J1)", () => {
    expect(surfaceForWidth(1025)).toBe("desktop");
    expect(surfaceForWidth(1180)).toBe("desktop");
    expect(surfaceForWidth(1920)).toBe("desktop");
  });

  it("is total across the boundary — every non-negative width maps to a surface", () => {
    for (const w of [0, 1, 393, 480, 481, 1024, 1025, 5000]) {
      expect(["iphone", "ipad", "desktop"]).toContain(surfaceForWidth(w));
    }
  });
});
