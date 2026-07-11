/**
 * C2 soft-gate (FR-5): FLAG-5 Wrap-up `?session=` wire only when
 * `readActiveQuiz` is exported by `quiz_session_store`.
 *
 * Spec: docs/plan/preact-parity-C2-summary-payoff.spec.md §FR-5 / FR-18.
 */

import { describe, expect, it } from "vitest";
import path from "node:path";
import fs from "node:fs";
import { Project, SyntaxKind } from "ts-morph";

const FRONTEND_ROOT = path.resolve(__dirname, "../..");

function readActiveQuizExported(): boolean {
  const storePath = path.join(
    FRONTEND_ROOT,
    "components/quiz/quiz_session_store.ts",
  );
  const src = fs.readFileSync(storePath, "utf8");
  return (
    /export\s+(?:async\s+)?function\s+readActiveQuiz\b/.test(src) ||
    /export\s+\{[^}]*\breadActiveQuiz\b[^}]*\}/.test(src) ||
    /export\s+const\s+readActiveQuiz\b/.test(src)
  );
}

function coachPageImportsReadActiveQuiz(): boolean {
  const pagePath = path.join(
    FRONTEND_ROOT,
    "app/(coach)/learn/coach/page.tsx",
  );
  const project = new Project({
    tsConfigFilePath: path.join(FRONTEND_ROOT, "tsconfig.json"),
    skipAddingFilesFromTsConfig: true,
  });
  const sf = project.addSourceFileAtPath(pagePath);
  return sf.getImportDeclarations().some((imp) =>
    imp.getNamedImports().some((n) => n.getName() === "readActiveQuiz"),
  );
}

describe("C2 FLAG-5 soft-gate (FR-5)", () => {
  it("matches coach/page import state to readActiveQuiz substrate presence", () => {
    const substrate = readActiveQuizExported();
    const imported = coachPageImportsReadActiveQuiz();
    if (!substrate) {
      expect(imported).toBe(false);
    } else {
      expect(imported).toBe(true);
    }
  });

  it("unwraps FLAG-5 test.fail only when substrate + e2e file both exist", () => {
    const substrate = readActiveQuizExported();
    const e2ePath = path.join(
      FRONTEND_ROOT,
      "e2e/learn/validate_epic_ab.spec.ts",
    );
    if (!substrate || !fs.existsSync(e2ePath)) {
      // No e2e assertion when the continuity-fixes e2e is absent.
      expect(true).toBe(true);
      return;
    }
    const src = fs.readFileSync(e2ePath, "utf8");
    // FLAG-5 guard must not remain wrapped in test.fail once both land.
    expect(src).not.toMatch(/test\.fail\([^)]*FLAG-5|FLAG-5[\s\S]*?test\.fail/);
    void SyntaxKind; // keep ts-morph import used if tree-shaken
  });
});
