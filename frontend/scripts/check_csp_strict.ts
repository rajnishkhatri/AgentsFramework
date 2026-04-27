/**
 * check_csp_strict.ts — Frontend Reviewer tool (FD3.CSP1 / FD3.CSP2 / FE-AP-19).
 *
 * Parses the Content-Security-Policy header string out of a Next.js edge
 * middleware file (e.g. `frontend/middleware.ts`) and asserts the strict-CSP
 * contract from `prompts/codeReviewer/frontend/architecture_rules.j2`:
 *
 *   CSP1   No `'unsafe-inline'` or `'unsafe-eval'` anywhere.
 *   CSP2   `script-src` includes `nonce-${nonce}` AND `'strict-dynamic'`;
 *          `style-src` includes `nonce-${nonce}`.
 *   HARD   `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`.
 *
 * Discovery: ts-morph walks the source AST looking for either
 *   (a) a function literally named `buildCSP` whose body returns the CSP
 *       string (the canonical pattern in `frontend/middleware.ts`), or
 *   (b) any string concatenation / template literal that contains the
 *       directives `default-src` and `script-src` (defensive fallback for
 *       hand-rolled middleware).
 *
 * Output JSON conforms to the `check_csp_strict` schema in §5 of the
 * Frontend Reviewer system prompt:
 *   {
 *     "pass": bool,
 *     "file": str,
 *     "csp": str,
 *     "violations": [{"rule": str, "directive": str, "description": str}]
 *   }
 *
 * Exit codes: 0 on PASS, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_csp_strict.ts <middleware_filepath>`
 */

import * as path from "node:path";
import * as fs from "node:fs";
import { Project, SyntaxKind, type SourceFile } from "ts-morph";

interface Violation {
  rule: string;
  directive: string;
  description: string;
}

interface CheckResult {
  pass: boolean;
  file: string;
  csp: string | null;
  violations: Violation[];
  error?: string;
}

const FORBIDDEN_TOKENS = ["'unsafe-inline'", "'unsafe-eval'"];

/**
 * Extract a CSP string from the source file. Returns the raw string with
 * any `${nonce}` interpolations preserved verbatim so the directive checks
 * can match against the literal token `'nonce-${nonce}'`.
 *
 * Walks the AST (NOT a regex over the text) so JS comments inside the
 * `buildCSP` array body do not leak into the CSP value.
 *
 * @param sf  ts-morph SourceFile loaded from disk.
 * @returns The CSP string, or null when no candidate could be located.
 */
export function extractCspString(sf: SourceFile): string | null {
  // Strategy A: walk every ArrayLiteralExpression and join its element
  // texts (after un-quoting). The reviewer's canonical middleware writes
  // CSP as `[ ` ... ` ].join("; ")`. AST-based extraction skips comment
  // trivia automatically.
  for (const arr of sf.getDescendantsOfKind(SyntaxKind.ArrayLiteralExpression)) {
    const elements = arr.getElements();
    const tokens: string[] = [];
    for (const el of elements) {
      const txt = stripQuotes(el.getText());
      tokens.push(txt);
    }
    const joined = tokens.join("; ");
    if (joined.includes("default-src") && joined.includes("script-src")) {
      return joined;
    }
  }

  // Strategy B: a single template literal returned directly from a
  // function (rare but valid) — match against the largest such literal.
  let best: string | null = null;
  for (const node of sf.getDescendants()) {
    const k = node.getKind();
    if (
      k === SyntaxKind.TemplateExpression ||
      k === SyntaxKind.NoSubstitutionTemplateLiteral ||
      k === SyntaxKind.StringLiteral
    ) {
      const txt = stripQuotes(node.getText());
      if (txt.includes("default-src") && txt.includes("script-src")) {
        if (!best || txt.length > best.length) best = txt;
      }
    }
  }
  return best;
}

function stripQuotes(s: string): string {
  const trimmed = s.trim();
  if (
    (trimmed.startsWith("`") && trimmed.endsWith("`")) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'")) ||
    (trimmed.startsWith('"') && trimmed.endsWith('"'))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

/**
 * Parse a CSP string into a directive map. Splits on `;` and treats the
 * first whitespace-separated token of each segment as the directive name.
 *
 * @param csp  Raw CSP header string (may contain `${...}` placeholders).
 * @returns Map of directive name -> ordered token array (sources only).
 */
export function parseCspDirectives(csp: string): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const segment of csp.split(";")) {
    const trimmed = segment.trim();
    if (!trimmed) continue;
    const tokens = trimmed.split(/\s+/);
    const name = tokens[0]?.toLowerCase();
    if (!name) continue;
    out.set(name, tokens.slice(1));
  }
  return out;
}

