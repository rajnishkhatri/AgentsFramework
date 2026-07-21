/**
 * CollapsibleCoachAnswer — FR-3/4/7 structural tests (jsdom + renderToStaticMarkup).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CollapsibleCoachAnswer } from "./CollapsibleCoachAnswer";
import type { CoachTurn } from "./use_coach";

function turn(
  opts: { pending?: boolean; error?: boolean; markdown?: string } = {},
): CoachTurn {
  const pending = opts.pending ?? false;
  const error = opts.error ?? false;
  return {
    id: "t1",
    user: "Why B?",
    coach: {
      role: "coach",
      markdown: opts.markdown ?? "Look at the comma. Then check the clause.",
      status: pending ? "streaming" : error ? "error" : "complete",
      pending,
      error,
      canRetry: error,
      traceId: null,
    },
  };
}

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("CollapsibleCoachAnswer", () => {
  it("collapsed: summary button with aria-expanded false; body hidden", () => {
    const doc = dom(
      <CollapsibleCoachAnswer
        turn={turn()}
        expanded={false}
        onToggle={() => {}}
      />,
    );
    const btn = doc.querySelector('[data-testid="coach-answer-toggle-t1"]');
    expect(btn?.getAttribute("aria-expanded")).toBe("false");
    expect(btn?.getAttribute("aria-controls")).toBe("coach-answer-body-t1");
    expect(btn?.textContent).toContain("Look at the comma.");
    const body = doc.querySelector('[data-testid="coach-answer-body-t1"]');
    expect(body?.hasAttribute("hidden")).toBe(true);
  });

  it("expanded: body visible; chevron down", () => {
    const doc = dom(
      <CollapsibleCoachAnswer
        turn={turn()}
        expanded={true}
        onToggle={() => {}}
      />,
    );
    expect(
      doc
        .querySelector('[data-testid="coach-answer-toggle-t1"]')
        ?.getAttribute("aria-expanded"),
    ).toBe("true");
    expect(
      doc
        .querySelector('[data-testid="coach-answer-body-t1"]')
        ?.hasAttribute("hidden"),
    ).toBe(false);
  });

  it("FR-20: collapsed chrome is chevron + Coach + truncated summary; no timestamp", () => {
    const doc = dom(
      <CollapsibleCoachAnswer
        turn={turn()}
        expanded={false}
        onToggle={() => {}}
      />,
    );
    const btn = doc.querySelector('[data-testid="coach-answer-toggle-t1"]');
    expect(btn?.textContent).toMatch(/^[▸▾]/);
    expect(btn?.textContent).toContain("Coach");
    expect(
      doc.querySelector('[data-testid="coach-answer-summary-t1"]')?.textContent,
    ).toContain("Look at the comma.");
    expect(btn?.textContent).not.toMatch(/\d{1,2}:\d{2}/);
    expect(doc.querySelector("time")).toBeNull();
  });

  it("FR-3/4: pending/error have no toggle; Retry present on error", () => {
    const pending = dom(
      <CollapsibleCoachAnswer
        turn={turn({ pending: true })}
        expanded={false}
        onToggle={() => {}}
      />,
    );
    expect(
      pending.querySelector('[data-testid="coach-answer-toggle-t1"]'),
    ).toBeNull();
    expect(
      pending
        .querySelector('[data-testid="coach-answer-body-t1"]')
        ?.hasAttribute("hidden"),
    ).toBe(false);

    const errored = dom(
      <CollapsibleCoachAnswer
        turn={turn({ error: true })}
        expanded={false}
        onToggle={() => {}}
        onRetry={() => {}}
      />,
    );
    expect(
      errored.querySelector('[data-testid="coach-answer-toggle-t1"]'),
    ).toBeNull();
    expect(errored.querySelector('[data-testid="coach-retry"]')).not.toBeNull();
  });
});
