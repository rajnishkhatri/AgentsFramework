// @vitest-environment happy-dom
/**
 * ReplayScrubber — scrubber-only behaviour (Sprint 4 Replay surface).
 *
 * The scrubber MUST be purely client-side: every datum comes from the
 * already-fetched ReplayFrame[] passed in as props.  These tests exercise
 * the empty state, default frame, and slider/button progression -- they
 * do NOT mount any network code.
 */
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReplayScrubber } from "./ReplayScrubber";
import type { ReplayFrame } from "@/lib/translators/events_to_replay_frames";

function makeFrame(overrides: Partial<ReplayFrame> & { index: number }): ReplayFrame {
  return {
    index: overrides.index,
    event_id: overrides.event_id ?? `evt-${overrides.index}`,
    event_type: overrides.event_type ?? "step_executed",
    timestamp: overrides.timestamp ?? "2026-04-26T08:00:00.000Z",
    active_agent: overrides.active_agent ?? "cli-agent",
    active_model: overrides.active_model ?? "gpt-4o",
    current_step: overrides.current_step ?? 0,
    last_input: overrides.last_input ?? null,
    last_output: overrides.last_output ?? null,
    params: overrides.params ?? {},
  };
}

describe("ReplayScrubber — failure first", () => {
  it("renders the empty state when no frames are provided", () => {
    render(<ReplayScrubber frames={[]} />);
    expect(screen.getByRole("status", { name: /no replay frames/i })).toBeDefined();
  });
});

describe("ReplayScrubber — acceptance", () => {
  const FRAMES: ReplayFrame[] = [
    makeFrame({ index: 0, event_type: "task_started" }),
    makeFrame({ index: 1, event_type: "model_selected" }),
    makeFrame({ index: 2, event_type: "task_completed" }),
  ];

  it("starts on frame 1 of N and renders the snapshot", () => {
    render(<ReplayScrubber frames={FRAMES} />);
    expect(screen.getByText(/frame 1 of 3/i)).toBeDefined();
    const snapshot = screen.getByTestId("replay-snapshot");
    expect(snapshot.textContent).toContain("task_started");
  });

  it("advances to the next frame when the slider moves", () => {
    render(<ReplayScrubber frames={FRAMES} />);
    const slider = screen.getByRole("slider", { name: /replay position/i });
    fireEvent.change(slider, { target: { value: "2" } });
    expect(screen.getByText(/frame 3 of 3/i)).toBeDefined();
    const snapshot = screen.getByTestId("replay-snapshot");
    expect(snapshot.textContent).toContain("task_completed");
  });

  it("Next button advances by one and disables at the end", () => {
    render(<ReplayScrubber frames={FRAMES} />);
    const next = screen.getByRole("button", { name: /next/i });
    fireEvent.click(next);
    expect(screen.getByText(/frame 2 of 3/i)).toBeDefined();
    fireEvent.click(next);
    expect(screen.getByText(/frame 3 of 3/i)).toBeDefined();
    expect(next.hasAttribute("disabled")).toBe(true);
  });
});
