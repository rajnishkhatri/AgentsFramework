/**
 * test_scoring — pure raw→scale-band lookup for the English section (Test-01).
 *
 * Test-01's scoring guide (embedded official PreACT tables) converts a raw
 * correct count to a scale-score BAND, not one number:
 *   raw correct → percent → × official English max raw (33) → equivalent raw →
 *   look up the scale range.
 *
 * This is a pure function so the Results view renders a faithful, node-testable
 * band. The table is the abbreviated English lookup from Test-01.md's SCORING
 * GUIDE (interpolate to the nearest lower row, ACT-style). Import: stdlib only.
 */

/** English equivalent-raw (/33) → scale band, from Test-01's official table. */
const ENGLISH_SCALE: ReadonlyArray<readonly [number, string]> = [
  [5, "3–7"],
  [8, "6–10"],
  [11, "8–12"],
  [13, "9–13"],
  [15, "11–15"],
  [18, "13–17"],
  [21, "16–20"],
  [23, "18–22"],
  [25, "19–23"],
  [28, "22–28"],
  [30, "25–31"],
  [33, "32–32"],
];

/** The official English max raw the percent is scaled onto (Test-01 §Step 1). */
export const ENGLISH_MAX_RAW = 33;

/**
 * Convert a raw score (correct / total answered-out-of-section) to a scale band.
 * Returns null for a zero-length section (no band to show).
 */
export function englishScaleBand(correct: number, total: number): string | null {
  if (total <= 0) return null;
  const pct = correct / total;
  const equivalentRaw = Math.round(pct * ENGLISH_MAX_RAW);
  // Nearest table row at or below the equivalent raw (floor to a defined row).
  let band = ENGLISH_SCALE[0]![1];
  for (const [raw, range] of ENGLISH_SCALE) {
    if (equivalentRaw >= raw) band = range;
    else break;
  }
  return band;
}
