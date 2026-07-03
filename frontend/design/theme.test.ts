/**
 * Phase 0.2 — FR-A1/A2/A4/A5 base tokens are normative (L1 deterministic, TAP-1).
 *
 * Companion to tokens.test.ts (FR-A3 bucket accents). This locks the *base*
 * design system — the warm cream/charcoal/terracotta palette (light + dark),
 * the type scale + line-heights, and the radii — against drift. The spec
 * (docs/plan/preact-english-coach-ui.spec.md §3.A) declares these tokens
 * "normative … requirements, not suggestions"; this test is the guard that
 * makes that word enforceable.
 *
 * Behavioral spec, not algorithm mirror (Anti-Pattern 1 avoided): we run the
 * real `pnpm tokens:build` and assert the observable artifact the app consumes
 * — `app/generated-theme.css` — resolves each token to its spec value in the
 * light `@theme` block and (for FR-A2) the dark `[data-theme="dark"]` block.
 * A reimplementation of the build that still emits the correct CSS stays green.
 *
 * Spec: docs/plan/preact-english-coach-ui.spec.md §3.A FR-A1, FR-A2, FR-A4, FR-A5.
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
 * FR-A1: light base palette. `muted`/`accent`/`success` were darkened in the
 * Phase-4 a11y pass (FR-K2) so muted-on-bg, accent-on-bg, and white-on-accent
 * text all clear WCAG-AA 4.5:1 (hues preserved); `accent` was darkened once
 * more (#a75c44 → #93513d) so accent text also clears 4.5:1 on its own
 * `--color-accent-light` tint (~#ede0da — the soft feedback banner surface the
 * axe sweep measures). `bg`/`fg`/`danger`/`warning` already passed and are
 * unchanged; the dark palette is unchanged.
 */
const LIGHT_BASE: ReadonlyArray<readonly [cssVar: string, value: string]> = [
  ["--color-bg", "#f9f7f5"],
  ["--color-fg", "#1f1e1d"],
  ["--color-muted", "#666460"],
  ["--color-accent", "#93513d"],
  ["--color-danger", "#c0392b"],
  ["--color-success", "#2a7f51"],
  ["--color-warning", "#a9741f"],
  // On-fill text (Phase-4 a11y): white clears AA on every LIGHT fill …
  ["--color-on-accent", "#ffffff"],
  ["--color-on-success", "#ffffff"],
  ["--color-on-danger", "#ffffff"],
];

/** FR-A2: dark base palette, verbatim from the spec §3.A. */
const DARK_BASE: ReadonlyArray<readonly [cssVar: string, value: string]> = [
  ["--color-bg", "#241c15"],
  ["--color-fg", "#f9f7f5"],
  ["--color-accent", "#e5967c"],
  ["--color-danger", "#e57368"],
  ["--color-success", "#5cba86"],
  ["--color-warning", "#e3b357"],
  ["--color-surface", "#322a24"],
  ["--color-surface-sunken", "#3f3831"],
  // … but the dark-tuned fills are LIGHT (lifted-L coral/green/red), so white
  // text fails AA on them (2.3–3.0:1); on-fill text flips to the dark bg hex
  // (5.6–7.2:1). The dark axe sweep in e2e/learn/a11y.spec.ts is the oracle.
  ["--color-on-accent", "#241c15"],
  ["--color-on-success", "#241c15"],
  ["--color-on-danger", "#241c15"],
];

/** FR-A4: type scale sizes, verbatim from the spec §3.A. */
const TYPE_SCALE: ReadonlyArray<readonly [cssVar: string, value: string]> = [
  ["--text-sm", "1rem"],
  ["--text-base", "1.125rem"],
  ["--text-lg", "1.25rem"],
  ["--text-xl", "1.5rem"],
  ["--text-2xl", "1.75rem"],
];

/** FR-A4: the answer/body line-height is 1.6 (the one line-height the spec names). */
const BASE_LINE_HEIGHT: readonly [cssVar: string, value: string] = [
  "--text-base--line-height",
  "1.6",
];

/** FR-A5: radii sm 10px / md 16px / lg 22px, expressed in rem in the token source. */
const RADII: ReadonlyArray<readonly [cssVar: string, value: string]> = [
  ["--radius-sm", "0.625rem"], // 10px
  ["--radius-md", "1rem"], // 16px
  ["--radius-lg", "1.375rem"], // 22px
];

let lightBlock = "";
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
  const css = readFileSync(GENERATED_CSS, "utf8");
  lightBlock = extractBlock(css, "@theme");
  darkBlock = extractBlock(css, '[data-theme="dark"]');
});

describe("FR-A1 light_base_palette_normative", () => {
  it("generates a non-empty light @theme block", () => {
    expect(lightBlock.length).toBeGreaterThan(0);
  });

  it.each(LIGHT_BASE)("%s resolves to %s in @theme", (cssVar, value) => {
    expect(lightBlock).toContain(`${cssVar}: ${value};`);
  });
});

describe("FR-A2 dark_base_palette_normative", () => {
  it("generates a non-empty dark [data-theme=dark] block", () => {
    expect(darkBlock.length).toBeGreaterThan(0);
  });

  it.each(DARK_BASE)("%s resolves to %s in [data-theme=dark]", (cssVar, value) => {
    expect(darkBlock).toContain(`${cssVar}: ${value};`);
  });
});

describe("FR-A4 type_scale_normative", () => {
  it.each(TYPE_SCALE)("%s resolves to %s in @theme", (cssVar, value) => {
    expect(lightBlock).toContain(`${cssVar}: ${value};`);
  });

  it("the answer/body line-height is 1.6", () => {
    const [cssVar, value] = BASE_LINE_HEIGHT;
    expect(lightBlock).toContain(`${cssVar}: ${value};`);
  });
});

describe("FR-A5 radii_normative", () => {
  it.each(RADII)("%s resolves to %s (spec px) in @theme", (cssVar, value) => {
    expect(lightBlock).toContain(`${cssVar}: ${value};`);
  });
});
