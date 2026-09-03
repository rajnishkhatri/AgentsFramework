/**
 * C-1 — exam-local item VM (FR-P2-10/11).
 * Text-first: imageUrl only when the question carries an AssetRef
 * (image-necessary). String mapping only — no fetch.
 */

import { describe, expect, it } from "vitest";
import { FAKE_OFFICIAL_FORM } from "@/lib/adapters/engine/exam_forms/fixtures/fake_official_form";
import type { ExamQuestion } from "@/lib/wire/exam_entities";
import { toExamItemVM } from "./exam_item_vm";

function questionById(id: string): ExamQuestion {
  const found = FAKE_OFFICIAL_FORM.sections
    .flatMap((s) => s.questions)
    .find((q) => q.id === id);
  if (found == null) throw new Error(`fixture missing ${id}`);
  return found;
}

describe("toExamItemVM (C-1 / FR-P2-10/11)", () => {
  it.each([
    { id: "e-1", wantImage: false, passageLabel: null },
    { id: "r-1", wantImage: false, passageLabel: "A" },
    { id: "m-1", wantImage: false, passageLabel: null },
  ] as const)(
    "ok item $id → stem/choices text, no imageUrl (FR-P2-10)",
    ({ id, wantImage, passageLabel }) => {
      const q = questionById(id);
      const vm = toExamItemVM(q);
      expect(vm.stem).toBe(q.stem);
      expect(vm.choices.map((c) => c.letter)).toEqual(
        q.choices.map((c) => c.letter),
      );
      expect(vm.choices.map((c) => c.label)).toEqual(
        q.choices.map((c) => c.label),
      );
      expect(vm.imageUrl).toBeNull();
      expect(wantImage).toBe(false);
      expect(vm.passageLabel).toBe(passageLabel);
    },
  );

  it("math-notation item → imageUrl from AssetRef (FR-P2-11)", () => {
    const q = questionById("m-2");
    const vm = toExamItemVM(q);
    expect(q.image).toEqual({
      store: "form-image",
      form_id: "fake-official-form",
      key: "math/q-2.png",
    });
    expect(vm.imageUrl).toBe(
      "/api/engine/asset/fake-official-form/math/q-2.png",
    );
    expect(vm.stem).toBe(q.stem);
    expect(vm.choices).toHaveLength(4);
    expect(vm.passageLabel).toBeNull();
  });

  it("figure-passage science item → imageUrl (FR-P2-11)", () => {
    const q = questionById("s-1");
    const vm = toExamItemVM(q);
    expect(q.image).not.toBeNull();
    expect(vm.imageUrl).toBe(
      `/api/engine/asset/${q.image!.form_id}/${q.image!.key}`,
    );
    expect(vm.passageLabel).toBe("P1");
  });

  it("English/Reading ok items on the fixture have no imageUrl", () => {
    const ids = ["e-1", "e-2", "r-1", "r-2"] as const;
    for (const id of ids) {
      expect(toExamItemVM(questionById(id)).imageUrl).toBeNull();
    }
  });
});
