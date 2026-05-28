/**
 * Architecture test (S4.2.1, hardened by Sprint 4 review F5).
 *
 * The brainstorm and sprint board both forbid graph re-execution from any
 * frontend layer.  This test enforces that the Replay surface (workflow
 * detail page + replay scrubber + replay translator) only consumes
 * already-fetched events and never reaches a runtime endpoint.
 *
 * Sprint 4 review F5 fix: the previous version allowlisted multiple
 * non-events client methods AND only scanned `app/traces/` -- which
 * meant a future change to `components/traces/ReplayScrubber.tsx` or
 * `lib/translators/events_to_replay_frames.ts` could introduce a runtime
 * endpoint without being caught.  We now:
 *   1. Scan the replay-specific component + translator files directly.
 *   2. Restrict the workflow-detail page (the only Replay entry point) to
 *      a tiny allowlist that explicitly includes `getWorkflowEvents`
 *      (the one read call Replay needs).
 *   3. The list page (`/traces/page.tsx`) keeps the broader allowlist
 *      because it is a pure RSC index, not the Replay surface.
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const PROJECT_ROOT = path.resolve(__dirname, "../..");
const TRACES_APP_ROOT = path.join(PROJECT_ROOT, "app", "traces");
const REPLAY_SURFACE_FILES = [
  // Workflow detail page hosts the Replay tab.
  path.join(PROJECT_ROOT, "app", "traces", "[wf_id]", "page.tsx"),
  // Replay UI shell.
  path.join(PROJECT_ROOT, "components", "traces", "ReplayScrubber.tsx"),
  // Pure translator that turns events into replay frames.
  path.join(PROJECT_ROOT, "lib", "translators", "events_to_replay_frames.ts"),
];

// Index pages such as /traces/page.tsx aren't the Replay surface; they may
// list adapter methods used elsewhere on the page (e.g. listWorkflows for
// the index table).  These remain under the broader scan that asserts no
// runtime endpoints are reached.
const INDEX_PAGE_ALLOWED_METHODS = new Set([
  "getWorkflowEvents",
  "getWorkflowDecisions",
  "getWorkflowIntegrity",
  "getWorkflowCompliance",
  "listWorkflows",
]);

// Replay surface is much stricter: only the events read is allowed.  Any
// new adapter method introduced here is a regression.
const REPLAY_SURFACE_ALLOWED_METHODS = new Set(["getWorkflowEvents"]);

const RUNTIME_CALL_FORBIDDEN_PATTERNS: RegExp[] = [
  /\/api\/v1\/workflows\/[^/]+\/(replay|resume|invoke|execute|run)/,
  /['"]\.\.\/orchestration/,
  /from\s+['"]@\/lib\/runtime/,
  /from\s+['"]langgraph/,
  /from\s+['"]langchain/,
];

const REPLAY_TRANSLATOR_FORBIDDEN_PATTERNS: RegExp[] = [
  /\bfetch\s*\(/,
  /\bEventSource\b/,
  /from\s+['"]@\/lib\/adapters/,
  /from\s+['"]@\/lib\/transport/,
  /from\s+['"]@\/lib\/composition/,
];

function collectTsFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === ".next") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectTsFiles(full));
    } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
      out.push(full);
    }
  }
  return out;
}

describe("replay has no runtime calls", () => {
  it("no file under app/traces/ calls a forbidden runtime endpoint", () => {
    const files = collectTsFiles(TRACES_APP_ROOT);
    expect(files.length).toBeGreaterThan(0);
    const violations: string[] = [];
    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      for (const pattern of RUNTIME_CALL_FORBIDDEN_PATTERNS) {
        if (pattern.test(content)) {
          violations.push(
            `${path.relative(PROJECT_ROOT, file)}: matches forbidden pattern ${pattern}`,
          );
        }
      }
    }
    expect(violations).toEqual([]);
  });

  it("no file under app/traces/ invokes an explainabilityClient method outside the read allowlist", () => {
    const files = collectTsFiles(TRACES_APP_ROOT);
    const methodCallRegex =
      /explainabilityClient\.([A-Za-z_][A-Za-z0-9_]*)/g;
    const violations: string[] = [];
    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      let match: RegExpExecArray | null;
      while ((match = methodCallRegex.exec(content)) !== null) {
        const method = match[1]!;
        if (!INDEX_PAGE_ALLOWED_METHODS.has(method)) {
          violations.push(
            `${path.relative(PROJECT_ROOT, file)}: calls unallowed method ${method}`,
          );
        }
      }
    }
    expect(violations).toEqual([]);
  });

  it("the Replay surface (page + scrubber + translator) only calls getWorkflowEvents", () => {
    const violations: string[] = [];
    for (const file of REPLAY_SURFACE_FILES) {
      if (!fs.existsSync(file)) continue;
      const content = fs.readFileSync(file, "utf-8");
      const methodCallRegex =
        /explainabilityClient\.([A-Za-z_][A-Za-z0-9_]*)/g;
      let match: RegExpExecArray | null;
      while ((match = methodCallRegex.exec(content)) !== null) {
        const method = match[1]!;
        if (!REPLAY_SURFACE_ALLOWED_METHODS.has(method)) {
          violations.push(
            `${path.relative(PROJECT_ROOT, file)}: Replay surface called ${method}; only getWorkflowEvents is allowed`,
          );
        }
      }
    }
    expect(violations).toEqual([]);
  });

  it("the replay translator MUST NOT reach for transport/adapter/SDK code", () => {
    const translatorFile = path.join(
      PROJECT_ROOT,
      "lib",
      "translators",
      "events_to_replay_frames.ts",
    );
    if (!fs.existsSync(translatorFile)) return;
    const content = fs.readFileSync(translatorFile, "utf-8");
    const violations: string[] = [];
    for (const pattern of REPLAY_TRANSLATOR_FORBIDDEN_PATTERNS) {
      if (pattern.test(content)) {
        violations.push(`${pattern}`);
      }
    }
    for (const pattern of RUNTIME_CALL_FORBIDDEN_PATTERNS) {
      if (pattern.test(content)) {
        violations.push(`${pattern}`);
      }
    }
    expect(violations).toEqual([]);
  });
});
