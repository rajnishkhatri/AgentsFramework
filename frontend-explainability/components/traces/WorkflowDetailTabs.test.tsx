// @vitest-environment happy-dom
/**
 * WorkflowDetailTabs — keyboard/screen-reader contract.
 *
 * Asserts ARIA Authoring Practices conformance for the tablist, plus the
 * default tab + click-to-switch behaviour.
 */
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { WorkflowDetailTabs } from "./WorkflowDetailTabs";

function renderTabs() {
  return render(
    <WorkflowDetailTabs
      timeline={<div data-testid="timeline-body">timeline-body</div>}
      cascade={<div data-testid="cascade-body">cascade-body</div>}
      replay={<div data-testid="replay-body">replay-body</div>}
    />,
  );
}

describe("WorkflowDetailTabs — failure first", () => {
  it("renders three tabs as real <button role='tab'> elements", () => {
    renderTabs();
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.getAttribute("type"))).toEqual([
      "button",
      "button",
      "button",
    ]);
  });
});

describe("WorkflowDetailTabs — acceptance", () => {
  it("defaults to the Timeline tab and renders only its body visibly", () => {
    renderTabs();
    const timeline = screen.getByRole("tab", { name: /timeline/i });
    const cascade = screen.getByRole("tab", { name: /cascade/i });
    expect(timeline.getAttribute("aria-selected")).toBe("true");
    expect(cascade.getAttribute("aria-selected")).toBe("false");
    // The selected panel is visible; the other two are `hidden`.
    const panels = document.querySelectorAll('[role="tabpanel"]');
    const visiblePanels = Array.from(panels).filter(
      (p) => !p.hasAttribute("hidden"),
    );
    expect(visiblePanels).toHaveLength(1);
    expect(visiblePanels[0]?.textContent).toContain("timeline-body");
  });

  it("switches the selected tab + visible panel when clicked", () => {
    renderTabs();
    fireEvent.click(screen.getByRole("tab", { name: /cascade/i }));
    expect(
      screen.getByRole("tab", { name: /cascade/i }).getAttribute("aria-selected"),
    ).toBe("true");
    expect(
      screen.getByRole("tab", { name: /timeline/i }).getAttribute("aria-selected"),
    ).toBe("false");
    const visiblePanels = Array.from(
      document.querySelectorAll('[role="tabpanel"]'),
    ).filter((p) => !p.hasAttribute("hidden"));
    expect(visiblePanels[0]?.textContent).toContain("cascade-body");
  });
});
