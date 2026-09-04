/**
 * S-I1 / FR-P2-19 — PT2 is an asset-served registry entry; when `_generated`
 * exists the server lists it and getExamFormForClient returns 4 sections
 * parsed under ClientExamForm.strict().
 */

import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { ANSWER_BEARING_FIELDS } from "@/components/exam/exam_key_posture";
import { ClientExamForm } from "@/lib/wire/exam_entities";

import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import {
  getExamFormDelivery,
  listExamForms,
  listRegisteredExamFormIds,
} from "./index";

const PT2 = "act-practice-test-2";
const GENERATED_CLIENT = join(
  dirname(fileURLToPath(import.meta.url)),
  "_generated",
  `${PT2}.client.ts`,
);

describe("S-I1 PT2 asset-served registry (FR-P2-19)", () => {
  it("registers PT2 as asset-served", () => {
    expect(listRegisteredExamFormIds()).toContain(PT2);
    expect(getExamFormDelivery(PT2)).toBe("asset-served");
  });

  // Local-only tier: the ©ACT `_generated/` artifact is gitignored and absent in
  // CI (tasks §"real ©ACT JSON is a local-only test tier"), so this skips there
  // and runs locally once `pnpm convert:official` has produced the artifact.
  it.skipIf(!existsSync(GENERATED_CLIENT))(
    "lists PT2 and returns a 4-section ClientExamForm when _generated exists",
    async () => {
      await import("./generated_official_form");

      expect(listExamForms().map((f) => f.id)).toContain(PT2);

      const db = new InMemoryEngineDb();
      const payload = await db.getExamFormForClient("learner-si1", PT2);
      expect(payload).not.toBeNull();
      const parsed = ClientExamForm.safeParse(payload);
      expect(parsed.success, parsed.success ? "" : String(parsed.error)).toBe(
        true,
      );
      expect(payload!.delivery).toBe("asset-served");
      expect(payload!.sections).toHaveLength(4);
      expect(payload!.sections.map((s) => s.code)).toEqual([
        "english",
        "math",
        "reading",
        "science",
      ]);
      const raw = JSON.stringify(payload);
      for (const field of ANSWER_BEARING_FIELDS) {
        expect(raw).not.toContain(`"${field}"`);
      }
    },
  );
});
