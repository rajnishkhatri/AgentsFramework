/**
 * check_bundle_budget.ts — Frontend Reviewer tool (FD5.BUDGET) — STUB.
 *
 * The full implementation requires `@next/bundle-analyzer` +
 * `frontend/.bundle-baseline.json`. Until both ship the script returns
 * `{ pass: true, skipped: true, ... }` so CI does not block (the FD5.BUDGET
 * hypothesis is recorded as a `gaps[]` entry by the reviewer).
 *
 * When the prerequisites ARE present, the implementation reads
 * `.next/analyze/*.json` and compares each route's First Load JS to the
 * committed baseline; routes whose `delta_pct > 10` fail.
 *
 * Output JSON conforms to §5 of the Frontend Reviewer system prompt.
 *
 * Exit codes: 0 on PASS or skipped, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_bundle_budget.ts [route]`
 */

import * as path from "node:path";
import * as fs from "node:fs";

interface RouteDelta {
  route: string;
  delta_pct: number;
}

interface CheckResult {
  pass: boolean;
  route: string;
  skipped: boolean;
  reason?: string;
  missing?: string[];
  first_load_kb?: number;
  baseline_kb?: number;
  delta_pct?: number;
  violations: RouteDelta[];
  error?: string;
}

const SCRIPT_DIR = (import.meta as { dirname?: string }).dirname ?? __dirname;
const FRONTEND_ROOT = path.resolve(SCRIPT_DIR, "..");
const BASELINE = path.join(FRONTEND_ROOT, ".bundle-baseline.json");
const ANALYZE_DIR = path.join(FRONTEND_ROOT, ".next", "analyze");
const PCT_THRESHOLD = 10;

function toolchainStatus(): { ready: boolean; missing: string[] } {
  const missing: string[] = [];
  const pkgPath = path.join(FRONTEND_ROOT, "package.json");
  let pkg: { devDependencies?: Record<string, string> } = {};
  if (fs.existsSync(pkgPath)) {
    pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  }
  if (!pkg.devDependencies?.["@next/bundle-analyzer"]) {
    missing.push("@next/bundle-analyzer");
  }
  if (!fs.existsSync(BASELINE)) {
    missing.push("frontend/.bundle-baseline.json");
  }
  return { ready: missing.length === 0, missing };
}

function readAnalyzedRoutes(): Record<string, number> {
  if (!fs.existsSync(ANALYZE_DIR)) return {};
  const out: Record<string, number> = {};
  for (const entry of fs.readdirSync(ANALYZE_DIR)) {
    if (!entry.endsWith(".json")) continue;
    const file = path.join(ANALYZE_DIR, entry);
    try {
      const data = JSON.parse(fs.readFileSync(file, "utf8")) as Record<string, number>;
      for (const [route, kb] of Object.entries(data)) {
        out[route] = Number(kb);
      }
    } catch {
      // ignore malformed analyze output; the bundle-analyzer pipeline
      // is responsible for shape conformance.
    }
  }
  return out;
}

/**
 * Public entrypoint. Returns the schema-shaped result and never throws.
 *
 * @param route  Route to check (or `"all"` to evaluate every route).
 */
export function checkBundleBudget(route: string = "all"): CheckResult {
  const { ready, missing } = toolchainStatus();
  if (!ready) {
    return {
      pass: true,
      route,
      skipped: true,
      reason: "bundle baseline not committed",
      missing,
      violations: [],
    };
  }

  let baseline: Record<string, number>;
  try {
    baseline = JSON.parse(fs.readFileSync(BASELINE, "utf8")) as Record<string, number>;
  } catch (e) {
    return {
      pass: false,
      route,
      skipped: false,
      reason: "failed to parse baseline",
      violations: [],
      error: e instanceof Error ? e.message : String(e),
    };
  }

  const live = readAnalyzedRoutes();
  const violations: RouteDelta[] = [];
  for (const [r, baseKb] of Object.entries(baseline)) {
    if (route !== "all" && route !== r) continue;
    const liveKb = live[r];
    if (liveKb === undefined) continue;
    const delta = baseKb === 0 ? 0 : ((liveKb - baseKb) / baseKb) * 100;
    if (delta > PCT_THRESHOLD) violations.push({ route: r, delta_pct: Number(delta.toFixed(2)) });
  }
  const targetBase = baseline[route];
  const targetLive = live[route];
  const result: CheckResult = {
    pass: violations.length === 0,
    route,
    skipped: false,
    violations,
  };
  if (typeof targetLive === "number") result.first_load_kb = targetLive;
  if (typeof targetBase === "number") result.baseline_kb = targetBase;
  if (
    typeof targetBase === "number" &&
    typeof targetLive === "number" &&
    targetBase !== 0
  ) {
    result.delta_pct = Number((((targetLive - targetBase) / targetBase) * 100).toFixed(2));
  }
  return result;
}

function main(argv: string[]): number {
  const route = argv[2] ?? "all";
  const result = checkBundleBudget(route);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  if (result.error) return 2;
  if (result.skipped) return 0;
  return result.pass ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
