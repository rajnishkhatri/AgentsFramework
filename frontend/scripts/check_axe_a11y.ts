/**
 * check_axe_a11y.ts — Frontend Reviewer tool (FD4.AXE) — STUB.
 *
 * The full implementation requires `@axe-core/playwright` + a Storybook
 * host (`.storybook/` + `npm run storybook`). Per the user's pragmatic
 * decision (D-V3-S4.x — dynamic a11y deferred until Storybook lands),
 * this script ships in stub mode:
 *
 *   - If the toolchain is missing, emit
 *       { pass: true, skipped: true, reason, missing: [...] }
 *     and exit 0 so CI does not block.
 *   - If the toolchain IS installed (devDependency present AND
 *     `.storybook/` exists), the placeholder code path documents what
 *     the full implementation will do via a `// TODO` and an
 *     `assert(false, ...)` so the gap is visible the moment the
 *     prerequisites land.
 *
 * Output JSON conforms to §5 of the Frontend Reviewer system prompt.
 *
 * Exit codes: 0 on PASS or skipped, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_axe_a11y.ts [target]`
 */

import * as path from "node:path";
import * as fs from "node:fs";
import { strict as assert } from "node:assert";

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

function toolchainStatus(): { ready: boolean; missing: string[] } {
  const missing: string[] = [];
  const pkgPath = path.join(FRONTEND_ROOT, "package.json");
  let pkg: { devDependencies?: Record<string, string>; scripts?: Record<string, string> } = {};
  if (fs.existsSync(pkgPath)) {
    pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  }
  if (!pkg.devDependencies?.["@axe-core/playwright"]) {
    missing.push("@axe-core/playwright");
  }
  if (!fs.existsSync(path.join(FRONTEND_ROOT, ".storybook"))) {
    missing.push(".storybook/");
  }
  if (!pkg.scripts?.storybook) {
    missing.push("storybook script in package.json");
  }
  return { ready: missing.length === 0, missing };
}

/**
 * Public entrypoint. Returns the schema-shaped result and never throws.
 *
 * @param target  Storybook story id or rendered route URL.
 */
export function checkAxeA11y(target: string = "all"): CheckResult {
  const { ready, missing } = toolchainStatus();
  if (!ready) {
    return {
      pass: true,
      target,
      skipped: true,
      reason: "axe-core toolchain not installed",
      missing,
      violations: [],
      incomplete: [],
    };
  }

  // TODO: when @axe-core/playwright + .storybook/ ship, replace this
  // assertion with the real Playwright + AxeBuilder loop. Until then we
  // surface the gap explicitly so a misconfigured-but-installed setup
  // doesn't silently report a green check.
  assert(false, "axe-core toolchain installed but check_axe_a11y full implementation pending");
  return {
    pass: false,
    target,
    skipped: false,
    reason: "unreachable",
    missing: [],
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
