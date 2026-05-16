// @vitest-environment happy-dom
/**
 * AgentCatalog — failure-first empty state, then capability search.
 *
 * S2.2.2 AC: "Capability search test asserting the empty-string query returns
 * the full list" -- this is the single most important behavioural property of
 * the search box, so it gets a dedicated failure-first test.
 */
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AgentCatalog } from "./AgentCatalog";
import type { AgentCard } from "@/lib/wire/responses";

function makeAgent(overrides: Partial<AgentCard> & Pick<AgentCard, "agent_id">): AgentCard {
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
    signature_verified: overrides.signature_verified ?? true,
    signature_verification_status:
      overrides.signature_verification_status ??
      ((overrides.signature_verified ?? true) ? "verified" : "failed"),
    created_at: overrides.created_at ?? "2026-04-01T00:00:00.000Z",
    updated_at: overrides.updated_at ?? "2026-04-01T00:00:00.000Z",
  };
}

const CLI = makeAgent({
  agent_id: "cli-agent",
  capabilities: [
    { name: "shell.run", description: "", parameters: {} },
    { name: "file.read", description: "", parameters: {} },
  ],
});
const DEV = makeAgent({
  agent_id: "dev-agent",
  capabilities: [{ name: "code.review", description: "", parameters: {} }],
});

describe("AgentCatalog — failure-first", () => {
  it("renders the empty state when the registry is empty", () => {
    render(<AgentCatalog agents={[]} />);
    expect(screen.getByRole("status", { name: /no agents/i })).toBeDefined();
  });
});

describe("AgentCatalog — capability search", () => {
  it("renders the full list on initial mount (empty query)", () => {
    render(<AgentCatalog agents={[CLI, DEV]} />);
    expect(screen.getByRole("link", { name: /cli-agent/i })).toBeDefined();
    expect(screen.getByRole("link", { name: /dev-agent/i })).toBeDefined();
  });

  it("filters by substring on capability name", () => {
    render(<AgentCatalog agents={[CLI, DEV]} />);
    const input = screen.getByLabelText(/filter agents by capability/i);
    fireEvent.change(input, { target: { value: "shell" } });
    expect(screen.getByRole("link", { name: /cli-agent/i })).toBeDefined();
    expect(screen.queryByRole("link", { name: /dev-agent/i })).toBeNull();
  });

  it("clearing the query restores the full list (empty-string => all)", () => {
    render(<AgentCatalog agents={[CLI, DEV]} />);
    const input = screen.getByLabelText(/filter agents by capability/i);
    fireEvent.change(input, { target: { value: "shell" } });
    fireEvent.change(input, { target: { value: "" } });
    expect(screen.getByRole("link", { name: /cli-agent/i })).toBeDefined();
    expect(screen.getByRole("link", { name: /dev-agent/i })).toBeDefined();
  });
});
