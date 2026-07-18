import { describe, expect, it } from "vitest";
import { resolveHintChoiceLetter } from "./resolve_hint_choice_letter";

describe("resolveHintChoiceLetter — ADR-0035 moment router", () => {
  it("no pick → null (item-level Gen1 ladder)", () => {
    expect(resolveHintChoiceLetter(null, "B")).toBeNull();
    expect(resolveHintChoiceLetter(undefined, "B")).toBeNull();
    expect(resolveHintChoiceLetter("", "B")).toBeNull();
  });

  it("correct letter → null (no choice-conditional key ladder)", () => {
    expect(resolveHintChoiceLetter("B", "B")).toBeNull();
  });

  it("wrong letter A–D → that letter", () => {
    expect(resolveHintChoiceLetter("A", "B")).toBe("A");
    expect(resolveHintChoiceLetter("C", "B")).toBe("C");
    expect(resolveHintChoiceLetter("D", "A")).toBe("D");
  });

  it("rejects non A–D junk", () => {
    expect(resolveHintChoiceLetter("E", "B")).toBeNull();
    expect(resolveHintChoiceLetter("a", "B")).toBeNull();
  });
});
