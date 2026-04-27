/**
 * Vitest sibling for `check_csp_strict.ts`.
 *
 * Failure paths first (FD6.ADAPTER): the rejection fixtures cover the three
 * documented violation classes (CSP1 unsafe-inline, CSP2 missing nonce,
 * hardening miss) BEFORE the canonical `frontend/middleware.ts` PASS.
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import * as os from "node:os";
import { checkCspStrict, evaluateCsp, parseCspDirectives } from "./check_csp_strict";

const TEST_DIR = (import.meta as { dirname?: string }).dirname ?? __dirname;
const FRONTEND_ROOT = path.resolve(TEST_DIR, "..");

function tmpFile(contents: string, ext = ".ts"): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "csp-test-"));
  const file = path.join(dir, `middleware${ext}`);
  fs.writeFileSync(file, contents, "utf8");
  return file;
}

describe("check_csp_strict — rejection fixtures (failure paths first)", () => {
  it("FAILS when 'unsafe-inline' appears in script-src (CSP1 / FE-AP-19)", () => {
    const fp = tmpFile(`
function buildCSP(nonce: string): string {
  return [
    \`default-src 'self'\`,
    \`script-src 'self' 'unsafe-inline' 'nonce-\${nonce}' 'strict-dynamic'\`,
    \`style-src 'self' 'nonce-\${nonce}'\`,
    \`object-src 'none'\`,
    \`base-uri 'self'\`,
    \`frame-ancestors 'none'\`,
  ].join("; ");
}
export {};
`);
    const result = checkCspStrict(fp);
    expect(result.pass).toBe(false);
    const csp1 = result.violations.find((v) => v.rule === "CSP1" && v.directive === "script-src");
    expect(csp1, "expected CSP1 violation on script-src").toBeTruthy();
  });

  it("FAILS when script-src is missing 'strict-dynamic' (CSP2)", () => {
    const fp = tmpFile(`
function buildCSP(nonce: string): string {
  return [
    \`default-src 'self'\`,
    \`script-src 'self' 'nonce-\${nonce}'\`,
    \`style-src 'self' 'nonce-\${nonce}'\`,
    \`object-src 'none'\`,
    \`base-uri 'self'\`,
    \`frame-ancestors 'none'\`,
  ].join("; ");
}
export {};
`);
    const result = checkCspStrict(fp);
    expect(result.pass).toBe(false);
    const csp2 = result.violations.find(
      (v) => v.rule === "CSP2" && v.description.includes("strict-dynamic"),
    );
    expect(csp2).toBeTruthy();
  });

  it("FAILS when frame-ancestors is missing entirely (HARD)", () => {
    const fp = tmpFile(`
function buildCSP(nonce: string): string {
  return [
    \`default-src 'self'\`,
    \`script-src 'self' 'nonce-\${nonce}' 'strict-dynamic'\`,
    \`style-src 'self' 'nonce-\${nonce}'\`,
    \`object-src 'none'\`,
    \`base-uri 'self'\`,
  ].join("; ");
}
export {};
`);
    const result = checkCspStrict(fp);
    expect(result.pass).toBe(false);
    const hard = result.violations.find((v) => v.directive === "frame-ancestors");
    expect(hard).toBeTruthy();
  });

  it("returns CSP_NOT_FOUND when no CSP grammar is present", () => {
    const fp = tmpFile(`export function middleware() { return null; }\n`);
    const result = checkCspStrict(fp);
    expect(result.pass).toBe(false);
    expect(result.violations[0]?.rule).toBe("CSP_NOT_FOUND");
  });
});

describe("check_csp_strict — pass fixture against the canonical middleware", () => {
  it("PASSES on frontend/middleware.ts as committed", () => {
    const fp = path.join(FRONTEND_ROOT, "middleware.ts");
    const result = checkCspStrict(fp);
    if (!result.pass) {
      // Surface the exact violations to the test log so a regression in
      // middleware.ts is debuggable from CI alone.
      throw new Error(
        `Expected canonical middleware to pass: ${JSON.stringify(result, null, 2)}`,
      );
    }
    expect(result.pass).toBe(true);
    expect(result.csp).toContain("script-src");
  });
});

describe("evaluateCsp / parseCspDirectives — unit-level coverage", () => {
  it("parses a simple CSP into directive -> sources", () => {
    const csp = "default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic'";
    const map = parseCspDirectives(csp);
    expect(map.get("default-src")).toEqual(["'self'"]);
    expect(map.get("script-src")).toEqual(["'self'", "'nonce-${nonce}'", "'strict-dynamic'"]);
  });

  it("flags 'unsafe-eval' identically to 'unsafe-inline' (CSP1)", () => {
    const csp =
      "default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic' 'unsafe-eval'; style-src 'self' 'nonce-${nonce}'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";
    const violations = evaluateCsp(parseCspDirectives(csp));
    expect(violations.some((v) => v.description.includes("'unsafe-eval'"))).toBe(true);
  });
});
