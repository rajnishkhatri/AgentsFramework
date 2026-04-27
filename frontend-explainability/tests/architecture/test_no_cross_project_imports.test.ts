/**
 * Architecture test: no cross-project imports.
 *
 * Rejects any import path containing ../../frontend/, ../frontend/,
 * or agent_ui_adapter.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const PROJECT_ROOT = path.resolve(__dirname, "../..");

const FORBIDDEN_PATTERNS = [
  /['"]\.\.\/\.\.\/frontend\//,
  /['"]\.\.\/frontend\//,
  /['"]agent_ui_adapter/,
  /from\s+['"]\.\.\/\.\.\/frontend\//,
  /from\s+['"]\.\.\/frontend\//,
  /from\s+['"]agent_ui_adapter/,
];

function collectTsFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const files: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === ".next") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectTsFiles(full));
    } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
      files.push(full);
    }
  }
  return files;
}

describe("no cross-project imports", () => {
  it("no file imports from frontend/ or agent_ui_adapter", () => {
    const files = collectTsFiles(PROJECT_ROOT);
    const violations: string[] = [];

    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]!;
        for (const pattern of FORBIDDEN_PATTERNS) {
          if (pattern.test(line)) {
            violations.push(
              `${path.relative(PROJECT_ROOT, file)}:${i + 1}: ${line.trim()}`,
            );
          }
        }
      }
    }

    expect(violations).toEqual([]);
  });
});
