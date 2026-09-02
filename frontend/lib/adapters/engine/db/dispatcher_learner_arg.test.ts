/**
 * FR-38 / R4 — learner-scoping is connascence of name, not position.
 *
 * Completeness: every exam EngineDb method is in the dispatcher LEARNER_ARG
 * map. arg0-name: each mapped index is 0 and the EngineDb first parameter is
 * named `learnerId`. Default deny: an exam method missing from the map does
 * not trust a client-supplied learnerId.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { ENGINE_DB_DISPOSITION, type EngineDbMethodName } from "./engine_db_disposition";
import {
  EXAM_ENGINE_DB_METHODS,
  EXAM_LEARNER_ARG,
  resolveExamLearnerArg,
} from "./dispatcher_learner_arg";

const ENGINE_DB_SRC = fs.readFileSync(
  path.join(path.dirname(fileURLToPath(import.meta.url)), "engine_db.ts"),
  "utf8",
);

function dispositionExamMethods(): EngineDbMethodName[] {
  return (Object.keys(ENGINE_DB_DISPOSITION) as EngineDbMethodName[]).filter(
    (name) => name.includes("Exam"),
  );
}

function firstParamName(method: string): string | undefined {
  const match = ENGINE_DB_SRC.match(new RegExp(`${method}\\(\\s*([A-Za-z_][A-Za-z0-9_]*)`));
  return match?.[1];
}

describe("dispatcher LEARNER_ARG — FR-38 (R4)", () => {
  it("maps every exam method (completeness)", () => {
    const examMethods = dispositionExamMethods();
    expect(examMethods).toHaveLength(9);
    expect([...EXAM_ENGINE_DB_METHODS].sort()).toEqual([...examMethods].sort());
    expect(Object.keys(EXAM_LEARNER_ARG).sort()).toEqual([...examMethods].sort());
  });

  it("pins LEARNER_ARG = 0 and names arg0 learnerId", () => {
    for (const method of EXAM_ENGINE_DB_METHODS) {
      expect(EXAM_LEARNER_ARG[method]).toBe(0);
      expect(firstParamName(method)).toBe("learnerId");
    }
  });

  it("denies an exam method missing from the map (default deny)", () => {
    expect(resolveExamLearnerArg("insertExamRun", {})).toBe("deny");
    expect(resolveExamLearnerArg("listSkills" as EngineDbMethodName)).toBeUndefined();
  });
});
