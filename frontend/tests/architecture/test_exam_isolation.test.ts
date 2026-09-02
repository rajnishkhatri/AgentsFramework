/**
 * FR-26 / FR-41 — exam-module isolation guard (ADR-0040).
 *
 * Authored red-before-green, ahead of any `components/exam/**` product code.
 * Asserts the *resolved* module graph (type-only + dynamic `import()`):
 *   - no edge between `components/exam/**` / `exam_run_repo` and
 *     quiz / scheduler / `skill_state` in either direction;
 *   - no `upsertSkillState` write from exam code.
 *
 * Green vacuously over an empty exam tree. A planted in-memory fixture proves
 * the detector fails on a forbidden edge (Pattern 7).
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import { Project, SyntaxKind } from "ts-morph";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");
const TSCONFIG = path.join(FRONTEND_ROOT, "tsconfig.json");

export interface ExamIsolationFinding {
  file: string;
  specifier: string;
  reason: string;
}

const EXAM_PATH_RE = /(?:^|\/)components\/exam(?:\/|$)|exam_run_repo/;
const FORBIDDEN_COUNTERPART_RE =
  /(?:^|\/)components\/quiz(?:\/|$)|(?:^|\/)adapters\/engine\/scheduler(?:\/|$)|skill_state/;
const SKILL_STATE_WRITE_RE = /\bupsertSkillState\b/;

function isExamSide(filePath: string): boolean {
  const rel = filePath.replace(/\\/g, "/");
  return EXAM_PATH_RE.test(rel);
}

function isForbiddenCounterpart(filePath: string): boolean {
  const rel = filePath.replace(/\\/g, "/");
  return FORBIDDEN_COUNTERPART_RE.test(rel);
}

function resolveSpec(fromFile: string, spec: string): string | null {
  if (spec.startsWith("@/")) {
    return path.join(FRONTEND_ROOT, spec.slice(2));
  }
  if (spec.startsWith(".")) {
    return path.resolve(path.dirname(fromFile), spec);
  }
  return null;
}

export function collectExamIsolationViolations(
  project: Project,
): ExamIsolationFinding[] {
  const findings: ExamIsolationFinding[] = [];
  for (const sf of project.getSourceFiles()) {
    const filePath = sf.getFilePath();
    if (filePath.includes("/tests/architecture/")) continue;
    if (filePath.endsWith(".test.ts") || filePath.endsWith(".test.tsx")) continue;

    const specs: string[] = [];
    for (const decl of sf.getImportDeclarations()) {
      specs.push(decl.getModuleSpecifierValue());
    }
    for (const call of sf.getDescendantsOfKind(SyntaxKind.CallExpression)) {
      const expr = call.getExpression();
      if (expr.getKind() === SyntaxKind.ImportKeyword) {
        const arg = call.getArguments()[0];
        if (arg && arg.getKind() === SyntaxKind.StringLiteral) {
          specs.push(arg.asKindOrThrow(SyntaxKind.StringLiteral).getLiteralValue());
        }
      }
    }

    for (const spec of specs) {
      const resolved = resolveSpec(filePath, spec);
      const resolvedNorm = (resolved ?? spec).replace(/\\/g, "/");
      if (isExamSide(filePath) && isForbiddenCounterpart(resolvedNorm)) {
        findings.push({
          file: filePath,
          specifier: spec,
          reason: "exam → quiz/scheduler/skill_state",
        });
      }
      if (isForbiddenCounterpart(filePath) && isExamSide(resolvedNorm)) {
        findings.push({
          file: filePath,
          specifier: spec,
          reason: "quiz/scheduler/skill_state → exam",
        });
      }
    }

    if (isExamSide(filePath) && SKILL_STATE_WRITE_RE.test(sf.getFullText())) {
      findings.push({
        file: filePath,
        specifier: "upsertSkillState",
        reason: "exam writes skill_state",
      });
    }
  }
  return findings;
}

function diskProject(): Project {
  return new Project({
    tsConfigFilePath: TSCONFIG,
    skipAddingFilesFromTsConfig: false,
  });
}

describe("test_exam_isolation (FR-26/FR-41)", () => {
  it("is green vacuously over the current tree (no forbidden exam edges)", () => {
    const findings = collectExamIsolationViolations(diskProject());
    expect(findings, findings.map((f) => `${f.file}: ${f.reason}`).join("\n")).toEqual(
      [],
    );
  });

  it("planted red fixture: exam → quiz edge is flagged", () => {
    const project = new Project({ useInMemoryFileSystem: true });
    const examFile = path.join(FRONTEND_ROOT, "components/exam/__planted_edge__.ts");
    const quizFile = path.join(FRONTEND_ROOT, "components/quiz/__planted_peer__.ts");
    project.createSourceFile(quizFile, `export const quizPeer = true;\n`);
    project.createSourceFile(
      examFile,
      `import { quizPeer } from "@/components/quiz/__planted_peer__";\nexport const x = quizPeer;\n`,
    );
    const findings = collectExamIsolationViolations(project);
    const hit = findings.find((f) => f.reason.includes("exam →"));
    expect(hit, "expected a forbidden exam → quiz edge").toBeTruthy();
  });

  it("planted red fixture: type-only + dynamic import edges are flagged", () => {
    const project = new Project({ useInMemoryFileSystem: true });
    const examFile = path.join(FRONTEND_ROOT, "components/exam/__planted_dyn__.ts");
    project.createSourceFile(
      examFile,
      `import type { QuizView } from "@/components/quiz/QuizView";\n` +
        `export async function load() {\n` +
        `  return import("@/lib/adapters/engine/scheduler/fsrs_scheduler");\n` +
        `}\n` +
        `export type T = QuizView;\n`,
    );
    const findings = collectExamIsolationViolations(project);
    expect(
      findings.length,
      "type-only and dynamic imports must resolve",
    ).toBeGreaterThan(0);
  });
});
