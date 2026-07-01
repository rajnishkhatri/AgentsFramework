/**
 * check_axe_a11y.ts — Frontend Reviewer tool (FD4.AXE) — STATIC checker.
 *
 * The static counterpart to the dynamic `e2e/accessibility.spec.ts`
 * (which runs `@axe-core/playwright` against live routes). Now that the
 * Storybook host (`.storybook/`), the `@storybook/addon-a11y` addon, and
 * the `*.stories.tsx` files have all landed (PS1), this checker verifies
 * the a11y toolchain is *wired* rather than merely installed:
 *
 *   - the Storybook a11y addon is listed in `.storybook/main.ts`, and
 *   - at least one `*.stories.tsx` exists for the addon's axe pass to cover.
 *
 * (The earlier stub emitted `{ skipped: true }` while the host was absent
 * and carried an `assert(false)` tripwire to force this replacement the
 * moment the prerequisites arrived. Both are now retired.)
 *
 * Output JSON conforms to §5 of the Frontend Reviewer system prompt.
 *
 * Exit codes: 0 on PASS, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_axe_a11y.ts [target]`
 */

import * as path from "node:path";
import * as fs from "node:fs";

interface CheckResult {
  pass: boolean;
  target: string;
  skipped: boolean;
  reason: string;
  missing: string[];
  violations: Array<{ rule_id: string; impact: string; nodes: Array<{ selector: string; html: string }> }>;
  incomplete: Array<{ rule_id: string; reason: string }>;
}

const SCRIPT_DIR = (import.meta as { dirname?: string }).dirname ?? __dirname;
const FRONTEND_ROOT = path.resolve(SCRIPT_DIR, "..");

/** The Storybook a11y addon whose presence proves the axe pass is wired. */
const A11Y_ADDON = "@storybook/addon-a11y";

/** Pure readiness verdict over already-read facts (unit-testable, no I/O). */
export interface AxeReadinessInput {
  addons: string[];
  storyCount: number;
}

export interface AxeReadinessResult {
  pass: boolean;
  skipped: boolean;
  reason: string;
  missing: string[];
}

/**
 * Static readiness verdict: the a11y addon must be wired AND stories must
 * exist for the addon's axe pass to have anything to cover. Pure — the
 * caller supplies the facts (addons list, story count).
 */
export function staticAxeReadiness(input: AxeReadinessInput): AxeReadinessResult {
  const missing: string[] = [];
  if (!input.addons.includes(A11Y_ADDON)) missing.push(A11Y_ADDON);
  if (input.storyCount === 0) missing.push("*.stories.tsx");

  if (!input.addons.includes(A11Y_ADDON)) {
    return { pass: false, skipped: false, reason: `${A11Y_ADDON} not wired in .storybook/main.ts`, missing };
  }
  if (input.storyCount === 0) {
    return { pass: false, skipped: false, reason: "no stories for the axe pass to cover", missing };
  }
  return {
    pass: true,
    skipped: false,
    reason: `axe a11y wired: ${A11Y_ADDON} + ${input.storyCount} stories`,
    missing: [],
  };
}

/** Read the addon list declared in `.storybook/main.ts` (best-effort string scan). */
function readStorybookAddons(): string[] {
  const mainPath = path.join(FRONTEND_ROOT, ".storybook", "main.ts");
  if (!fs.existsSync(mainPath)) return [];
  const src = fs.readFileSync(mainPath, "utf8");
  const addons: string[] = [];
  for (const m of src.matchAll(/["']@storybook\/addon-[a-z0-9-]+["']/g)) {
    addons.push(m[0].slice(1, -1));
  }
  return addons;
}

/** Count `*.stories.tsx|ts` files under `components/` (the main.ts stories glob). */
function countStories(): number {
  const root = path.join(FRONTEND_ROOT, "components");
  if (!fs.existsSync(root)) return 0;
  let count = 0;
  const walk = (dir: string): void => {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) walk(full);
      else if (/\.stories\.(tsx|ts)$/.test(ent.name)) count += 1;
    }
  };
  walk(root);
  return count;
}

/**
 * Public entrypoint. Returns the schema-shaped result and never throws.
 *
 * @param target  Storybook story id or rendered route URL.
 */
export function checkAxeA11y(target: string = "all"): CheckResult {
  const readiness = staticAxeReadiness({
    addons: readStorybookAddons(),
    storyCount: countStories(),
  });
  return {
    pass: readiness.pass,
    target,
    skipped: readiness.skipped,
    reason: readiness.reason,
    missing: readiness.missing,
    violations: [],
    incomplete: [],
  };
}

function main(argv: string[]): number {
  const target = argv[2] ?? "all";
  try {
    const result = checkAxeA11y(target);
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    if (result.skipped) return 0;
    return result.pass ? 0 : 1;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    process.stdout.write(
      JSON.stringify({
        pass: false,
        target,
        skipped: false,
        reason: msg,
        missing: [],
        violations: [],
        incomplete: [],
      }) + "\n",
    );
    return 2;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
