// @vitest-environment happy-dom
/**
 * CorrelationHealthBadge — failure-first "missing user_id" state, then the
 * "complete correlation" acceptance snapshot (S3.2.2 AC).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CorrelationHealthBadge } from "./CorrelationHealthBadge";
import type { CorrelationHealth } from "@/lib/wire/responses";

const COMPLETE: CorrelationHealth = {
  has_trace_id: true,
  has_user_id: true,
  has_task_id: true,
  has_agent_id: true,
  missing_keys: [],
};

const MISSING_USER: CorrelationHealth = {
  has_trace_id: true,
  has_user_id: false,
  has_task_id: true,
  has_agent_id: true,
  missing_keys: ["user_id"],
};

describe("CorrelationHealthBadge — failure-first", () => {
  it('names every missing key explicitly when "user_id" is missing', () => {
    const { container } = render(
      <CorrelationHealthBadge health={MISSING_USER} />,
    );
    const wrapper = container.querySelector(
      '[data-correlation-complete="false"]',
    );
    expect(wrapper).not.toBeNull();
    const userTile = container.querySelector('[data-key="user_id"]');
    expect(userTile).not.toBeNull();
    expect(userTile!.getAttribute("data-present")).toBe("false");
    // The aria label and the inline copy must both name "user_id" so the key
    // is NEVER silently omitted (S3.2.2 AC).
    expect(wrapper!.getAttribute("aria-label")).toContain("user_id");
    expect(screen.getAllByText(/user_id/).length).toBeGreaterThan(0);
  });

  it("each missing key gets its own data-present=false tile", () => {
    const allMissing: CorrelationHealth = {
      has_trace_id: false,
      has_user_id: false,
      has_task_id: false,
      has_agent_id: false,
      missing_keys: ["trace_id", "user_id", "task_id", "agent_id"],
    };
    const { container } = render(
      <CorrelationHealthBadge health={allMissing} />,
    );
    const tiles = container.querySelectorAll('[data-present="false"]');
    expect(tiles).toHaveLength(4);
  });
});

describe("CorrelationHealthBadge — acceptance", () => {
  it("renders the complete state when no keys are missing", () => {
    const { container } = render(
      <CorrelationHealthBadge health={COMPLETE} />,
    );
    const wrapper = container.querySelector(
      '[data-correlation-complete="true"]',
    );
    expect(wrapper).not.toBeNull();
    const present = container.querySelectorAll('[data-present="true"]');
    expect(present).toHaveLength(4);
    expect(screen.getByText(/correlation complete/i)).toBeDefined();
  });
});
