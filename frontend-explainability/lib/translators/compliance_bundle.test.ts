/**
 * compliance_bundle translator tests (Sprint 3 review F5 fix).
 *
 * Table-driven coverage of the guardrail-shape matrix recognised by the
 * backend aggregator: prompt_injection (`accepted`), agent_facts
 * (`verified`), output scanner (`stage=output`+`blocked`), plus the
 * empty/malformed cases that must be skipped rather than crash.
 */
import { describe, it, expect } from "vitest";
import { countGuardrails } from "./compliance_bundle";
import type {
  BlackBoxEvent,
  ComplianceBundle,
  CorrelationHealth,
  IntegrityReport,
} from "@/lib/wire/responses";

function makeEvent(
  event_type: string,
  details: Record<string, unknown> = {},
): BlackBoxEvent {
  return {
    event_id: `evt-${Math.random().toString(36).slice(2, 8)}`,
    workflow_id: "wf-test",
    event_type,
    timestamp: "2026-04-26T08:00:00.000Z",
    step: null,
    details,
    integrity_hash: "h",
  };
}

const COMPLETE_HEALTH: CorrelationHealth = {
  has_trace_id: true,
  has_user_id: true,
  has_task_id: true,
  has_agent_id: true,
  missing_keys: [],
};

const CLEAN_INTEGRITY: IntegrityReport = {
  workflow_id: "wf-test",
  chain_valid: true,
  broken_at_event_id: null,
  expected_hash: null,
  actual_hash: null,
};

function makeBundle(events: BlackBoxEvent[]): ComplianceBundle {
  return {
    workflow_id: "wf-test",
    event_count: events.length,
    hash_chain_valid: true,
    bundle_type: "compliance_audit",
    exported_at: "2026-04-26T08:00:01.000Z",
    events,
    identity_cards: {},
    audit_trails: {},
    phase_decisions: [],
    correlation_health: COMPLETE_HEALTH,
    integrity: CLEAN_INTEGRITY,
  };
}

describe("countGuardrails — failure-first", () => {
  it("returns all-zero for an empty bundle", () => {
    expect(countGuardrails(makeBundle([]))).toEqual({
      total: 0,
      pass: 0,
      fail: 0,
    });
  });

  it("returns all-zero when no guardrail events are present", () => {
    expect(
      countGuardrails(
        makeBundle([
          makeEvent("task_started", { agent_id: "cli-agent" }),
          makeEvent("step_executed", { latency_ms: 100 }),
        ]),
      ),
    ).toEqual({ total: 0, pass: 0, fail: 0 });
  });

  it("skips guardrail events whose shape is unrecognised", () => {
    expect(
      countGuardrails(
        makeBundle([
          makeEvent("guardrail_checked", { foo: "bar" }),
        ]),
      ),
    ).toEqual({ total: 0, pass: 0, fail: 0 });
  });
});

describe("countGuardrails — shape matrix", () => {
  it.each([
    {
      label: "prompt_injection accepted",
      details: { accepted: true, guardrail: "prompt_injection" },
      counts: { total: 1, pass: 1, fail: 0 },
    },
    {
      label: "prompt_injection rejected",
      details: { accepted: false, guardrail: "prompt_injection" },
      counts: { total: 1, pass: 0, fail: 1 },
    },
    {
      label: "agent_facts verified",
      details: { verified: true, guardrail: "agent_facts" },
      counts: { total: 1, pass: 1, fail: 0 },
    },
    {
      label: "agent_facts unverified",
      details: { verified: false, guardrail: "agent_facts" },
      counts: { total: 1, pass: 0, fail: 1 },
    },
    {
      label: "output scanner blocked",
      details: { stage: "output", blocked: true },
      counts: { total: 1, pass: 0, fail: 1 },
    },
    {
      label: "output scanner not blocked",
      details: { stage: "output", blocked: false },
      counts: { total: 1, pass: 1, fail: 0 },
    },
  ])("classifies $label correctly", ({ details, counts }) => {
    expect(
      countGuardrails(makeBundle([makeEvent("guardrail_checked", details)])),
    ).toEqual(counts);
  });

  it("aggregates a mixed workflow with all three shapes", () => {
    const counts = countGuardrails(
      makeBundle([
        makeEvent("task_started"),
        makeEvent("guardrail_checked", { verified: true, guardrail: "agent_facts" }),
        makeEvent("guardrail_checked", { accepted: true, guardrail: "prompt_injection" }),
        makeEvent("guardrail_checked", { stage: "output", blocked: true }),
        makeEvent("guardrail_checked", { foo: "bar" }), // skipped
      ]),
    );
    expect(counts).toEqual({ total: 3, pass: 2, fail: 1 });
  });
});
