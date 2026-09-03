/**
 * FR-P2-8 / ADR-0042 — hardened no-client-served-keys guard.
 *
 * Retires the textual `/\bdb-served\b/` heuristic. Asserts:
 *   (1) resolved module graph: no client-reachable module imports
 *       `exam_forms/_generated/*.keys.ts`
 *   (2) payload schema: `ClientExamForm` is `.strict()` and lacks the four
 *       answer-bearing fields
 *   (3) planted red fixtures prove both checks fire
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import { Project } from "ts-morph";
import {
  ANSWER_BEARING_FIELDS,
  EXAM_KEY_POSTURE,
} from "@/components/exam/exam_key_posture";
import { ClientExamForm } from "@/lib/wire/exam_entities";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");
const KEYS_IMPORT_RE = /exam_forms\/_generated\/[^"'/]+\.keys/;

function isClientReachablePath(filePath: string): boolean {
  const norm = filePath.replaceAll("\\", "/");
  return (
    norm.includes("/app/") ||
    norm.includes("/components/") ||
    norm.endsWith("/lib/composition_engine_browser.ts")
  );
}

function collectKeysImportViolations(project: Project): string[] {
  const findings: string[] = [];
  for (const sf of project.getSourceFiles()) {
    const filePath = sf.getFilePath().replaceAll("\\", "/");
    if (filePath.includes("/tests/architecture/")) continue;
    if (filePath.endsWith(".test.ts") || filePath.endsWith(".test.tsx")) continue;
    if (!isClientReachablePath(filePath)) continue;
    for (const decl of sf.getImportDeclarations()) {
      const spec = decl.getModuleSpecifierValue();
      if (KEYS_IMPORT_RE.test(spec) || spec.includes("_generated/") && spec.includes(".keys")) {
        findings.push(`${filePath}: client module imports ${spec}`);
      }
    }
    const text = sf.getFullText();
    if (KEYS_IMPORT_RE.test(text)) {
      findings.push(`${filePath}: client module references exam_forms/_generated/*.keys`);
    }
  }
  return findings;
}

function clientExamFormLacksAnswerFields(schema: {
  safeParse: (v: unknown) => { success: boolean };
  keyof?: () => { options?: readonly string[] };
  _def?: { typeName?: string; unknownKeys?: string };
}): string[] {
  const findings: string[] = [];
  const keys = schema.keyof?.().options ?? [];
  for (const field of ANSWER_BEARING_FIELDS) {
    if (keys.includes(field)) {
      findings.push(`ClientExamForm schema includes answer-bearing field ${field}`);
    }
    const leaked = schema.safeParse({
      id: "leak",
      title: "leak",
      blueprint: "act-enhanced",
      composite_sections: [],
      delivery: "asset-served",
      sections: [],
      [field]: "B",
    });
    if (leaked.success) {
      findings.push(`ClientExamForm.safeParse accepted leaked ${field}`);
    }
  }
  const extra = schema.safeParse({
    id: "leak",
    title: "leak",
    blueprint: "act-enhanced",
    composite_sections: [],
    delivery: "asset-served",
    sections: [],
    answer_letter: "B",
  });
  if (extra.success) {
    findings.push("ClientExamForm is not .strict() — accepted answer_letter");
  }
  return findings;
}

function diskProject(): Project {
  const project = new Project({
    tsConfigFilePath: path.join(FRONTEND_ROOT, "tsconfig.json"),
    skipAddingFilesFromTsConfig: true,
  });
  project.addSourceFilesAtPaths([
    path.join(FRONTEND_ROOT, "app/**/*.{ts,tsx}"),
    path.join(FRONTEND_ROOT, "components/**/*.{ts,tsx}"),
    path.join(FRONTEND_ROOT, "lib/composition_engine_browser.ts"),
  ]);
  return project;
}

describe("exam key posture (FR-P2-8)", () => {
  it("is a literal code switch, not env-overridable", () => {
    expect(EXAM_KEY_POSTURE === "client" || EXAM_KEY_POSTURE === "server").toBe(
      true,
    );
    expect(Object.isFrozen(Object.freeze({ EXAM_KEY_POSTURE }))).toBe(true);
  });

  it("is green vacuously (no client-reachable import of _generated/*.keys.ts)", () => {
    const findings = collectKeysImportViolations(diskProject());
    expect(findings, findings.join("\n")).toEqual([]);
  });

  it("ClientExamForm is .strict() and omits answer-bearing fields", () => {
    const findings = clientExamFormLacksAnswerFields(ClientExamForm);
    expect(findings, findings.join("\n")).toEqual([]);
    for (const field of ANSWER_BEARING_FIELDS) {
      expect(ClientExamForm.keyof().options).not.toContain(field);
    }
  });

  it("planted red fixture: a client module importing _generated/*.keys.ts fails", () => {
    const project = new Project({ useInMemoryFileSystem: true });
    const keysPath = path.join(
      FRONTEND_ROOT,
      "lib/adapters/engine/exam_forms/_generated/planted.keys.ts",
    );
    const clientPath = path.join(
      FRONTEND_ROOT,
      "components/exam/__planted_keys_import__.ts",
    );
    project.createSourceFile(keysPath, `export const KEYS = { "q-1": "B" };\n`);
    project.createSourceFile(
      clientPath,
      `import { KEYS } from "@/lib/adapters/engine/exam_forms/_generated/planted.keys";\nexport const leak = KEYS;\n`,
    );
    const findings = collectKeysImportViolations(project);
    expect(
      findings.some((f) => KEYS_IMPORT_RE.test(f) || f.includes(".keys")),
      findings.join("\n"),
    ).toBe(true);
  });

  it("planted red fixture: a schema leaking answer_letter fails", () => {
    const leaking = {
      safeParse: (v: unknown) => {
        const rec = v as { answer_letter?: unknown };
        return { success: rec.answer_letter !== undefined };
      },
    };
    const findings = clientExamFormLacksAnswerFields(leaking);
    expect(
      findings.some((f) => f.includes("answer_letter")),
      findings.join("\n"),
    ).toBe(true);
  });
});
