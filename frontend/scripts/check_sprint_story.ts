/**
 * check_sprint_story.ts — Frontend Reviewer tool (FD8.{story_id}).
 *
 * Reads the "Sprint Story Acceptance Map" markdown table from
 * `prompts/codeReviewer/frontend/architecture_rules.j2`, locates the row
 * for the requested `story_id` (e.g. `S2.1.2`), then:
 *
 *   1. Verifies every `key_files` entry exists on disk.
 *   2. Dispatches the `acceptance_signal` shell command (when present)
 *      and captures its exit code + stdout/stderr.
 *
 * Output JSON conforms to the spec in §5 of the Frontend Reviewer system
 * prompt:
 *   {
 *     "pass": bool,
 *     "story_id": str,
 *     "key_files_present": [str],
 *     "key_files_missing": [str],
 *     "acceptance_signal": str,
 *     "acceptance_signal_exit_code": int,
 *     "acceptance_signal_output": str
 *   }
 *
 * Exit codes: 0 on PASS, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_sprint_story.ts <story_id>`
 */

import * as path from "node:path";
import * as fs from "node:fs";
import { spawnSync } from "node:child_process";

/**
 * Cached `rg` availability lookup. The Sprint Story Acceptance Map uses
 * `rg -n` for in-file content probes, but ripgrep is not part of the
 * default macOS / minimal-Linux toolchain. When it is missing we fall
 * back to `grep -nE` which has the same flag surface for these probes
 * (line-numbered, ERE patterns, exits non-zero on no-match).
 */
let _rgAvailable: boolean | null = null;
function rgAvailable(): boolean {
  if (_rgAvailable !== null) return _rgAvailable;
  const probe = spawnSync("bash", ["-lc", "command -v rg >/dev/null 2>&1"], {
    encoding: "utf8",
  });
  _rgAvailable = probe.status === 0;
  return _rgAvailable;
}

interface SprintRow {
  story_id: string;
  key_files: string[];
  acceptance_signal: string;
  known_status: string;
}

interface CheckResult {
  pass: boolean;
  story_id: string;
  row_found: boolean;
  key_files_present: string[];
  key_files_missing: string[];
  acceptance_signal: string;
  acceptance_signal_exit_code: number;
  acceptance_signal_output: string;
  error?: string;
}

const SCRIPT_DIR = (import.meta as { dirname?: string }).dirname ?? __dirname;
const REPO_ROOT = path.resolve(SCRIPT_DIR, "..", "..");
const ARCH_RULES = path.join(
  REPO_ROOT,
  "prompts",
  "codeReviewer",
  "frontend",
  "architecture_rules.j2",
);

/**
 * Parse the Sprint Story Acceptance Map (Markdown table) out of the
 * architecture_rules.j2 file. Returns one row per data line in the table.
 *
 * @param markdown  Raw file contents.
 */
export function parseSprintStoryMap(markdown: string): SprintRow[] {
  const rows: SprintRow[] = [];
  const lines = markdown.split("\n");
  let inTable = false;
  for (const line of lines) {
    if (/^##\s+Sprint Story Acceptance Map/.test(line)) {
      inTable = true;
      continue;
    }
    if (!inTable) continue;
    // Leaving the table on a new H2 just toggles inTable off; we keep
    // scanning so multiple "Sprint Story Acceptance Map" sections can be
    // parsed (used by the test fixtures).
    if (/^##\s+/.test(line) && !/Sprint Story/.test(line)) {
      inTable = false;
      continue;
    }
    if (!line.startsWith("|")) continue;

    const trimmed = line.trim();
    // Skip header / divider rows.
    if (/\|-+\|/.test(trimmed)) continue;
    if (/\bstory_id\b/i.test(trimmed) && /\bkey_files\b/i.test(trimmed)) continue;

    const cells = trimmed
      .split("|")
      .slice(1, -1)
      .map((c) => c.trim());
    if (cells.length < 4) continue;
    const id = (cells[0] ?? "").replace(/\*\*/g, "").trim();
    if (!/^S\d/.test(id)) continue;

    const keyFilesRaw = cells[1] ?? "";
    const acceptance = cells[2] ?? "";
    const known = cells[3] ?? "";

    const keyFiles = extractFilePaths(keyFilesRaw);
    rows.push({
      story_id: id,
      key_files: keyFiles,
      acceptance_signal: stripBackticks(acceptance),
      known_status: known,
    });
  }
  return rows;
}

