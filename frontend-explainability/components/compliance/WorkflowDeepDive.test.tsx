// @vitest-environment happy-dom
/**
 * WorkflowDeepDive — failure-first "missing user_id" snapshot, then the
 * "complete correlation" acceptance snapshot (S3.2.2 AC).
 *
 * The deep-dive component itself does not consume `correlation_health` (the
 * page-level CorrelationHealthBadge does that); these snapshots therefore
 * focus on the four-quadrant join: Recording / Identity / Validation /
 * Reasoning rendered from a stub `ComplianceBundle`.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { WorkflowDeepDive } from "./WorkflowDeepDive";
import type {
  AgentCard,
  BlackBoxEvent,
  ComplianceBundle,
  CorrelationHealth,
  DecisionRecord,
} from "@/lib/wire/responses";

function makeAgent(id: string, verified: boolean): AgentCard {
  return {
    agent_id: id,
    agent_name: `${id}-name`,
    owner: "ops",
    version: "1.0",
    description: "",
    capabilities: [],
    policies: [],
    status: "active",
    valid_until: null,
    parent_agent_id: null,
    signature_truncated: "aa…bb",
    signature_verified: verified,
    signature_verification_status: verified ? "verified" : "failed",
    created_at: "2026-04-01T00:00:00.000Z",
    updated_at: "2026-04-01T00:00:00.000Z",
  };
}

function makeEvent(
  type: string,
  details: Record<string, unknown> = {},
): BlackBoxEvent {
  return {
    event_id: `evt-${Math.random().toString(36).slice(2, 8)}`,
    workflow_id: "wf-test",
    event_type: type,
    timestamp: "2026-04-26T08:00:00.000Z",
    step: null,
    details,
    integrity_hash: "h",
  };
}

function makeDecision(phase: string, description: string): DecisionRecord {
  return {
    workflow_id: "wf-test",
    phase,
    description,
    alternatives: [],
    rationale: "r",
    confidence: 0.9,
    timestamp: "2026-04-26T08:00:01.000Z",
  };
}

function makeBundle(
  health: CorrelationHealth,
  overrides: Partial<ComplianceBundle> = {},
): ComplianceBundle {
  return {
    workflow_id: "wf-test",
    event_count: 3,
    hash_chain_valid: true,
    bundle_type: "compliance_audit",
    exported_at: "2026-04-26T08:00:02.000Z",
    events: [
      makeEvent("task_started", { agent_id: "cli-agent" }),
      makeEvent("guardrail_checked", {
        guardrail: "prompt_injection",
        accepted: true,
      }),
      makeEvent("task_completed", { status: "success" }),
    ],
    identity_cards: { "cli-agent": makeAgent("cli-agent", true) },
    audit_trails: {},
    phase_decisions: [makeDecision("routing", "picked gpt-4o")],
    correlation_health: health,
    integrity: {
      workflow_id: "wf-test",
      chain_valid: true,
      broken_at_event_id: null,
      expected_hash: null,
      actual_hash: null,
    },
    ...overrides,
  };
}

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

describe("WorkflowDeepDive — failure-first", () => {
  it("renders all four quadrants even when correlation is incomplete", () => {
    const { container } = render(
      <WorkflowDeepDive bundle={makeBundle(MISSING_USER)} />,
    );
    expect(container.querySelector('[data-quadrant="recording"]')).not.toBeNull();
    expect(container.querySelector('[data-quadrant="identity"]')).not.toBeNull();
    expect(container.querySelector('[data-quadrant="validation"]')).not.toBeNull();
    expect(container.querySelector('[data-quadrant="reasoning"]')).not.toBeNull();
  });

  it("flags an unverified agent in the identity quadrant", () => {
    const bundle = makeBundle(COMPLETE, {
      identity_cards: { "bad-agent": makeAgent("bad-agent", false) },
    });
    const { container } = render(<WorkflowDeepDive bundle={bundle} />);
    const identity = container.querySelector('[data-quadrant="identity"]');
    expect(identity).not.toBeNull();
    expect(identity!.textContent).toContain("verification failed");
    expect(
      identity!.querySelector('[data-verification-status="failed"]'),
    ).not.toBeNull();
  });

  it("surfaces broken_at_event_id and expected/actual hashes when chain is tampered", () => {
    const tampered = makeBundle(COMPLETE, {
      hash_chain_valid: false,
      integrity: {
        workflow_id: "wf-test",
        chain_valid: false,
        broken_at_event_id: "evt-2",
        expected_hash: "a".repeat(64),
        actual_hash: "b".repeat(64),
      },
    });
    const { container } = render(<WorkflowDeepDive bundle={tampered} />);
    const evidence = container.querySelector(
      '[data-testid="recording-break-evidence"]',
    );
    expect(evidence).not.toBeNull();
    expect(evidence!.textContent).toContain("evt-2");
    // Truncated hashes are shown so operators can compare without scrolling.
    expect(evidence!.textContent).toContain("aaaaaaaa");
    expect(evidence!.textContent).toContain("bbbbbbbb");
  });

  it("hides the break-evidence panel when the chain is valid", () => {
    const bundle = makeBundle(COMPLETE);
    const { container } = render(<WorkflowDeepDive bundle={bundle} />);
    expect(
      container.querySelector('[data-testid="recording-break-evidence"]'),
    ).toBeNull();
  });

  it("renders a guardrail empty-state when no guardrail events exist", () => {
    const bundle = makeBundle(COMPLETE, { events: [] });
    const { container } = render(<WorkflowDeepDive bundle={bundle} />);
    const validation = container.querySelector('[data-quadrant="validation"]');
    expect(validation).not.toBeNull();
    expect(validation!.textContent).toContain("No guardrail checks");
  });
});

describe("WorkflowDeepDive — acceptance", () => {
  it("renders all four quadrants with their drill-in links on a fully-correlated workflow", () => {
    const { container } = render(
      <WorkflowDeepDive bundle={makeBundle(COMPLETE)} />,
    );
    const recordingLink = container.querySelector(
      '[data-quadrant="recording"] a[href="/traces/wf-test"]',
    );
    expect(recordingLink).not.toBeNull();

    const reasoningLink = container.querySelector(
      '[data-quadrant="reasoning"] a[href="/decisions/wf-test"]',
    );
    expect(reasoningLink).not.toBeNull();

    const identityAgent = container.querySelector('[data-agent="cli-agent"]');
    expect(identityAgent).not.toBeNull();
    expect(identityAgent!.textContent).toContain("verified");

    const validation = container.querySelector('[data-quadrant="validation"]');
    expect(validation!.textContent).toContain("Pass / Fail");

    const reasoning = container.querySelector('[data-quadrant="reasoning"]');
    expect(reasoning!.textContent).toContain("picked gpt-4o");
  });
});
