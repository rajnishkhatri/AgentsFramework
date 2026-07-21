import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CoachTriggerPill } from "./CoachTriggerPill";

describe("CoachTriggerPill", () => {
  it("renders floating Coach control with testid", () => {
    const doc = new JSDOM(
      renderToStaticMarkup(
        <CoachTriggerPill onClick={() => {}} />,
      ),
    ).window.document;
    const pill = doc.querySelector("[data-testid='coach-trigger-pill']");
    expect(pill).not.toBeNull();
    expect(pill?.textContent).toContain("Coach");
  });
});
