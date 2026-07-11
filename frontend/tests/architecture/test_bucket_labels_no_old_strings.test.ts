/**
 * D2 FR-1 — no pre-parity bucket display labels in the runtime TS/TSX bundle.
 *
 * Walks frontend ts/tsx files (excluding PreAct/, .next/, node_modules/,
 * dist/) and fails if any of the three old display strings remain:
 *   - "Grammar & Usage"
 *   - "Rhetorical Skills"
 *   - skill-name-position "Style" (heuristic: name: "Style" or
 *     "s-style": "Style" / Record value next to s-style key)
 *
 * Substring false positives (TextStyle, styleProp) are intentionally
 * ignored — only whole quoted literals in name-position fire.
 */

import { describe, expect, it } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");

const OLD_EXACT = ['"Grammar & Usage"', '"Rhetorical Skills"'] as const;

/** Skill-name-position "Style" — not TextStyle / styleProp. */
const STYLE_NAME_RE =
  /(?:name\s*:\s*"Style"|"s-style"\s*:\s*"Style")/;

const SKIP_DIR = new Set([
  "node_modules",
  ".next",
  "dist",
  "coverage",
  "playwright-report",
  "test-results",
]);

function walkTsFiles(dir: string, out: string[]): void {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".") && entry.isDirectory()) {
      if (SKIP_DIR.has(entry.name)) continue;
    }
    if (SKIP_DIR.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkTsFiles(full, out);
      continue;
    }
    if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
      out.push(full);
    }
  }
}

describe("D2 FR-1 — no old bucket display labels in frontend TS/TSX", () => {
  it("fails when Grammar & Usage / Rhetorical Skills / name: Style remain", () => {
    const files: string[] = [];
    walkTsFiles(FRONTEND_ROOT, files);

    const hits: string[] = [];
    for (const file of files) {
      // This arch test file itself documents the forbidden strings — skip it.
      if (file.endsWith("test_bucket_labels_no_old_strings.test.ts")) continue;
      const text = fs.readFileSync(file, "utf8");
      const rel = path.relative(FRONTEND_ROOT, file);
      for (const needle of OLD_EXACT) {
        if (text.includes(needle)) {
          hits.push(`${rel}: contains ${needle}`);
        }
      }
      if (STYLE_NAME_RE.test(text)) {
        hits.push(`${rel}: skill-name-position "Style"`);
      }
    }

    expect(
      hits,
      `Old bucket labels still present:\n${hits.join("\n")}`,
    ).toEqual([]);
  });
});
