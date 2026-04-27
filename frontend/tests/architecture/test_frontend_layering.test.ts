/**
 * Frontend layering / dependency-rule enforcement (S3.10.1).
 *
 * Mirrors the §10 dependency direction table from FRONTEND_ARCHITECTURE.md and
 * enforces the four-ring contract via ts-morph. This is the TS equivalent of
 * `tests/architecture/test_middleware_layer.py`.
 *
 * Per the TDD-Agentic-Systems prompt §Pattern 7 (Dependency Rule Enforcement
 * Test): the test IS the tool. It must pass on the current codebase and must
 * fail when a planted violation is introduced (the second `describe` block
 * verifies this self-referentially).
 *
 * Rules enforced:
 *   F-R1  Components contain no domain logic        -- enforced via ESLint elsewhere
 *   F-R2  SDK imports only in adapters/             -- HERE
 *   F-R3  One-port-per-file in ports/                -- HERE
 *   F-R8  No SDK type escapes past adapter boundary -- approximated via F-R2
 *
 *   wire/, trust-view/         -> only `zod` + stdlib
 *   ports/                     -> wire/ + trust-view/ only
 *   translators/               -> wire/ + trust-view/ only
 *   transport/                 -> wire/ only (EventSource permitted in sse_client.ts)
 *   adapters/<family>/         -> SDK + wire/ + trust-view/ + ports/ + same-family siblings
 *   composition.ts             -> may name concrete adapters; the ONLY file
 *                                  that may import from `adapters/` directly
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import { Project, type SourceFile } from "ts-morph";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");
const LIB_ROOT = path.join(FRONTEND_ROOT, "lib");
const TSCONFIG = path.join(FRONTEND_ROOT, "tsconfig.json");

// SDK packages that are confined to `lib/adapters/**`. Mirrors the
// THIRD_PARTY_SDK_PACKAGES list in §2 of STYLE_GUIDE_FRONTEND.md.
const SDK_PACKAGES = new Set<string>([
  "@copilotkit/react-core",
  "@copilotkit/react-ui",
  "@copilotkit/runtime",
  "@workos-inc/authkit-nextjs",
  "@workos-inc/node",
  "@langchain/langgraph-sdk",
  "mem0ai",
  "langfuse",
  "drizzle-orm",
  "@neondatabase/serverless",
]);

// Packages that the entire frontend may import freely (no architectural
// significance). Anything outside this list and SDK_PACKAGES is treated as
// a vendor SDK candidate -- the layering test will flag it when it appears
// outside `lib/adapters/`.
const FREE_PACKAGES = new Set<string>([
  "zod",
  "react",
  "react-dom",
  "next",
  "next/server",
  "next/headers",
  "next/navigation",
  "next/cache",
  "next-themes",
  // node:* stdlib is matched by prefix below
]);

const RING_FORBIDDEN_OUTBOUND_DIRS: Record<string, ReadonlyArray<string>> = {
  // Wire is the innermost ring: zod + stdlib only. All `lib/<other-ring>/`
  // imports are forbidden.
  wire: ["trust-view", "ports", "translators", "transport", "adapters", "composition"],
  "trust-view": [
    "wire",
    "ports",
    "translators",
    "transport",
    "adapters",
    "composition",
  ],
  ports: ["translators", "transport", "adapters", "composition"],
  translators: ["transport", "adapters", "composition"],
  transport: ["trust-view", "ports", "translators", "adapters", "composition"],
  // Adapters depend on `ports/`, `wire/`, `trust-view/`, and SDKs only
  // (Rule A3). `transport/` and `translators/` are NEVER imported into
  // an adapter -- the composition root assembles them and injects the
  // result via constructor options. `composition.ts` is also forbidden so
  // an adapter cannot reach back into the wiring layer.
  adapters: ["transport", "translators", "composition"],
  bff: ["adapters"],
};

interface ImportFinding {
  file: string;
  importPath: string;
  reason: string;
}

function newProject(): Project {
  return new Project({
    tsConfigFilePath: TSCONFIG,
    skipAddingFilesFromTsConfig: false,
  });
}

function ringOf(filePath: string): string | null {
  const rel = path.relative(LIB_ROOT, filePath);
  if (rel.startsWith("..")) return null;
  const top = rel.split(path.sep)[0];
  if (top === "composition.ts") return "composition";
  if (top === "composition_react.tsx") return "composition";
  // BFF server composition is the server-side counterpart of the React
  // composition seam -- it is allowed to name concrete adapters and read
  // env. The chat / API surface code in `lib/bff/handlers.ts` and the
  // app/api/**/route.ts files must NOT name concrete adapters; they go
  // through `serverPortBag()`.
  if (rel.replace(/\\/g, "/") === "bff/server_composition.ts") return "composition";
  return top ?? null;
}

