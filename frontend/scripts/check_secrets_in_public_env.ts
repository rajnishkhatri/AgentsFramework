/**
 * check_secrets_in_public_env.ts — Frontend Reviewer tool (FD3.SEC1 /
 * FE-AP-18 AUTO-REJECT).
 *
 * Reads `.env*` files (or any `next.config.ts`-style file) line-by-line,
 * extracts every `NEXT_PUBLIC_*` variable name, and flags any whose name
 * matches the secret-pattern regex set:
 *
 *   *KEY*, *SECRET*, *TOKEN*, *PRIVATE*, *API*, *CREDENTIAL*  (case-insensitive)
 *
 * Also flags raw API-key-shaped VALUES whose default leaks into a
 * NEXT_PUBLIC_ slot:
 *
 *   - long base64-ish or hex strings (>=32 chars)
 *   - `sk_*` / `pk_*` Stripe-style identifiers
 *   - JWT-shaped strings (3 base64url segments separated by '.')
 *
 * ## False-positive suppression (hybrid)
 *
 * The detector intentionally over-fires on names that contain `KEY`,
 * `API`, etc. so it never silently approves a true leak. Two opt-in
 * channels narrow the false-positive surface for documented public-by-
 * design vendor variables (e.g. CopilotKit's `cpk_pub_*` browser key):
 *
 * 1. **`NEXT_PUBLIC_*PUBLIC*` substring rule.** When a variable is named
 *    `NEXT_PUBLIC_<…>` AND the suffix after `NEXT_PUBLIC_` itself
 *    contains the substring `PUBLIC` (case-insensitive), the
 *    NAME-pattern check is skipped. The variable's NAME has loudly
 *    re-affirmed the public-by-design intent. The VALUE-shape check
 *    still runs — a `NEXT_PUBLIC_FOO_PUBLIC_KEY=sk_live_…` with a
 *    leaked Stripe secret value still trips FE-AP-18.
 *
 * 2. **Per-project allowlist file.** The optional `--allowlist <path>`
 *    flag points to a JSON file shaped as
 *    `{ "names": [string], "patterns": [regex_string] }`. Default path
 *    when the flag is omitted: `frontend/scripts/secrets_allowlist.json`
 *    (relative to the script location). If the file is missing, no
 *    allowlist is applied. An exact-match against `names[]` skips BOTH
 *    the NAME regex AND the VALUE-shape check for that variable. A
 *    regex match against `patterns[]` applied to the VALUE skips only
 *    the value-shape check (so vendor public-key prefixes like
 *    `^cpk_pub_…$` can be pre-allowed for any future variable that
 *    serves them).
 *
 * Output JSON conforms to §5 of the Frontend Reviewer system prompt:
 *   {
 *     "pass": bool,
 *     "file": str,
 *     "violations": [{"var": str, "line": int, "matched_pattern": str}]
 *   }
 *
 * Exit codes: 0 on PASS, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_secrets_in_public_env.ts <env_filepath> [--allowlist <path>]`
 */

import * as path from "node:path";
import * as fs from "node:fs";

interface Violation {
  var: string;
  line: number;
  matched_pattern: string;
}

interface CheckResult {
  pass: boolean;
  file: string;
  violations: Violation[];
  error?: string;
}

interface AllowlistFile {
  names?: string[];
  patterns?: string[];
}

/**
 * Resolved allowlist used by `evaluateEnvLine`. `names` is matched by
 * exact equality; `patterns` is a list of pre-compiled regexes that
 * are applied to the VALUE (anywhere match — `RegExp.test` semantics).
 */
export interface ResolvedAllowlist {
  names: ReadonlySet<string>;
  patterns: ReadonlyArray<RegExp>;
}

const EMPTY_ALLOWLIST: ResolvedAllowlist = {
  names: new Set<string>(),
  patterns: [],
};

const NAME_PATTERNS: ReadonlyArray<{ rx: RegExp; label: string }> = [
  { rx: /KEY/i, label: "*KEY*" },
  { rx: /SECRET/i, label: "*SECRET*" },
  { rx: /TOKEN/i, label: "*TOKEN*" },
  { rx: /PRIVATE/i, label: "*PRIVATE*" },
  { rx: /API/i, label: "*API*" },
  { rx: /CREDENTIAL/i, label: "*CREDENTIAL*" },
];