function stripBackticks(s: string): string {
  return s.replace(/`/g, "").trim();
}

function extractFilePaths(cell: string): string[] {
  // Pull out any `path/with/extension.ext` candidates from inside backticks
  // or bare. Brace-expansion patterns like `foo.{ts,test.ts}` are expanded.
  const out: string[] = [];
  const codeMatches = cell.match(/`([^`]+)`/g) ?? [];
  for (const cm of codeMatches) {
    const inner = cm.slice(1, -1).trim();
    out.push(...expandBraces(inner));
  }
  if (out.length === 0) {
    // Fallback: bare path tokens.
    for (const tok of cell.split(/[,\s]+/)) {
      if (/^[\w./[\]-]+\.[\w]+$/.test(tok)) out.push(tok);
    }
  }
  return out
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !s.startsWith("n/a"));
}

/**
 * Translate a Sprint Story Acceptance Map signal into an executable
 * bash command. The Map uses ` + ` as a markdown-friendly "AND"
 * separator between component checks (e.g.
 * "pytest … + rg -n tablesFilter …"); shell-execute these as `&&` so
 * the row only PASSES when every component check exits 0.
 *
 * `pytest` invocations targeting `tests/infra/` are additionally
 * defended with `--override-ini="addopts="` so pyproject.toml's default
 * `-m 'not infra'` exclusion does not deselect the entire suite. This
 * mirrors how the IaC reviewer runs the suite in CI (`pytest -m infra`)
 * and is a no-op for tests that are not marker-decorated.
 *
 * @param signal  Raw `acceptance_signal` cell from architecture_rules.j2.
 */
export function composeShellCommand(signal: string): string {
  const parts = signal
    .split(/\s+\+\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
  const normalised = parts.map((cmd) => {
    let next = cmd;
    if (/^pytest\b/.test(next) && /tests\/infra\//.test(next)) {
      next = next.replace(/^pytest\b/, 'pytest --override-ini="addopts="');
    }
    if (/^rg\b/.test(next) && !rgAvailable()) {
      // `rg -n PAT PATH` -> `grep -nE PAT PATH`. Both accept -n (line
      // numbers) and exit non-zero on no-match; grep -E parses POSIX
      // ERE which is the rg-default flavour for the simple anchored
      // word-boundary patterns the Map uses.
      next = next.replace(/^rg\s+-n\b/, "grep -nE").replace(/^rg\b/, "grep -E");
    }
    return next;
  });
  return normalised.join(" && ");
}

function expandBraces(s: string): string[] {
  // Simple `prefix.{a,b}.suffix` expansion (one set per token is enough).
  const m = s.match(/^(.*?)\{([^}]+)\}(.*)$/);
  if (!m) return [s];
  const [, pre = "", inner = "", post = ""] = m;
  return inner.split(",").map((piece) => `${pre}${piece.trim()}${post}`);
}

/**
 * Look up a single sprint story by id and verify its key files + signal.
 *
 * @param storyId  Sprint board id (e.g. `S2.1.2`).
 */
export function checkSprintStory(storyId: string): CheckResult {
  const baseResult: CheckResult = {
    pass: false,
    story_id: storyId,
    row_found: false,
    key_files_present: [],
    key_files_missing: [],
    acceptance_signal: "",
    acceptance_signal_exit_code: -1,
    acceptance_signal_output: "",
  };
  if (!fs.existsSync(ARCH_RULES)) {
    return { ...baseResult, error: `architecture_rules.j2 not found at ${ARCH_RULES}` };
  }
  const md = fs.readFileSync(ARCH_RULES, "utf8");
  const rows = parseSprintStoryMap(md);
  const row = rows.find((r) => r.story_id === storyId);
  if (!row) {
    return {
      ...baseResult,
      error: `story_id ${storyId} not found in Sprint Story Acceptance Map`,
    };
  }

  const present: string[] = [];
  const missing: string[] = [];
  for (const rel of row.key_files) {
    const abs = path.join(REPO_ROOT, rel);
    if (fs.existsSync(abs)) present.push(rel);
    else missing.push(rel);
  }

  let exitCode = 0;
  let output = "";
  if (row.acceptance_signal && !row.acceptance_signal.toLowerCase().startsWith("manual")) {
    const shellCommand = composeShellCommand(row.acceptance_signal);
    const ran = spawnSync("bash", ["-lc", shellCommand], {
      cwd: REPO_ROOT,
      encoding: "utf8",
      timeout: 60_000,
    });
    exitCode = ran.status ?? -1;
    output = `${ran.stdout ?? ""}\n${ran.stderr ?? ""}`.trim();
  } else {
    output = `acceptance_signal skipped (manual or empty): "${row.acceptance_signal}"`;
  }

  const pass = missing.length === 0 && exitCode === 0;
  return {
    pass,
    story_id: storyId,
    row_found: true,
    key_files_present: present,
    key_files_missing: missing,
    acceptance_signal: row.acceptance_signal,
    acceptance_signal_exit_code: exitCode,
    acceptance_signal_output: output,
  };
}

function main(argv: string[]): number {
  const arg = argv[2];
  if (!arg) {
    process.stderr.write("usage: tsx frontend/scripts/check_sprint_story.ts <story_id>\n");
    return 2;
  }
  const result = checkSprintStory(arg);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  if (result.error) return 2;
  return result.pass ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
