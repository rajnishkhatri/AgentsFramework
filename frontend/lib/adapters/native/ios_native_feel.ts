/**
 * Pure iOS native-feel helper (P6 Step 3) — SDK-free decision logic.
 *
 * Architecture: this file holds the deterministic LOGIC the native-feel
 * controller needs — map the resolved theme to a Capacitor status-bar style,
 * and turn a keyboard-height event into a clamped pixel offset. No SDK, no DOM,
 * so it is trivially unit-testable (the Capacitor boundary lives in the sibling
 * `capacitor_native_feel.ts`). Analogue of `ios_deep_link_auth.ts` for Step 2.
 *
 * Plan: docs/plans/p6_capacitor_ios_shell.plan.md (Step 3)
 */

/**
 * Capacitor `StatusBar` style names (Style enum keys). "Dark" = light glyphs
 * (used over a dark bar), "Light" = dark glyphs (over a light bar), "Default" =
 * the OS default (light content) used as the safe fallback.
 */
export type StatusBarStyleName = "Dark" | "Light" | "Default";

/**
 * The custom property the layout reads to lift the composer above the on-screen
 * keyboard. The controller writes it on keyboard show/hide; globals.css consumes
 * it as bottom padding. Locked by a test so a rename can't silently break lift.
 */
export const KEYBOARD_OFFSET_VAR = "--keyboard-offset";

/**
 * Map a resolved theme string to the status-bar style that keeps the glyphs
 * legible. Case-insensitive; any unrecognised / missing theme falls back to the
 * OS default (light content) rather than guessing a style that could hide the
 * status bar.
 */
export function statusBarStyleForTheme(
  theme: string | null | undefined,
): StatusBarStyleName {
  switch ((theme ?? "").toLowerCase()) {
    case "dark":
      return "Dark";
    case "light":
      return "Light";
    default:
      return "Default";
  }
}

/**
 * Turn a raw keyboard height (from the native keyboard-show event) into a safe
 * integer pixel offset: non-finite / negative heights collapse to 0 (no
 * negative or NaN padding), otherwise the height is rounded to a whole pixel.
 */
export function keyboardOffsetPx(height: number): number {
  if (!Number.isFinite(height) || height <= 0) return 0;
  return Math.round(height);
}
