/**
 * Phase 2.3 — CoachView SSR structural tests (FR-F1/F3/F4, U4; L1 jsdom).
 *
 * Repo convention (no @testing-library/react): renderToStaticMarkup + JSDOM.
 * The run logic is proven in use_coach.test.ts; here we assert the view renders
 * coach turns faithfully. Edge/a11y first: a terminal error shows a RETRY
 * affordance, never a stuck spinner (FR-F4); streaming shows a typing indicator
 * (FR-F3); coach prose lives in a single role="log" aria-live="polite" region
 * (U4).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CoachView } from "./CoachView";
import type { CoachTurn } from "./use_coach";
import type { CoachMessage } from "@/lib/translators/coach_message_vm";

function coach(over: Partial<CoachMessage> = {}): CoachMessage {
  return {
    role: "coach",
    markdown: "Look at the subject–verb link.",
    status: "complete",
    pending: false,
    error: false,
    canRetry: false,
    traceId: "tr-1",
    ...over,
  };
}

function turn(over: Partial<CoachTurn> = {}): CoachTurn {
  return { id: "t1", user: "why is B right?", coach: coach(), ...over };
}

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("CoachView — FR-F4 error shows retry, not a spinner (edge first)", () => {
  it("a terminal error renders a retry control and NO typing indicator", () => {
    const doc = dom(
      <CoachView
        turns={[turn({ coach: coach({ status: "error", error: true, canRetry: true, pending: false, markdown: "stream dropped" }) })]}
        busy={false}
      />,
    );
    expect(doc.querySelector('[data-testid="coach-retry"]'), "retry control").not.toBeNull();
    expect(doc.querySelector('[data-testid="coach-typing"]')).toBeNull();
  });
});

describe("CoachView — FR-F3 streaming typing indicator", () => {
  it("a pending turn renders a typing indicator", () => {
    const doc = dom(
      <CoachView turns={[turn({ coach: coach({ status: "streaming", pending: true }) })]} busy />,
    );
    expect(doc.querySelector('[data-testid="coach-typing"]'), "typing indicator").not.toBeNull();
    expect(doc.querySelector('[data-testid="coach-retry"]')).toBeNull();
  });
});

describe("CoachView — U4 streaming region + FR-F1 turns", () => {
  it("coach prose lives in a single role=log aria-live=polite region", () => {
    const doc = dom(<CoachView turns={[turn()]} busy={false} />);
    const logs = doc.querySelectorAll('[role="log"]');
    expect(logs).toHaveLength(1);
    expect(logs[0]!.getAttribute("aria-live")).toBe("polite");
    expect(logs[0]!.textContent).toContain("subject–verb");
  });

  it("renders the learner ask and the coach reply for each turn", () => {
    const doc = dom(<CoachView turns={[turn()]} busy={false} />);
    expect(doc.querySelector('[data-testid="coach-turn-t1"]'), "turn").not.toBeNull();
    expect(doc.body.textContent).toContain("why is B right?");
    expect(doc.body.textContent).toContain("subject–verb");
  });

  it("empty transcript renders no turns and no error", () => {
    const doc = dom(<CoachView turns={[]} busy={false} />);
    expect(doc.querySelectorAll('[data-testid^="coach-turn-"]')).toHaveLength(0);
    expect(doc.querySelector('[data-testid="coach-retry"]')).toBeNull();
  });
});
