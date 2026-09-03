/**
 * C-2 — ExamRunnerView text|image branch (FR-P2-11, FR-P2-13).
 * Repo convention: renderToStaticMarkup + JSDOM; createRoot for onError.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { FAKE_OFFICIAL_FORM } from "@/lib/adapters/engine/exam_forms/fixtures/fake_official_form";
import { ExamRunnerView, type ExamRunnerViewProps } from "./ExamRunnerView";
import { toExamItemVM, type ExamItemVM } from "./exam_item_vm";

const noop = (): void => undefined;

function vmFromId(id: string): ExamItemVM {
  const q = FAKE_OFFICIAL_FORM.sections
    .flatMap((s) => s.questions)
    .find((item) => item.id === id);
  if (q == null) throw new Error(`fixture missing ${id}`);
  return toExamItemVM(q);
}

function props(over: Partial<ExamRunnerViewProps> = {}): ExamRunnerViewProps {
  return {
    vm: vmFromId("e-1"),
    selectedLetter: null,
    flagged: false,
    index: 0,
    count: 2,
    answeredCount: 0,
    remainingMs: 60_000,
    fiveMinWarning: false,
    sectionLabel: "English",
    cells: [],
    pendingBlankConfirm: null,
    notSaved: false,
    onSelect: noop,
    onClear: noop,
    onFlag: noop,
    onPrev: noop,
    onNext: noop,
    onJump: noop,
    onSubmit: noop,
    onConfirmSubmit: noop,
    onCancelSubmit: noop,
    ...over,
  };
}

function renderDoc(over: Partial<ExamRunnerViewProps> = {}): Document {
  const html = renderToStaticMarkup(
    React.createElement(ExamRunnerView, props(over)),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("ExamRunnerView — text-first ok item (FR-P2-10 / Test-01)", () => {
  it("renders stem text and four choice buttons, no official image", () => {
    const doc = renderDoc({ vm: vmFromId("e-1") });
    expect(doc.querySelector('[data-testid="exam-runner"]')).not.toBeNull();
    expect(doc.body.textContent).toContain("synthetic stem");
    expect(doc.querySelectorAll('[data-testid^="choice-"]')).toHaveLength(4);
    expect(doc.querySelector("img")).toBeNull();
    expect(doc.body.textContent).not.toMatch(/content unavailable/i);
  });
});

describe("ExamRunnerView — image-necessary item (FR-P2-11)", () => {
  it("renders official <img> in place of the stem plus four choice buttons", () => {
    const vm = vmFromId("m-2");
    const doc = renderDoc({
      vm,
      index: 1,
      count: 2,
      sectionLabel: "Math",
    });
    const img = doc.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toBe(vm.imageUrl);
    expect(img?.getAttribute("alt")).toBe("Question 2 (official image)");
    expect(doc.querySelector('[data-testid="exam-item-stem"]')).toBeNull();
    expect(doc.querySelectorAll('[data-testid^="choice-"]')).toHaveLength(4);
    expect(doc.querySelector('[data-testid="choice-A"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="choice-D"]')).not.toBeNull();
  });
});

describe("ExamRunnerView — failed asset (FR-P2-13)", () => {
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

  it("onError replaces the img with a content-unavailable status", async () => {
    await act(async () => {
      root.render(
        React.createElement(
          ExamRunnerView,
          props({
            vm: vmFromId("m-2"),
            index: 1,
            sectionLabel: "Math",
          }),
        ),
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
    const status = container.querySelector('[role="status"]');
    expect(status?.textContent).toMatch(/content unavailable/i);
  });
});
