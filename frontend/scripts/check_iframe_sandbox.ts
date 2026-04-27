/**
 * check_iframe_sandbox.ts — Frontend Reviewer tool (FD3.SBX1 / FD3.SBX2 /
 * FE-AP-4 AUTO-REJECT).
 *
 * Walks the JSX of a `.tsx` file and asserts every `<iframe>` element:
 *
 *   SBX1   has a `sandbox` attribute (missing entirely → AUTO-REJECT FE-AP-4).
 *   SBX2   the sandbox token list contains exactly `"allow-scripts"` and
 *          excludes the dangerous-trio set:
 *            allow-same-origin, allow-top-navigation, allow-forms,
 *            allow-popups, allow-modals, allow-pointer-lock.
 *
 * Output JSON conforms to §5 of the Frontend Reviewer system prompt:
 *   {
 *     "pass": bool,
 *     "file": str,
 *     "iframes": [{"line": int, "sandbox": str|null, "violations": [str]}]
 *   }
 *
 * Exit codes: 0 on PASS, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_iframe_sandbox.ts <filepath>`
 */

import * as path from "node:path";
import * as fs from "node:fs";
import {
  Project,
  SyntaxKind,
  type JsxAttributeLike,
  type JsxOpeningElement,
  type JsxSelfClosingElement,
  type SourceFile,
} from "ts-morph";

interface IframeReport {
  line: number;
  sandbox: string | null;
  violations: string[];
}

interface CheckResult {
  pass: boolean;
  file: string;
  iframes: IframeReport[];
  error?: string;
}

const FORBIDDEN_TOKENS = new Set<string>([
  "allow-same-origin",
  "allow-top-navigation",
  "allow-top-navigation-by-user-activation",
  "allow-forms",
  "allow-popups",
  "allow-popups-to-escape-sandbox",
  "allow-modals",
  "allow-pointer-lock",
  "allow-presentation",
  "allow-storage-access-by-user-activation",
]);

const REQUIRED_TOKEN = "allow-scripts";

function attributeText(attr: JsxAttributeLike): string | null {
  if (attr.getKind() !== SyntaxKind.JsxAttribute) return null;
  const init = (attr as { getInitializer?: () => unknown }).getInitializer?.();
  if (!init) return ""; // boolean attribute, e.g. `<iframe sandbox />`
  const node = init as { getKind: () => SyntaxKind; getLiteralValue?: () => string; getText: () => string };
  const k = node.getKind();
  if (k === SyntaxKind.StringLiteral) {
    return node.getLiteralValue?.() ?? "";
  }
  if (k === SyntaxKind.JsxExpression) {
    // Expression form (e.g. sandbox={"allow-scripts"} or a variable). For
    // a string-literal expression we extract; otherwise we fall back to
    // the raw text and the caller treats it as an unverifiable value.
    const txt = node.getText();
    const literal = txt.match(/\{\s*["'`]([^"'`]*)["'`]\s*\}/);
    if (literal && literal[1] !== undefined) return literal[1];
    return txt;
  }
  return node.getText();
}

function reportFor(open: JsxOpeningElement | JsxSelfClosingElement): IframeReport {
  const violations: string[] = [];
  const attrs = open.getAttributes();
  let sandbox: string | null = null;
  let hasSandbox = false;
  for (const attr of attrs) {
    if (attr.getKind() !== SyntaxKind.JsxAttribute) continue;
    const name = (attr as { getNameNode?: () => { getText: () => string } }).getNameNode?.().getText();
    if (name === "sandbox") {
      hasSandbox = true;
      sandbox = attributeText(attr);
      break;
    }
  }
  if (!hasSandbox) {
    violations.push("SBX1: <iframe> missing the `sandbox` attribute (FE-AP-4 AUTO-REJECT).");
  } else {
    const value = (sandbox ?? "").trim();
    if (value === "" || value.startsWith("{") || value.includes("${")) {
      violations.push(
        "SBX2: <iframe sandbox> uses a non-literal value; the reviewer cannot verify the token list. Use a string literal.",
      );
    } else {
      const tokens = value.split(/\s+/).filter(Boolean);
      if (!tokens.includes(REQUIRED_TOKEN)) {
        violations.push(
          `SBX2: <iframe sandbox> must include exactly \`${REQUIRED_TOKEN}\` (got "${value}").`,
        );
      }
      for (const tok of tokens) {
        if (FORBIDDEN_TOKENS.has(tok)) {
          violations.push(
            `SBX2: <iframe sandbox> includes forbidden token \`${tok}\` (FE-AP-4 AUTO-REJECT).`,
          );
        }
      }
    }
  }
  return {
    line: open.getStartLineNumber(),
    sandbox,
    violations,
  };
}

function collectIframes(sf: SourceFile): IframeReport[] {
  const out: IframeReport[] = [];
  for (const node of sf.getDescendants()) {
    if (node.getKind() === SyntaxKind.JsxOpeningElement) {
      const open = node as JsxOpeningElement;
      const tag = open.getTagNameNode().getText();
      if (tag === "iframe") out.push(reportFor(open));
    } else if (node.getKind() === SyntaxKind.JsxSelfClosingElement) {
      const sc = node as JsxSelfClosingElement;
      const tag = sc.getTagNameNode().getText();
      if (tag === "iframe") out.push(reportFor(sc));
    }
  }
  return out;
}

/**
 * Run the iframe sandbox check on a single file. Public entrypoint used by
 * the CLI wrapper and the Vitest sibling.
 *
 * @param filepath  Absolute or repo-relative path to the .tsx file.
 */
export function checkIframeSandbox(filepath: string): CheckResult {
  const abs = path.resolve(filepath);
  if (!fs.existsSync(abs)) {
    return {
      pass: false,
      file: filepath,
      iframes: [],
      error: `file not found: ${filepath}`,
    };
  }
  try {
    const project = new Project({ useInMemoryFileSystem: false, compilerOptions: { jsx: 4 } });
    const sf = project.addSourceFileAtPath(abs);
    const iframes = collectIframes(sf);
    const pass = iframes.every((i) => i.violations.length === 0);
    return { pass, file: filepath, iframes };
  } catch (e) {
    return {
      pass: false,
      file: filepath,
      iframes: [],
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

function main(argv: string[]): number {
  const arg = argv[2];
  if (!arg) {
    process.stderr.write("usage: tsx frontend/scripts/check_iframe_sandbox.ts <filepath>\n");
    return 2;
  }
  const result = checkIframeSandbox(arg);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  if (result.error) return 2;
  return result.pass ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
