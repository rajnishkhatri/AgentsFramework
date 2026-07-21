/**
 * Phase 1.1 — surface classification (FR-J1/J2/J3, L1 deterministic, TAP-1).
 *
 * Wide-layout Direction 2b (ADR-0035): `coachMode` + 64px rail (FR-1/9/10).
 */

import { describe, expect, it } from "vitest";
import {
  coachMode,
  contentWidthAfterSidebar,
  isWideSurface,
  RAIL_COLLAPSED,
  RAIL_EXPANDED,
  SPLIT_MIN_CONTENT_WIDTH,
  surfaceForWidth,
} from "./use_surface";

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

describe("isWideSurface — nav helpers only (FR-8)", () => {
  it("is false only for iphone", () => {
    expect(isWideSurface("iphone")).toBe(false);
  });

  it("is true for ipad and desktop", () => {
    expect(isWideSurface("ipad")).toBe(true);
    expect(isWideSurface("desktop")).toBe(true);
  });
});

describe("coachMode + rail constants (FR-1, FR-9, FR-10)", () => {
  it("exports RAIL_COLLAPSED = 64 and keeps expanded / split floor", () => {
    expect(RAIL_COLLAPSED).toBe(64);
    expect(RAIL_EXPANDED).toBe(224);
    expect(SPLIT_MIN_CONTENT_WIDTH).toBe(900);
  });

  it("computes content width as viewport minus sidebar", () => {
    expect(contentWidthAfterSidebar(1200, false)).toBe(1200 - RAIL_EXPANDED);
    expect(contentWidthAfterSidebar(1200, true)).toBe(1200 - RAIL_COLLAPSED);
  });

  it("iphone → fullscreen regardless of content width", () => {
    expect(coachMode("iphone", 390, RAIL_COLLAPSED)).toBe("fullscreen");
    expect(coachMode("iphone", 1440, RAIL_COLLAPSED)).toBe("fullscreen");
  });

  it("FR-10: iPad landscape content ≥ 900 → inline (1024 − 64 = 960)", () => {
    expect(coachMode("ipad", 1024, RAIL_COLLAPSED)).toBe("inline");
  });

  it("FR-1: iPad portrait content < 900 → drawer (768 − 64 = 704)", () => {
    expect(coachMode("ipad", 768, RAIL_COLLAPSED)).toBe("drawer");
  });

  it("desktop wide → inline; mid-band collapsed → drawer", () => {
    expect(coachMode("desktop", 1440, RAIL_COLLAPSED)).toBe("inline");
    // 900 − 64 = 836 < 900
    expect(coachMode("desktop", 900, RAIL_COLLAPSED)).toBe("drawer");
  });

  it("boundary: contentWidth === 900 → inline", () => {
    // viewport = 900 + 64 = 964
    expect(coachMode("ipad", 964, RAIL_COLLAPSED)).toBe("inline");
  });
});
