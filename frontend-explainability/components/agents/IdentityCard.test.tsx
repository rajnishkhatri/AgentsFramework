// @vitest-environment happy-dom
/**
 * IdentityCard — snapshot-by-status (S2.2.2 AC: snapshot per identity status).
 *
 * F-R6: failure-first sentry asserting NO Suspend / Restore / Revoke buttons
 * exist. A regression that adds `<button>Suspend</button>` will fail this
 * test before any reviewer sees the diff.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { IdentityCard } from "./IdentityCard";
import type { AgentCard } from "@/lib/wire/responses";

function makeCard(overrides: Partial<AgentCard>): AgentCard {
  return {
    agent_id: "cli-agent",
    agent_name: "CLI Agent",
    owner: "ops",
    version: "1.0",
    description: "",
    capabilities: [{ name: "shell.run", description: "", parameters: {} }],
    policies: [{ name: "never-rm-rf", description: "", rules: {} }],
    status: "active",
    valid_until: null,
    parent_agent_id: null,
    signature_truncated: "aaaaaaaa…bbbbbbbb",
    signature_verified: true,
    signature_verification_status: "verified",
    created_at: "2026-04-01T00:00:00.000Z",
    updated_at: "2026-04-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("IdentityCard — F-R6 read-only sentry", () => {
  it("never renders Suspend / Restore / Revoke buttons", () => {
    render(<IdentityCard agent={makeCard({})} />);
    const forbidden = /(suspend|restore|revoke|delete|rotate|disable)/i;
    const buttons = screen.queryAllByRole("button");
    const matches = buttons
      .map((b) => b.textContent ?? "")
      .filter((t) => forbidden.test(t));
    expect(matches).toEqual([]);
  });
});

describe("IdentityCard — snapshot per identity status", () => {
  const STATUSES: Array<{
    status: AgentCard["status"];
    verification: AgentCard["signature_verification_status"];
  }> = [
    { status: "active", verification: "verified" },
    { status: "suspended", verification: "failed" },
    { status: "revoked", verification: "failed" },
  ];

  it.each(STATUSES)(
    "renders the $status identity card with $verification verification badge",
    ({ status, verification }) => {
      const { container } = render(
        <IdentityCard
          agent={makeCard({
            status,
            signature_verified: verification === "verified",
            signature_verification_status: verification,
          })}
        />,
      );
      const article = container.querySelector(`[data-status="${status}"]`);
      expect(article).not.toBeNull();
      const badge = container.querySelector(
        `[data-verification-status="${verification}"]`,
      );
      expect(badge).not.toBeNull();
    },
  );

  it("renders an unavailable verification badge when status='unavailable'", () => {
    const { container } = render(
      <IdentityCard
        agent={makeCard({
          status: "active",
          signature_verified: false,
          signature_verification_status: "unavailable",
        })}
      />,
    );
    const badge = container.querySelector(
      "[data-verification-status='unavailable']",
    );
    expect(badge).not.toBeNull();
    expect(badge?.textContent ?? "").toMatch(/unavailable/i);
  });

  it("shows '—' when there are no capabilities", () => {
    render(
      <IdentityCard
        agent={makeCard({ capabilities: [], policies: [] })}
      />,
    );
    expect(screen.getByText(/no capabilities declared/i)).toBeDefined();
    expect(screen.getByText(/no policies attached/i)).toBeDefined();
  });
});
