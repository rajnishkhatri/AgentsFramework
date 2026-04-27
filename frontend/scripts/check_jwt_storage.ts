/**
 * check_jwt_storage.ts — Frontend Reviewer tool (FD3.SEC2).
 *
 * AST scans a `.ts` / `.tsx` file for `localStorage.setItem(...)` and
 * `sessionStorage.setItem(...)` calls whose key (first arg) OR value
 * (second arg) identifier matches the auth-pattern regex:
 *
 *   /(token|jwt|access|session|bearer|auth)/i
 *
 * Each match emits a violation with the line number, the storage API,
 * and the offending identifier. The OWASP / FE-AP-18 storage policy is
 * "JWT in HttpOnly + Secure + SameSite=Strict cookies, NEVER localStorage"
 * — this check enforces the second clause.
 *
 * Output JSON conforms to §5 of the Frontend Reviewer system prompt:
 *   {
 *     "pass": bool,
 *     "file": str,
 *     "violations": [{"line": int, "api": str, "key_or_value": str}]
 *   }
 *
 * Exit codes: 0 on PASS, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_jwt_storage.ts <filepath>`
 */

import * as path from "node:path";
import * as fs from "node:fs";
import { Project, SyntaxKind, type CallExpression } from "ts-morph";

interface Violation {
  line: number;
  api: string;
  key_or_value: string;
}

interface CheckResult {
  pass: boolean;
  file: string;
  violations: Violation[];
  error?: string;
}

const AUTH_PATTERN = /(token|jwt|access|session|bearer|auth)/i;
const STORAGE_OBJECTS = new Set<string>(["localStorage", "sessionStorage"]);

function exprText(node: { getText: () => string }): string {
  return node.getText();
}

function isStorageSetItem(call: CallExpression): { isStorage: boolean; api: string } {
  const expr = call.getExpression();
  if (expr.getKind() !== SyntaxKind.PropertyAccessExpression) return { isStorage: false, api: "" };
  const pae = expr.asKindOrThrow(SyntaxKind.PropertyAccessExpression);
  const member = pae.getName();
  if (member !== "setItem") return { isStorage: false, api: "" };
  const objText = pae.getExpression().getText();
  // Match `localStorage` or `window.localStorage` (and similar for session).
  for (const obj of STORAGE_OBJECTS) {
    if (objText === obj || objText.endsWith(`.${obj}`)) {
      return { isStorage: true, api: `${obj}.setItem` };
    }
  }
  return { isStorage: false, api: "" };
}

/**
 * Walk a file's AST and return every storage-write that handles an
 * auth-shaped key or identifier.
 *
 * @param filepath  Absolute or repo-relative path to a TypeScript source.
 */
export function checkJwtStorage(filepath: string): CheckResult {
  const abs = path.resolve(filepath);
  if (!fs.existsSync(abs)) {
    return {
      pass: false,
      file: filepath,
      violations: [],
      error: `file not found: ${filepath}`,
    };
  }
  try {
    const project = new Project({ useInMemoryFileSystem: false, compilerOptions: { jsx: 4 } });
    const sf = project.addSourceFileAtPath(abs);
    const violations: Violation[] = [];
    for (const call of sf.getDescendantsOfKind(SyntaxKind.CallExpression)) {
      const { isStorage, api } = isStorageSetItem(call);
      if (!isStorage) continue;
      const args = call.getArguments();
      const keyArg = args[0];
      const valArg = args[1];
      const keyText = keyArg ? exprText(keyArg).replace(/['"`]/g, "") : "";
      const valText = valArg ? exprText(valArg).replace(/['"`]/g, "") : "";
      if (AUTH_PATTERN.test(keyText) || AUTH_PATTERN.test(valText)) {
        violations.push({
          line: call.getStartLineNumber(),
          api,
          key_or_value: keyText || valText,
        });
      }
    }
    return { pass: violations.length === 0, file: filepath, violations };
  } catch (e) {
    return {
      pass: false,
      file: filepath,
      violations: [],
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

function main(argv: string[]): number {
  const arg = argv[2];
  if (!arg) {
    process.stderr.write("usage: tsx frontend/scripts/check_jwt_storage.ts <filepath>\n");
    return 2;
  }
  const result = checkJwtStorage(arg);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  if (result.error) return 2;
  return result.pass ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