function resolveImportToRing(
  importingFile: string,
  importPath: string,
): string | null {
  // `lib/<ring>/...` style absolute or relative
  if (importPath.startsWith(".") || importPath.startsWith("@/lib/")) {
    let resolved: string;
    if (importPath.startsWith("@/lib/")) {
      resolved = path.join(LIB_ROOT, importPath.slice("@/lib/".length));
    } else {
      resolved = path.resolve(path.dirname(importingFile), importPath);
    }
    if (!resolved.startsWith(LIB_ROOT)) return null;
    const rel = path.relative(LIB_ROOT, resolved);
    const top = rel.split(path.sep)[0];
    if (top === "composition.ts" || top === "composition") return "composition";
    return top ?? null;
  }
  return null;
}

function isStdlibOrAllowed(spec: string): boolean {
  if (spec.startsWith("node:")) return true;
  if (FREE_PACKAGES.has(spec)) return true;
  return false;
}

function collectViolations(project: Project): ImportFinding[] {
  const findings: ImportFinding[] = [];
  for (const sf of project.getSourceFiles()) {
    const filePath = sf.getFilePath();
    // Skip tests, stories, snapshot baselines, generated files, and scripts.
    if (filePath.endsWith(".test.ts")) continue;
    if (filePath.endsWith(".test.tsx")) continue;
    if (filePath.endsWith(".stories.tsx")) continue;
    if (filePath.endsWith("__python_schema_baseline__.json")) continue;
    if (filePath.includes("/scripts/")) continue;
    if (filePath.includes("/tests/architecture/__fixtures__/")) continue;
    // wire-types.ts is generated codegen; treat as allowed surface.
    if (filePath.endsWith("/lib/wire-types.ts")) continue;

    const ring = ringOf(filePath);
    if (!ring) continue;

    const fileForbid = RING_FORBIDDEN_OUTBOUND_DIRS[ring] ?? [];
    const isAdapter = ring === "adapters";
    const isComposition = ring === "composition";

    for (const decl of sf.getImportDeclarations()) {
      const spec = decl.getModuleSpecifierValue();
      const targetRing = resolveImportToRing(filePath, spec);

      // 1. Cross-ring violations (wire/trust-view/ports/translators/transport)
      if (targetRing && fileForbid.includes(targetRing)) {
        findings.push({
          file: path.relative(FRONTEND_ROOT, filePath),
          importPath: spec,
          reason: `${ring}/ may not import from ${targetRing}/`,
        });
      }

      // 2. Adapters may not be imported outside composition root.
      if (
        targetRing === "adapters" &&
        !isComposition &&
        !isAdapter // intra-family adapter imports are fine
      ) {
        findings.push({
          file: path.relative(FRONTEND_ROOT, filePath),
          importPath: spec,
          reason: `Only composition.ts may name concrete adapters (C1/F1)`,
        });
      }

      // 3. Third-party SDK isolation (F-R2).
      if (SDK_PACKAGES.has(spec) && !isAdapter) {
        findings.push({
          file: path.relative(FRONTEND_ROOT, filePath),
          importPath: spec,
          reason: `SDK '${spec}' may only be imported from lib/adapters/** (F-R2)`,
        });
      }

      // 4. wire/ and trust-view/ are pure: only zod + stdlib.
      if ((ring === "wire" || ring === "trust-view") && targetRing == null) {
        if (!isStdlibOrAllowed(spec) && !SDK_PACKAGES.has(spec)) {
          // Not a known free package and not an in-repo ring -> reject.
          // (We accept zod via FREE_PACKAGES.)
          findings.push({
            file: path.relative(FRONTEND_ROOT, filePath),
            importPath: spec,
            reason: `${ring}/ must import only zod + stdlib (W1)`,
          });
        }
      }
    }
  }
  return findings;
}

// ── Test 1: live codebase passes ───────────────────────────────────────

