/**
 * C-3 — ExamPassageBlock (FR-P2-12).
 * Lookup by the current question's passage label; figure image when present;
 * nothing for Math (no passages).
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { FAKE_OFFICIAL_FORM } from "@/lib/adapters/engine/exam_forms/fixtures/fake_official_form";
import type { ExamPassage } from "@/lib/wire/exam_entities";
import { ExamPassageBlock } from "./ExamPassageBlock";

function section(code: "math" | "reading" | "science") {
  const found = FAKE_OFFICIAL_FORM.sections.find((s) => s.code === code);
  if (found == null) throw new Error(`fixture missing ${code}`);
  return found;
}

const TEXT_PASSAGE: ExamPassage = {
  label: "A",
  title: "Passage A",
  intro: "A synthetic reading intro.",
  text: "The town held a meeting about the bridge.",
  image: null,
  question_numbers: [1, 2],
};

function renderDoc(props: {
  passages: readonly ExamPassage[];
  passageLabel: string | null;
}): Document {
  const html = renderToStaticMarkup(React.createElement(ExamPassageBlock, props));
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("ExamPassageBlock (C-3 / FR-P2-12)", () => {
  it("renders the matching text passage for the current question label", () => {
    const doc = renderDoc({
      passages: [TEXT_PASSAGE],
      passageLabel: "A",
    });
    const root = doc.querySelector('[data-testid="exam-passage"]');
    expect(root).not.toBeNull();
    expect(root?.className).toContain("@container");
    expect(doc.body.textContent).toContain("Passage A");
    expect(doc.body.textContent).toContain("A synthetic reading intro.");
    expect(doc.body.textContent).toContain(
      "The town held a meeting about the bridge.",
    );
    expect(doc.querySelector("img")).toBeNull();
  });

  it("renders a figure image when the passage carries one", () => {
    const science = section("science");
    const doc = renderDoc({
      passages: science.passages,
      passageLabel: "P1",
    });
    expect(doc.body.textContent).toContain("Figure 1");
    expect(doc.body.textContent).toContain("A synthetic figure passage.");
    const img = doc.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toBe(
      "/api/engine/asset/fake-official-form/science%2Fp-figure.png",
    );
    expect(img?.getAttribute("alt")).toMatch(/figure|passage|official/i);
  });

  it("renders nothing for Math (no passages)", () => {
    const math = section("math");
    expect(math.passages).toEqual([]);
    const html = renderToStaticMarkup(
      React.createElement(ExamPassageBlock, {
        passages: math.passages,
        passageLabel: null,
      }),
    );
    expect(html).toBe("");
  });

  it("renders nothing when the label does not match a passage", () => {
    const html = renderToStaticMarkup(
      React.createElement(ExamPassageBlock, {
        passages: [TEXT_PASSAGE],
        passageLabel: "Z",
      }),
    );
    expect(html).toBe("");
  });
});

describe("ExamPassageBlock — failed figure asset (FR-P2-13)", () => {
  let container: HTMLDivElement;
  let root: Root;
  const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    root.unmount();
    container.remove();
  });

  it("onError replaces the figure img with a content-unavailable status", async () => {
    const science = section("science");
    await act(async () => {
      root.render(
        React.createElement(ExamPassageBlock, {
          passages: science.passages,
          passageLabel: "P1",
        }),
      );
    });
    await flush();
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    await act(async () => {
      img?.dispatchEvent(new Event("error", { bubbles: true }));
    });
    await flush();
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toMatch(/content unavailable/i);
  });
});
