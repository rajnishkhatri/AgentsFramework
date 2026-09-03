/**
 * B0-3 — image-necessary rule (spec §4.1 / decisions.md).
 * A question gets an image iff text_fidelity ∈ {math-notation, low}
 * or its passage is a figure passage. English/Reading `ok` → no image.
 */

import { describe, expect, it } from "vitest";
import { needsImage } from "./exam_image_rule";

describe("needsImage (B0-3 / §4.1)", () => {
  it.each([
    {
      name: "ok fidelity, no passage → no image",
      q: { text_fidelity: "ok" as const },
      passage: undefined,
      want: false,
    },
    {
      name: "math-notation → image",
      q: { text_fidelity: "math-notation" as const },
      passage: undefined,
      want: true,
    },
    {
      name: "low fidelity → image",
      q: { text_fidelity: "low" as const },
      passage: undefined,
      want: true,
    },
    {
      name: "figure passage → image even when text is ok",
      q: { text_fidelity: "ok" as const },
      passage: { is_figure: true },
      want: true,
    },
    {
      name: "English ok, non-figure passage → no image",
      q: { text_fidelity: "ok" as const },
      passage: { is_figure: false },
      want: false,
    },
    {
      name: "Reading ok, no passage → no image",
      q: { text_fidelity: "ok" as const },
      passage: null,
      want: false,
    },
  ])("$name", ({ q, passage, want }) => {
    expect(needsImage(q, passage)).toBe(want);
  });
});
