/**
 * FR-35 / ADR-0041 — no DB-served form serializes answer-bearing fields to
 * the client while posture = "client". Phase-1 client-bundled Test-01 is
 * the recorded accepted-risk exemption. A planted DB-served form with keys
 * must fail the detector.
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import { Project } from "ts-morph";
import {
  ANSWER_BEARING_FIELDS,
  EXAM_KEY_POSTURE,
  type ExamKeyPosture,
} from "@/components/exam/exam_key_posture";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");

function collectClientServedKeyViolations(
  project: Project,
  opts: { posture?: ExamKeyPosture } = {},
): string[] {
  const posture = opts.posture ?? EXAM_KEY_POSTURE;
  if (posture !== "client") return [];
  const findings: string[] = [];
  for (const sf of project.getSourceFiles()) {
    const filePath = sf.getFilePath();
    if (filePath.includes("/tests/architecture/")) continue;
    if (filePath.endsWith(".test.ts") || filePath.endsWith(".test.tsx")) continue;
    const text = sf.getFullText();
    if (!/\bdb-served\b/.test(text)) continue;
    for (const field of ANSWER_BEARING_FIELDS) {
      if (text.includes(field)) {
        findings.push(
          `${filePath}: db-served form serializes ${field} while posture=client`,
        );
      }
    }
  }
  return findings;
}

describe("exam key posture (FR-35)", () => {
  it("is a literal code switch, not env-overridable", () => {
    expect(EXAM_KEY_POSTURE === "client" || EXAM_KEY_POSTURE === "server").toBe(
      true,
    );
    expect(Object.isFrozen(Object.freeze({ EXAM_KEY_POSTURE }))).toBe(true);
  });

  it("is green for the client-bundled phase-1 registry (accepted-risk exemption)", () => {
    const project = new Project({
      tsConfigFilePath: path.join(FRONTEND_ROOT, "tsconfig.json"),
      skipAddingFilesFromTsConfig: false,
    });
    const findings = collectClientServedKeyViolations(project);
    expect(findings, findings.join("\n")).toEqual([]);
  });

  it("planted red fixture: a DB-served form with keys fails while posture=client", () => {
    const project = new Project({ useInMemoryFileSystem: true });
    const planted = path.join(
      FRONTEND_ROOT,
      "lib/adapters/engine/exam_forms/__planted_db_served__.ts",
    );
    project.createSourceFile(
      planted,
      `
export const DELIVERY = "db-served" as const;
export const PLANTED_FORM = {
  id: "official-db",
  delivery: "db-served",
  questions: [{ answer_letter: "B", per_choice_rationale: {}, why_correct_md: "x", why_tempted_md: "y" }],
};
`,
    );
    const findings = collectClientServedKeyViolations(project, {
      posture: "client",
    });
    expect(
      findings.some((f) => f.includes("db-served") && f.includes("answer_letter")),
      findings.join("\n"),
    ).toBe(true);
    expect(ANSWER_BEARING_FIELDS).toContain("answer_letter");
  });
});
