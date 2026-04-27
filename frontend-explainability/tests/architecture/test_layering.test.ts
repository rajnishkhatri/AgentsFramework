/**
 * Architecture test: import layering rules for frontend-explainability/.
 *
 * Mirrors frontend/tests/architecture/test_frontend_layering.test.ts but
 * path-rooted at frontend-explainability/lib/.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const LIB_ROOT = path.resolve(__dirname, "../../lib");

type SubPackage =
  | "wire"
  | "ports"
  | "adapters"
  | "translators"
  | "transport"
  | "composition";

function ringOf(filePath: string): SubPackage | "other" {
  const rel = path.relative(LIB_ROOT, filePath);
  if (rel.startsWith("wire")) return "wire";
  if (rel.startsWith("ports")) return "ports";
  if (rel.startsWith("adapters")) return "adapters";
  if (rel.startsWith("translators")) return "translators";
  if (rel.startsWith("transport")) return "transport";
  if (rel === "composition.ts") return "composition";
  return "other";
}

const ALLOWED_IMPORTS: Record<SubPackage, readonly SubPackage[]> = {
  wire: [],
  ports: ["wire"],
  translators: ["wire"],
  transport: ["wire"],
  adapters: ["ports", "wire"],
  composition: ["wire", "ports", "adapters", "translators", "transport"],
};

function extractImports(content: string): string[] {
  const importRegex = /from\s+['"]([^'"]+)['"]/g;
  const imports: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = importRegex.exec(content)) !== null) {
    imports.push(match[1]!);
  }
  return imports;
}

function collectTsFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const files: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectTsFiles(full));
    } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
      if (!entry.name.endsWith(".test.ts") && !entry.name.endsWith(".test.tsx")) {
        files.push(full);
      }
    }
  }
  return files;
}

function resolveImportToRing(
  importPath: string,
  fromFile: string,
): SubPackage | null {
  if (!importPath.startsWith(".") && !importPath.startsWith("@/lib/")) {
    return null;
  }
  let resolved: string;
  if (importPath.startsWith("@/lib/")) {
    resolved = path.resolve(LIB_ROOT, importPath.slice(6));
  } else {
    resolved = path.resolve(path.dirname(fromFile), importPath);
  }
  const rel = path.relative(LIB_ROOT, resolved);
  if (rel.startsWith("..")) return null;
  return ringOf(resolved) as SubPackage;
}

describe("frontend-explainability layering", () => {
  it("wire/ imports nothing from lib/", () => {
    const wireDir = path.join(LIB_ROOT, "wire");
    const files = collectTsFiles(wireDir);
    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      const imports = extractImports(content);
      for (const imp of imports) {
        const ring = resolveImportToRing(imp, file);
        if (ring !== null) {
          expect.soft(
            ring,
            `${path.relative(LIB_ROOT, file)} imports from ${ring}/ (forbidden for wire)`,
          ).toBe("wire");
        }
      }
    }
  });

  it("all lib/ files respect the dependency table", () => {
    const files = collectTsFiles(LIB_ROOT);
    const violations: string[] = [];

    for (const file of files) {
      const ring = ringOf(file);
      if (ring === "other") continue;

      const allowed = ALLOWED_IMPORTS[ring];
      const content = fs.readFileSync(file, "utf-8");
      const imports = extractImports(content);

      for (const imp of imports) {
        const targetRing = resolveImportToRing(imp, file);
        if (targetRing === null || targetRing === ring) continue;
        if (!allowed.includes(targetRing)) {
          violations.push(
            `${path.relative(LIB_ROOT, file)} (${ring}) imports from ${targetRing}/ (not in allowed: [${allowed.join(", ")}])`,
          );
        }
      }
    }

    expect(violations).toEqual([]);
  });
});
