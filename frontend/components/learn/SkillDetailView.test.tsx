/**
 * L1 tests for SkillDetailView — E1a FR-6b/6e/11/12/13/14/16.
 * Repo convention (no @testing-library/react): renderToStaticMarkup + JSDOM
 * for structure; createRoot for interactive FR-12/13/14.
 */

import { describe, expect, it, vi } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { Skill, Tutorial } from "@/lib/wire/engine_entities";
import { toSkillDetailVM } from "@/lib/translators/skill_detail_vm";
import { SkillDetailView } from "./SkillDetailView";

// react-dom/client needs a document in the node environment.
const domGlobal = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "http://localhost/",
});
(
  globalThis as unknown as { window: Window; document: Document }
).window = domGlobal.window as unknown as Window;
(globalThis as unknown as { document: Document }).document = domGlobal.window.document;

const SKILL: Skill = {
  id: "s-punc",
  subject: "act-english",
  key: "punctuation",
  name: "Punctuation",
  share_of_test_pct: 15,
  accent_var: "--color-bucket-punctuation",
  description: "",
  order: 1,
};

function fullTutorial(): Tutorial {
  return {
    id: "tut-1",
    subject: "act-english",
    skill_id: "s-punc",
    body_md: "Run the removal test.",
    examples: ["My kitchen, which provides an alternative to eating out, is small."],
    generated_from: "hand:rajnish@2026-07-11",
    reviewed: true,
    ground_md: "You already use commas.",
    pitfall_md: "A pair vs none flips meaning.",
    question_md: "How do you tell?",
    self_explain_prompt: "When do you think a clause needs commas?",
    worked_example: {
      sentence: "My kitchen, which provides an alternative to eating out, is small.",
      steps: ["Remove.", "Non-essential.", "Fence."],
      answer: "Keep both commas.",
    },
    completion_try: {
      sentence: "The teacher, who grades fairly, is popular.",
      choices: [
        { text: "Keep both commas", correct: true },
        { text: "Delete the commas", correct: false },
      ],
      why: "Still stands → keep both.",
    },
    annotated_examples: [
      {
        pre: "My kitchen",
        clause: "which provides an alternative to eating out",
        post: " is small.",
        essential: false,
        callouts: ["remove it → still works"],
      },
    ],
  };
}

function ssr(vm: ReturnType<typeof toSkillDetailVM>): Document {
  const html = renderToStaticMarkup(<SkillDetailView vm={vm} />);
  return new JSDOM(html).window.document;
}

describe("SkillDetailView — structural FRs", () => {
  it("FR-11: exactly one opener marker; no color-dot sequence", () => {
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: fullTutorial(),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    const doc = ssr(vm);
    expect(doc.querySelectorAll('[data-testid="opener-marker"]')).toHaveLength(1);
    expect(doc.body.textContent).not.toMatch(/●●●|●●○/);
  });

  it("FR-6b: callout body byte-equal to misconception tag; no Fix node", () => {
    const tag = "deleting commas to shorten a which-clause";
    const vm = toSkillDetailVM({
      context: "returning",
      tutorial: fullTutorial(),
      skill: SKILL,
      misconceptionTag: tag,
      dueSkills: [{ skillId: "s-gram", name: "Usage" }],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    const doc = ssr(vm);
    expect(doc.querySelector('[data-testid="callout-body"]')!.textContent).toBe(
      tag,
    );
    expect(doc.body.textContent).not.toMatch(/\bFix\b/);
  });

  it("FR-6e / FR-16: returning rail has dueChecklist + coachEntry; no accuracyStat", () => {
    const vm = toSkillDetailVM({
      context: "returning",
      tutorial: fullTutorial(),
      skill: SKILL,
      misconceptionTag: "a tag",
      dueSkills: [{ skillId: "s-gram", name: "Usage" }],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    const doc = ssr(vm);
    expect(doc.querySelector('[data-testid="block-dueChecklist"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="block-coachEntry"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="block-accuracyStat"]')).toBeNull();
  });
});

describe("SkillDetailView — interactive FRs (createRoot)", () => {
  function mount(vm: ReturnType<typeof toSkillDetailVM>, spies?: {
    onAttemptRecord?: () => void;
    onSchedulerReview?: () => void;
  }): HTMLElement {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    act(() => {
      root.render(
        <SkillDetailView
          vm={vm}
          {...(spies?.onAttemptRecord
            ? { onAttemptRecord: spies.onAttemptRecord }
            : {})}
          {...(spies?.onSchedulerReview
            ? { onSchedulerReview: spies.onSchedulerReview }
            : {})}
        />,
      );
    });
    return host;
  }

  it("FR-12: local grade + no attemptRepo/scheduler spy calls", () => {
    const onAttemptRecord = vi.fn();
    const onSchedulerReview = vi.fn();
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: fullTutorial(),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    const host = mount(vm, { onAttemptRecord, onSchedulerReview });
    const choice = host.querySelector(
      '[data-testid="try-choice-0"]',
    ) as HTMLButtonElement;
    act(() => {
      choice.click();
    });
    expect(host.querySelector('[data-testid="try-feedback"]')).not.toBeNull();
    const cta = host.querySelector(
      '[data-testid="practice-skill-cta"]',
    ) as HTMLAnchorElement;
    expect(cta.getAttribute("href")).toBe("/learn/quiz?focus=s-punc");
    expect(onAttemptRecord).not.toHaveBeenCalled();
    expect(onSchedulerReview).not.toHaveBeenCalled();
  });

  it("FR-13: wrong pick does not change subsequent blocks", () => {
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: fullTutorial(),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    const host = mount(vm);
    const before = host.querySelectorAll("[data-testid^='block-']").length;
    const wrong = host.querySelector(
      '[data-testid="try-choice-1"]',
    ) as HTMLButtonElement;
    act(() => {
      wrong.click();
    });
    const after = host.querySelectorAll("[data-testid^='block-']").length;
    expect(after).toBe(before);
    expect(host.querySelector('[data-testid="try-again"]')).not.toBeNull();
  });

  it("FR-14: note echoes in rule; empty note → no echo", () => {
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: fullTutorial(),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    const host = mount(vm);
    expect(host.querySelector('[data-testid="note-echo"]')).toBeNull();
    const input = host.querySelector(
      '[data-testid="self-explain-input"]',
    ) as HTMLTextAreaElement;
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value",
      )!.set!;
      nativeInputValueSetter.call(input, "when you can remove it");
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(host.querySelector('[data-testid="note-echo"]')!.textContent).toContain(
      "when you can remove it",
    );
  });
});