/**
 * Apply the CSP1 / CSP2 / hardening rules to a parsed directive map.
 *
 * @param directives  Output of {@link parseCspDirectives}.
 * @returns A list of violations (empty when the CSP is fully compliant).
 */
export function evaluateCsp(directives: Map<string, string[]>): Violation[] {
  const violations: Violation[] = [];

  for (const [name, sources] of directives) {
    for (const src of sources) {
      if (FORBIDDEN_TOKENS.includes(src)) {
        violations.push({
          rule: "CSP1",
          directive: name,
          description: `${name} contains forbidden token ${src}; remove it (FE-AP-19).`,
        });
      }
    }
  }

  const scriptSrc = directives.get("script-src") ?? [];
  const styleSrc = directives.get("style-src") ?? [];

  if (!scriptSrc.some((s) => /^'?nonce-\$\{[^}]*\}'?$/.test(s) || s.startsWith("'nonce-"))) {
    violations.push({
      rule: "CSP2",
      directive: "script-src",
      description:
        "script-src is missing a per-request `nonce-${nonce}` source; without it inline bootstrap scripts cannot execute under strict-dynamic.",
    });
  }
  if (!scriptSrc.includes("'strict-dynamic'")) {
    violations.push({
      rule: "CSP2",
      directive: "script-src",
      description: "script-src is missing `'strict-dynamic'` (required to allow nonce-trusted scripts to load further scripts).",
    });
  }
  if (!styleSrc.some((s) => /^'?nonce-\$\{[^}]*\}'?$/.test(s) || s.startsWith("'nonce-"))) {
    violations.push({
      rule: "CSP2",
      directive: "style-src",
      description: "style-src is missing a per-request `nonce-${nonce}` source.",
    });
  }

  const objectSrc = directives.get("object-src") ?? [];
  if (objectSrc.length === 0 || objectSrc[0] !== "'none'") {
    violations.push({
      rule: "HARD",
      directive: "object-src",
      description: "object-src must be exactly `'none'` (defense-in-depth; legacy plugins).",
    });
  }
  const baseUri = directives.get("base-uri") ?? [];
  if (baseUri.length === 0 || baseUri[0] !== "'self'") {
    violations.push({
      rule: "HARD",
      directive: "base-uri",
      description: "base-uri must be exactly `'self'` (prevents <base> hijack).",
    });
  }
  const frameAncestors = directives.get("frame-ancestors") ?? [];
  if (frameAncestors.length === 0 || frameAncestors[0] !== "'none'") {
    violations.push({
      rule: "HARD",
      directive: "frame-ancestors",
      description: "frame-ancestors must be exactly `'none'` (clickjacking lockdown).",
    });
  }

  return violations;
}

/**
 * Run the full CSP check on a middleware file. Public entrypoint exercised
 * by both the CLI and the Vitest sibling.
 *
 * @param filepath  Absolute or repo-relative path to the middleware file.
 */
export function checkCspStrict(filepath: string): CheckResult {
  const abs = path.resolve(filepath);
  if (!fs.existsSync(abs)) {
    return {
      pass: false,
      file: filepath,
      csp: null,
      violations: [],
      error: `file not found: ${filepath}`,
    };
  }

  const project = new Project({ useInMemoryFileSystem: false, compilerOptions: {} });
  const sf = project.addSourceFileAtPath(abs);
  const csp = extractCspString(sf);
  if (csp === null) {
    return {
      pass: false,
      file: filepath,
      csp: null,
      violations: [
        {
          rule: "CSP_NOT_FOUND",
          directive: "(none)",
          description:
            "Could not locate a CSP header string. Expected a `buildCSP` function or a string literal containing `default-src` and `script-src`.",
        },
      ],
    };
  }

  const directives = parseCspDirectives(csp);
  const violations = evaluateCsp(directives);
  return {
    pass: violations.length === 0,
    file: filepath,
    csp,
    violations,
  };
}

function main(argv: string[]): number {
  const arg = argv[2];
  if (!arg) {
    process.stderr.write("usage: tsx frontend/scripts/check_csp_strict.ts <middleware_filepath>\n");
    return 2;
  }
  try {
    const result = checkCspStrict(arg);
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    if (result.error) return 2;
    return result.pass ? 0 : 1;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    process.stdout.write(JSON.stringify({ pass: false, file: arg, csp: null, violations: [], error: msg }) + "\n");
    return 2;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