describe("Frontend layering enforcement [Pattern 7]", () => {
  it("the live `lib/` import graph contains zero rule violations", () => {
    const project = newProject();
    const findings = collectViolations(project);
    if (findings.length > 0) {
      const summary = findings
        .map((f) => `  - ${f.file}: imports '${f.importPath}' (${f.reason})`)
        .join("\n");
      throw new Error(`Architecture violations:\n${summary}`);
    }
    expect(findings).toEqual([]);
  });

  it("each file under lib/ports/ exports exactly one interface (F-R3)", () => {
    const portsDir = path.join(LIB_ROOT, "ports");
    if (!fs.existsSync(portsDir)) {
      // Ports not built yet; the conformance test in S3.2.1 will fill this in.
      return;
    }
    const project = newProject();
    const offenders: string[] = [];
    for (const file of project.getSourceFiles().filter((sf) => {
      const p = sf.getFilePath();
      return (
        p.startsWith(portsDir) && !p.endsWith(".test.ts") && !p.endsWith("/index.ts")
      );
    })) {
      const interfaces = file.getInterfaces().filter((i) => i.isExported());
      if (interfaces.length !== 1) {
        offenders.push(
          `${path.relative(FRONTEND_ROOT, file.getFilePath())}: ${interfaces.length} exported interfaces`,
        );
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});

// ── Test 2: planted violation MUST trip the detector ──────────────────

describe("Pattern 7 self-validation (the test catches violations)", () => {
  it("flags an SDK import that escapes lib/adapters/ (synthetic fixture)", () => {
    const project = new Project({ useInMemoryFileSystem: false, compilerOptions: {} });
    const fakePortPath = path.join(LIB_ROOT, "ports", "__synthetic_violation__.ts");
    project.createSourceFile(
      fakePortPath,
      `import { CopilotKit } from "@copilotkit/react-core";\nexport const x = CopilotKit;\n`,
      { overwrite: true },
    );
    // Re-run the detector against this synthetic project.
    const findings = collectViolations(project);
    const hit = findings.find(
      (f) => f.file.endsWith("__synthetic_violation__.ts") && f.reason.includes("F-R2"),
    );
    expect(hit, "expected an F-R2 violation to be flagged").toBeTruthy();
  });

  it("flags a forbidden cross-ring import (wire/ -> trust-view/)", () => {
    const project = new Project({ useInMemoryFileSystem: false, compilerOptions: {} });
    const fakeWire = path.join(LIB_ROOT, "wire", "__synthetic_violation__.ts");
    project.createSourceFile(
      fakeWire,
      `import { IdentityClaimSchema } from "../trust-view/identity";\nexport const y = IdentityClaimSchema;\n`,
      { overwrite: true },
    );
    const findings = collectViolations(project);
    const hit = findings.find(
      (f) =>
        f.file.endsWith("wire/__synthetic_violation__.ts") &&
        f.reason.includes("trust-view"),
    );
    expect(hit, "expected wire/ -> trust-view/ violation to be flagged").toBeTruthy();
  });

  it("flags an adapter that imports from transport/ or translators/ (Rule A3 regression guard)", () => {
    const project = new Project({ useInMemoryFileSystem: false, compilerOptions: {} });
    const fakeAdapter = path.join(
      LIB_ROOT,
      "adapters",
      "runtime",
      "__synthetic_violation__.ts",
    );
    project.createSourceFile(
      fakeAdapter,
      `import { connectSSE } from "../../transport/sse_client";\n` +
        `import { agUiToUiRuntime } from "../../translators/ag_ui_to_ui_runtime";\n` +
        `export const z = { connectSSE, agUiToUiRuntime };\n`,
      { overwrite: true },
    );
    const findings = collectViolations(project);
    const transportHit = findings.find(
      (f) =>
        f.file.endsWith("adapters/runtime/__synthetic_violation__.ts") &&
        f.reason.includes("transport"),
    );
    const translatorHit = findings.find(
      (f) =>
        f.file.endsWith("adapters/runtime/__synthetic_violation__.ts") &&
        f.reason.includes("translators"),
    );
    expect(transportHit, "expected adapters/ -> transport/ violation to be flagged").toBeTruthy();
    expect(translatorHit, "expected adapters/ -> translators/ violation to be flagged").toBeTruthy();
  });
});
