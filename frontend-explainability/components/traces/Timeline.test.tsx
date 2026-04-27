// @vitest-environment happy-dom
/**
 * Timeline + EventDetailPanel rendering tests.
 *
 * Failure-first: empty-frames empty-state asserted before any happy-path row.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Timeline } from "./Timeline";
import { EventDetailPanel } from "./EventDetailPanel";
import type { TimelineFrame } from "@/lib/translators/event_to_timeline";

const SAMPLE_FRAME: TimelineFrame = {
  id: "evt-1",
  parentId: null,
  label: "Task started",
  startMs: 0,
  durationMs: 500,
  color: "primary",
  kind: "task",
  step: null,
  details: { task_input: "hello" },
};

describe("Timeline — failure-first", () => {
  it("renders the empty state when frames is empty", () => {
    render(<Timeline frames={[]} />);
    expect(screen.getByRole("status", { name: /no events/i })).toBeDefined();
  });

  it("does not render an ordered list when frames is empty", () => {
    const { container } = render(<Timeline frames={[]} />);
    expect(container.querySelector("ol")).toBeNull();
  });
});

describe("Timeline — acceptance", () => {
  it("renders one li per frame as an accessible list", () => {
    render(<Timeline frames={[SAMPLE_FRAME]} />);
    expect(
      screen.getByRole("list", { name: /workflow event timeline/i }),
    ).toBeDefined();
    expect(screen.getAllByText("Task started").length).toBeGreaterThan(0);
  });
});

describe("EventDetailPanel — failure-first", () => {
  it("renders the no-event placeholder when frame is null", () => {
    render(<EventDetailPanel frame={null} />);
    expect(screen.getByText(/no event selected/i)).toBeDefined();
    expect(screen.getByText(/click any bar/i)).toBeDefined();
  });
});

describe("EventDetailPanel — acceptance", () => {
  it("renders kind, label, id, and details for a selected frame", () => {
    render(<EventDetailPanel frame={SAMPLE_FRAME} />);
    expect(screen.getByText("task")).toBeDefined();
    expect(screen.getByText(/^Task started$/)).toBeDefined();
    expect(screen.getByText("evt-1")).toBeDefined();
    expect(screen.getByText("task_input")).toBeDefined();
    expect(screen.getByText("hello")).toBeDefined();
  });
});
