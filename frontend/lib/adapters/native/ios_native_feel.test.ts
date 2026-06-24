/**
 * Tests for the pure iOS native-feel helper (P6 Step 3).
 *
 * L2 / Reproducible Reality: deterministic decision logic only — what status-bar
 * style a theme maps to, what keyboard-offset CSS a height implies, and whether a
 * theme string is one we recognise. No SDK, no DOM. Failure / edge paths first
 * (anti-Gap-Blindness): unknown theme, missing theme, zero/garbage keyboard
 * height.
 *
 * Plan: docs/plans/p6_capacitor_ios_shell.plan.md (Step 3)
 */

import { describe, it, expect } from "vitest";
import {
  statusBarStyleForTheme,
  keyboardOffsetPx,
  KEYBOARD_OFFSET_VAR,
} from "./ios_native_feel";

describe("statusBarStyleForTheme — failure / edge paths first", () => {
  it('returns "Default" (light glyphs) for an unknown theme string', () => {
    // A theme we don't recognise must not crash and must not pick a style that
    // could make the status bar invisible — fall back to the light-content
    // default rather than guessing.
    expect(statusBarStyleForTheme("solarized")).toBe("Default");
  });

  it('returns "Default" when the theme is null/undefined (not yet resolved)', () => {
    expect(statusBarStyleForTheme(null)).toBe("Default");
    expect(statusBarStyleForTheme(undefined)).toBe("Default");
  });

  it("is case-insensitive for the resolved theme", () => {
    expect(statusBarStyleForTheme("DARK")).toBe("Dark");
    expect(statusBarStyleForTheme("Light")).toBe("Light");
  });
});

describe("statusBarStyleForTheme — happy path", () => {
  it('maps "dark" theme → "Dark" (light text on the dark app bar)', () => {
    // Capacitor StatusBar Style.Dark = light text, used over a dark background.
    expect(statusBarStyleForTheme("dark")).toBe("Dark");
  });

  it('maps "light" theme → "Light" (dark text on the light app bar)', () => {
    expect(statusBarStyleForTheme("light")).toBe("Light");
  });
});

describe("keyboardOffsetPx — failure / edge paths first", () => {
  it("clamps a negative height to 0 (no negative padding)", () => {
    expect(keyboardOffsetPx(-50)).toBe(0);
  });

  it("returns 0 for NaN / non-finite height (garbage event payload)", () => {
    expect(keyboardOffsetPx(Number.NaN)).toBe(0);
    expect(keyboardOffsetPx(Number.POSITIVE_INFINITY)).toBe(0);
  });

  it("returns 0 when the keyboard is hidden (height 0)", () => {
    expect(keyboardOffsetPx(0)).toBe(0);
  });
});

describe("keyboardOffsetPx — happy path", () => {
  it("returns the rounded integer keyboard height for a shown keyboard", () => {
    expect(keyboardOffsetPx(336)).toBe(336);
    expect(keyboardOffsetPx(291.4)).toBe(291);
  });
});

describe("KEYBOARD_OFFSET_VAR", () => {
  it("is the custom property the layout consumes for composer lift", () => {
    // Locks the contract with globals.css (the var name must match the CSS that
    // reads it), so a rename can't silently break the keyboard lift.
    expect(KEYBOARD_OFFSET_VAR).toBe("--keyboard-offset");
  });
});