const VALUE_PATTERNS: ReadonlyArray<{ rx: RegExp; label: string }> = [
  { rx: /^sk_[A-Za-z0-9_-]{20,}$/, label: "sk_* secret-key shape" },
  { rx: /^pk_[A-Za-z0-9_-]{20,}$/, label: "pk_* public-key shape" },
  { rx: /^[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}$/, label: "JWT-shape" },
  { rx: /^[A-Fa-f0-9]{40,}$/, label: "long-hex shape (>=40 chars)" },
  { rx: /^[A-Za-z0-9+/=_-]{48,}$/, label: "long-base64 shape (>=48 chars)" },
];

const NEXT_PUBLIC_PREFIX = "NEXT_PUBLIC_";

/**
 * Compile a JSON allowlist file from disk into the runtime form the
 * line evaluator consumes. Missing file => empty allowlist (the caller
 * should NOT treat absence as an error; the default behaviour is
 * "no allowlist"). Malformed JSON or invalid regex patterns surface as
 * a thrown `Error` so the CLI can map them to exit code 2.
 *
 * @param allowlistPath  Absolute or relative path. Resolved against CWD.
 */
export function loadAllowlist(allowlistPath: string | null): ResolvedAllowlist {
  if (!allowlistPath) return EMPTY_ALLOWLIST;
  const abs = path.resolve(allowlistPath);
  if (!fs.existsSync(abs)) return EMPTY_ALLOWLIST;
  const raw = fs.readFileSync(abs, "utf8");
  let parsed: AllowlistFile;
  try {
    parsed = JSON.parse(raw) as AllowlistFile;
  } catch (e) {
    throw new Error(
      `failed to parse allowlist JSON at ${abs}: ${e instanceof Error ? e.message : String(e)}`,
    );
  }
  const names = new Set<string>(Array.isArray(parsed.names) ? parsed.names : []);
  const patterns: RegExp[] = [];
  for (const p of Array.isArray(parsed.patterns) ? parsed.patterns : []) {
    try {
      patterns.push(new RegExp(p));
    } catch (e) {
      throw new Error(
        `invalid regex in allowlist patterns[] (${p}): ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }
  return { names, patterns };
}

/**
 * Apply the name + value rules to a single `KEY=VALUE` line. Returns null
 * when the line is not a NEXT_PUBLIC_ assignment, or a violation entry
 * when one of the patterns matches. The optional `allowlist` argument
 * narrows false positives (see file header for the hybrid rules).
 *
 * @param line       Raw file line (with or without trailing newline).
 * @param lineNo     1-indexed line number for diagnostics.
 * @param allowlist  Resolved allowlist; defaults to empty (= legacy behaviour).
 */
export function evaluateEnvLine(
  line: string,
  lineNo: number,
  allowlist: ResolvedAllowlist = EMPTY_ALLOWLIST,
): Violation | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#")) return null;
  const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*(.*)$/);
  if (!match) return null;
  const name = match[1] ?? "";
  if (!name.startsWith(NEXT_PUBLIC_PREFIX)) return null;

  // Allowlist short-circuit: a name match skips BOTH name + value checks.
  if (allowlist.names.has(name)) return null;

  // Hybrid rule #1: when the suffix after `NEXT_PUBLIC_` contains the
  // substring `PUBLIC` (case-insensitive), the variable's name itself
  // re-affirms the public-by-design intent — skip the NAME-pattern
  // check. The VALUE-shape check still runs below.
  const suffix = name.slice(NEXT_PUBLIC_PREFIX.length);
  const hasPublicAffirmation = /PUBLIC/i.test(suffix);

  if (!hasPublicAffirmation) {
    for (const { rx, label } of NAME_PATTERNS) {
      if (rx.test(name)) {
        return { var: name, line: lineNo, matched_pattern: `name~${label}` };
      }
    }
  }

  let raw = (match[2] ?? "").trim();
  if ((raw.startsWith("'") && raw.endsWith("'")) || (raw.startsWith('"') && raw.endsWith('"'))) {
    raw = raw.slice(1, -1);
  }

  // Allowlist patterns: a value matching a pre-allowed shape (e.g.
  // CopilotKit's `cpk_pub_…`) is exempt from the value-shape detector.
  if (raw) {
    for (const px of allowlist.patterns) {
      if (px.test(raw)) return null;
    }
  }

  for (const { rx, label } of VALUE_PATTERNS) {
    if (raw && rx.test(raw)) {
      return { var: name, line: lineNo, matched_pattern: `value~${label}` };
    }
  }
  return null;
}

/**
 * Run the check on a single file.
 *
 * @param filepath   Absolute or repo-relative path to `.env*` or
 *                   `next.config.ts`.
 * @param allowlist  Resolved allowlist (defaults to empty).
 */
export function checkSecretsInPublicEnv(
  filepath: string,
  allowlist: ResolvedAllowlist = EMPTY_ALLOWLIST,
): CheckResult {
  const abs = path.resolve(filepath);
  if (!fs.existsSync(abs)) {
    return {
      pass: false,
      file: filepath,
      violations: [],
      error: `file not found: ${filepath}`,
    };
  }
  const text = fs.readFileSync(abs, "utf8");
  const violations: Violation[] = [];
  text.split(/\r?\n/).forEach((line, i) => {
    const v = evaluateEnvLine(line, i + 1, allowlist);
    if (v) violations.push(v);
  });
  return { pass: violations.length === 0, file: filepath, violations };
}

const SCRIPT_DIR = (import.meta as { dirname?: string }).dirname ?? __dirname;
const DEFAULT_ALLOWLIST_PATH = path.join(SCRIPT_DIR, "secrets_allowlist.json");

interface ParsedArgs {
  filepath: string | null;
  allowlistPath: string | null;
  usageError: string | null;
}

/**
 * Tiny CLI parser shared by `main` and the unit tests. Accepts:
 *   <env_filepath> [--allowlist <path>]
 *
 * `--allowlist` may also be passed as `--allowlist=<path>`. When
 * `--allowlist` is omitted, the caller falls back to the bundled
 * default at `frontend/scripts/secrets_allowlist.json`.
 *
 * @param argv  Raw `process.argv` slice (everything after node + script).
 */
export function parseCliArgs(argv: string[]): ParsedArgs {
  let filepath: string | null = null;
  let allowlistPath: string | null = null;
  let i = 0;
  while (i < argv.length) {
    const a = argv[i] ?? "";
    if (a === "--allowlist") {
      const next = argv[i + 1];
      if (!next) {
        return {
          filepath,
          allowlistPath,
          usageError: "--allowlist requires a path argument",
        };
      }
      allowlistPath = next;
      i += 2;
      continue;
    }
    if (a.startsWith("--allowlist=")) {
      allowlistPath = a.slice("--allowlist=".length);
      i += 1;
      continue;
    }
    if (a.startsWith("--")) {
      return { filepath, allowlistPath, usageError: `unknown flag: ${a}` };
    }
    if (filepath === null) {
      filepath = a;
      i += 1;
      continue;
    }
    return { filepath, allowlistPath, usageError: `unexpected argument: ${a}` };
  }
  return { filepath, allowlistPath, usageError: null };
}

function main(argv: string[]): number {
  const parsed = parseCliArgs(argv.slice(2));
  if (parsed.usageError) {
    process.stderr.write(`error: ${parsed.usageError}\n`);
    process.stderr.write(
      "usage: tsx frontend/scripts/check_secrets_in_public_env.ts <env_filepath> [--allowlist <path>]\n",
    );
    return 2;
  }
  if (!parsed.filepath) {
    process.stderr.write(
      "usage: tsx frontend/scripts/check_secrets_in_public_env.ts <env_filepath> [--allowlist <path>]\n",
    );
    return 2;
  }
  const allowlistPath = parsed.allowlistPath ?? DEFAULT_ALLOWLIST_PATH;
  let allowlist: ResolvedAllowlist;
  try {
    allowlist = loadAllowlist(allowlistPath);
  } catch (e) {
    process.stderr.write(
      `${e instanceof Error ? e.message : String(e)}\n`,
    );
    return 2;
  }
  const result = checkSecretsInPublicEnv(parsed.filepath, allowlist);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  if (result.error) return 2;
  return result.pass ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
