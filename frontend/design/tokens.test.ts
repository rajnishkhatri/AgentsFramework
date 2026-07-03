/**
 * Phase 0.1 — FR-A3 six bucket accents (L1 deterministic, TAP-1).
 *
 * Behavioral spec, not algorithm mirror (Anti-Pattern 1 avoided): we run the
 * real `pnpm tokens:build` and assert the observable artifact the app consumes
 * — `app/generated-theme.css` — resolves all six bucket accents to their
 * spec hex values in BOTH the light `@theme` block and the dark
 * `[data-theme="dark"]` block. A reimplementation of the build that still emits
 * the correct CSS keeps this test green.
 *
 * Spec: docs/plan/preact-english-coach-ui.spec.md §3.A FR-A3.
 */

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeAll, describe, expect, it } from "vitest";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.join(HERE, "..");
const GENERATED_CSS = path.join(FRONTEND_ROOT, "app", "generated-theme.css");
const BUILD_SCRIPT = path.join(HERE, "style-dictionary.config.mjs");

/**
 * FR-A3: the six bucket accents (light / dark), verbatim from the token source.
 *
 * The light hexes were darkened in the Phase-4 a11y pass (FR-K2) so each accent
 * clears WCAG-AA 4.5:1 both as text-on-bg and as white-on-fill; the hues are
 * preserved and the six remain visually distinct. The dark hexes are unchanged
 * (they already clear AA against the dark bg — see e2e/learn/a11y.spec.ts).
 */
const BUCKET_ACCENTS: ReadonlyArray<readonly [bucket: string, light: string, dark: string]> = [
  ["rhetoric", "#a75c44", "#e5967c"],
  ["usage", "#94672d", "#d6a45a"],
  ["punctuation", "#3e7b6d", "#6bbfa9"],
  ["organization", "#627741", "#9bb56e"],
  ["sentence-structure", "#537397", "#84a6cc"],
  ["conciseness", "#926086", "#c08fb4"],
];

let css = "";
/** The `@theme { ... }` (light) block. */
let lightBlock = "";
/** The `[data-theme="dark"] { ... }` (dark) block. */
let darkBlock = "";

function extractBlock(source: string, opener: string): string {
  const start = source.indexOf(opener);
  if (start === -1) return "";
  const braceStart = source.indexOf("{", start);
  const braceEnd = source.indexOf("}", braceStart);
  return source.slice(braceStart + 1, braceEnd);
}

beforeAll(() => {
  // Regenerate from the token JSON so the test reflects the current source,
  // not a stale committed artifact.
  execFileSync("node", [BUILD_SCRIPT], { cwd: FRONTEND_ROOT, stdio: "pipe" });
  css = readFileSync(GENERATED_CSS, "utf8");
  lightBlock = extractBlock(css, "@theme");
  darkBlock = extractBlock(css, '[data-theme="dark"]');
});

describe("FR-A3 six_bucket_accents_present_both_themes", () => {
  it("generates a non-empty light and dark theme block", () => {
    expect(lightBlock.length).toBeGreaterThan(0);
    expect(darkBlock.length).toBeGreaterThan(0);
  });

  it.each(BUCKET_ACCENTS)(
    "--color-bucket-%s resolves to its light hex in @theme",
    (bucket, light) => {
      expect(lightBlock).toContain(`--color-bucket-${bucket}: ${light};`);
    },
  );

  it.each(BUCKET_ACCENTS)(
    "--color-bucket-%s resolves to its dark hex in [data-theme=dark]",
    (bucket, _light, dark) => {
      expect(darkBlock).toContain(`--color-bucket-${bucket}: ${dark};`);
    },
  );

  it("defines exactly six bucket accents in each theme (no extras, no gaps)", () => {
    const countBuckets = (block: string) =>
      (block.match(/--color-bucket-[a-z-]+:/g) ?? []).length;
    expect(countBuckets(lightBlock)).toBe(6);
    expect(countBuckets(darkBlock)).toBe(6);
  });
});
