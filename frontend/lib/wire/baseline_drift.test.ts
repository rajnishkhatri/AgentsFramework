/**
 * Wire schema drift smoke test (Pattern 4 -- Consumer-Driven Contract).
 *
 * Confirms the TS Zod schemas accept the same field SET that the Python
 * Pydantic models declare in `__python_schema_baseline__.json`. This is NOT
 * a full structural diff (the canonical drift CI in S3.11.1 does that); it
 * catches the most common drift -- a field appearing only on one side --
 * cheaply and runs in the L1 budget.
 *
 * Per the TDD-Agentic-Systems prompt §Pattern 4: cross-layer types get
 * producer + consumer contract tests. The Python side is the producer, the
 * TS side is the consumer. This test makes the consumer's expectations
 * explicit.
 */

import { describe, expect, it } from "vitest";
import baseline from "./__python_schema_baseline__.json";
import * as agentProtocol from "./agent_protocol";
import * as aguiEvents from "./ag_ui_events";
import * as domainEvents from "./domain_events";

interface BaselineSchema {
  properties?: Record<string, unknown>;
  required?: string[];
  additionalProperties?: boolean;
}

interface Baseline {
  pinned_agui_version: string;
  schemas: Record<string, BaselineSchema>;
}

const data = baseline as unknown as Baseline;

const schemaIndex: Record<string, { _def: { typeName: string } } & {
  shape?: Record<string, unknown>;
}> = {
  // agent_protocol
  ThreadCreateRequest: agentProtocol.ThreadCreateRequestSchema as never,
  ThreadState: agentProtocol.ThreadStateSchema as never,
  RunCreateRequest: agentProtocol.RunCreateRequestSchema as never,
  RunStateView: agentProtocol.RunStateViewSchema as never,
  HealthResponse: agentProtocol.HealthResponseSchema as never,
  // domain_events
  LLMTokenEmitted: domainEvents.LLMTokenEmittedSchema as never,
  LLMMessageStarted: domainEvents.LLMMessageStartedSchema as never,
  LLMMessageEnded: domainEvents.LLMMessageEndedSchema as never,
  ToolCallStarted: domainEvents.ToolCallStartedSchema as never,
  ToolCallEnded: domainEvents.ToolCallEndedSchema as never,
  ToolResultReceived: domainEvents.ToolResultReceivedSchema as never,
  RunStartedDomain: domainEvents.RunStartedDomainSchema as never,
  RunFinishedDomain: domainEvents.RunFinishedDomainSchema as never,
  StateMutated: domainEvents.StateMutatedSchema as never,
  // ag_ui_events
  RunStarted: aguiEvents.RunStartedSchema as never,
  RunFinished: aguiEvents.RunFinishedSchema as never,
  RunError: aguiEvents.RunErrorSchema as never,
  StepStarted: aguiEvents.StepStartedSchema as never,
  StepFinished: aguiEvents.StepFinishedSchema as never,
  TextMessageStart: aguiEvents.TextMessageStartSchema as never,
  TextMessageContent: aguiEvents.TextMessageContentSchema as never,
  TextMessageEnd: aguiEvents.TextMessageEndSchema as never,
  ToolCallStart: aguiEvents.ToolCallStartSchema as never,
  ToolCallArgs: aguiEvents.ToolCallArgsSchema as never,
  ToolCallEnd: aguiEvents.ToolCallEndSchema as never,
  ToolResult: aguiEvents.ToolResultSchema as never,
  StateSnapshot: aguiEvents.StateSnapshotSchema as never,
  StateDelta: aguiEvents.StateDeltaSchema as never,
  MessagesSnapshot: aguiEvents.MessagesSnapshotSchema as never,
  Raw: aguiEvents.RawSchema as never,
  Custom: aguiEvents.CustomSchema as never,
};

function tsFieldNames(schemaName: string): Set<string> {
  const schema = schemaIndex[schemaName];
  if (!schema) return new Set();
  // Zod ZodObject exposes the shape via `.shape`. For ZodObject in v3 the
  // `_def.shape` is a thunk; reading `.shape` triggers it.
  const shape = (schema as unknown as { shape: Record<string, unknown> }).shape ?? {};
  return new Set(Object.keys(shape));
}

describe("Wire schema baseline parity (TS <-> Python)", () => {
  it("AGUI version is pinned to the baseline value", () => {
    expect(data.pinned_agui_version).toBe(aguiEvents.AGUI_PINNED_VERSION);
  });

  it.each(Object.keys(schemaIndex).sort())(
    "%s exposes every field the Python baseline declares",
    (schemaName) => {
      const baselineFields = Object.keys(
        data.schemas[schemaName]?.properties ?? {},
      );
      const tsFields = tsFieldNames(schemaName);

      const missingInTs = baselineFields.filter((f) => !tsFields.has(f));
      expect(missingInTs, `TS ${schemaName} missing: ${missingInTs.join(", ")}`).toEqual(
        [],
      );
    },
  );

  it.each(Object.keys(schemaIndex).sort())(
    "%s has no extra fields the Python baseline does not declare",
    (schemaName) => {
      const baselineFields = new Set(
        Object.keys(data.schemas[schemaName]?.properties ?? {}),
      );
      const tsFields = tsFieldNames(schemaName);
      const extraInTs = [...tsFields].filter((f) => !baselineFields.has(f));
      expect(extraInTs, `TS ${schemaName} has extras: ${extraInTs.join(", ")}`).toEqual(
        [],
      );
    },
  );
});
