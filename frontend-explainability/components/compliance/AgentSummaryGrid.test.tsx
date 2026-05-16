// @vitest-environment happy-dom
/**
 * AgentSummaryGrid — failure-first empty state, then acceptance snapshots
 * (S3.2.1 AC: agent identity card summary).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentSummaryGrid } from "./AgentSummaryGrid";
import type { AgentCard } from "@/lib/wire/responses";

function makeAgent(
  overrides: Partial<AgentCard> & Pick<AgentCard, "agent_id">,
): AgentCard {
  const verified = overrides.signature_verified ?? true;
  return {
    agent_id: overrides.agent_id,
    agent_name: overrides.agent_name ?? `${overrides.agent_id}-name`,
    owner: overrides.owner ?? "ops",
    version: overrides.version ?? "1.0",
    description: overrides.description ?? "",
    capabilities: overrides.capabilities ?? [],
    policies: overrides.policies ?? [],
    status: overrides.status ?? "active",
    valid_until: overrides.valid_until ?? null,
    parent_agent_id: overrides.parent_agent_id ?? null,
    signature_truncated: overrides.signature_truncated ?? "aaaa…bbbb",
    signature_verified: verified,
    signature_verification_status:
      overrides.signature_verification_status ??
      (verified ? "verified" : "failed"),
    created_at: overrides.created_at ?? "2026-04-01T00:00:00.000Z",
    updated_at: overrides.updated_at ?? "2026-04-01T00:00:00.000Z",
  };
}

describe("AgentSummaryGrid — failure-first", () => {
  it("renders the empty state when there are no agents", () => {
    render(<AgentSummaryGrid agents={[]} />);
    expect(screen.getByRole("status", { name: /no agents/i })).toBeDefined();
  });
});

describe("AgentSummaryGrid — acceptance", () => {
  it("renders one tile per agent with three-state verification badges", () => {
    const agents = [
      makeAgent({ agent_id: "cli-agent" }),
      makeAgent({
        agent_id: "suspended-agent",
        status: "suspended",
        signature_verified: false,
        signature_verification_status: "failed",
      }),
      makeAgent({
        agent_id: "missing-secret-agent",
        signature_verified: false,
        signature_verification_status: "unavailable",
      }),
    ];
    const { container } = render(<AgentSummaryGrid agents={agents} />);
    const items = container.querySelectorAll("li");
    expect(items).toHaveLength(3);
    expect(
      container.querySelector('[data-status="active"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-status="suspended"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-verification-status="verified"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-verification-status="failed"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-verification-status="unavailable"]'),
    ).not.toBeNull();
  });
});
