/**
 * B0-6 — synthetic non-©ACT 4-section asset-served fixture + in-memory store.
 * CI substrate for every later lane (FR-P2-14 contract / assertExamFormLoadable).
 */

import { describe, expect, it } from "vitest";
import { assertExamFormLoadable } from "../index";
import { FAKE_OFFICIAL_FORM, FAKE_OFFICIAL_FORM_ID } from "./fake_official_form";
import { FakeAssetStore } from "../../assets/fake_asset_store";

describe("fake_official_form (B0-6)", () => {
  it("is a loadable 4-section asset-served form", () => {
    expect(FAKE_OFFICIAL_FORM.id).toBe(FAKE_OFFICIAL_FORM_ID);
    expect(FAKE_OFFICIAL_FORM.delivery).toBe("asset-served");
    expect(FAKE_OFFICIAL_FORM.composite_sections).toEqual([
      "english",
      "math",
      "reading",
    ]);
    expect(FAKE_OFFICIAL_FORM.sections).toHaveLength(4);
    for (const section of FAKE_OFFICIAL_FORM.sections) {
      expect(section.questions.length).toBeGreaterThanOrEqual(2);
      expect(section.questions.length).toBeLessThanOrEqual(3);
    }
    expect(FAKE_OFFICIAL_FORM.sections.some((s) => s.scale_table !== null)).toBe(
      true,
    );
    const allQs = FAKE_OFFICIAL_FORM.sections.flatMap((s) => s.questions);
    expect(allQs.some((q) => q.image !== null)).toBe(true);
    expect(allQs.some((q) => q.scored === false)).toBe(true);
    expect(
      FAKE_OFFICIAL_FORM.sections.some((s) =>
        s.passages.some((p) => p.image !== null),
      ),
    ).toBe(true);
    expect(() => assertExamFormLoadable(FAKE_OFFICIAL_FORM)).not.toThrow();
  });
});

describe("FakeAssetStore (B0-6)", () => {
  it("round-trips a known key and returns null for an unknown key", async () => {
    const ref = FAKE_OFFICIAL_FORM.sections
      .flatMap((s) => s.questions)
      .find((q) => q.image)?.image;
    expect(ref).toBeTruthy();
    const bytes = new Uint8Array([1, 2, 3]);
    const store = new FakeAssetStore([[ref!, bytes]]);
    expect(await store.has(ref!)).toBe(true);
    expect(await store.getImage(ref!)).toEqual(bytes);
    const missing = { store: "form-image" as const, form_id: "x", key: "nope" };
    expect(await store.has(missing)).toBe(false);
    expect(await store.getImage(missing)).toBeNull();
  });
});
