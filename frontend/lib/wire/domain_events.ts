/**
 * Internal canonical domain events emitted by the Python `AgentRuntime.run()`.
 *
 * TypeScript / Zod mirror of `agent_ui_adapter/wire/domain_events.py` (single
 * source of truth). The frontend rarely consumes these directly -- AG-UI is
 * the public surface -- but the adapter conformance tests round-trip domain
 * events through the wire kernel to prove the schemas align byte-for-byte.
 *
 * Per W1: zod + stdlib only. Per W5: every event carries `trace_id`.
 * Per W3: discriminator-style union (here we use `z.union` because Python's
 * domain events have no `type` discriminator field -- the dispatcher uses
 * `isinstance`. The TS union mirrors that and is parsed structurally).
 */

import { z } from "zod";

// ── Common header ─────────────────────────────────────────────────────

const traceId = z.string().min(1, "trace_id must be non-empty (W5)");
const timestamp = z.string().datetime().optional();

// ── LLM lifecycle ─────────────────────────────────────────────────────

export const LLMTokenEmittedSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    message_id: z.string(),
    delta: z.string(),
  })
  .strict();
export type LLMTokenEmitted = z.infer<typeof LLMTokenEmittedSchema>;

export const LLMMessageStartedSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    message_id: z.string(),
  })
  .strict();
export type LLMMessageStarted = z.infer<typeof LLMMessageStartedSchema>;

export const LLMMessageEndedSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    message_id: z.string(),
  })
  .strict();
export type LLMMessageEnded = z.infer<typeof LLMMessageEndedSchema>;

// ── Tool lifecycle ────────────────────────────────────────────────────

export const ToolCallStartedSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    tool_call_id: z.string(),
    tool_name: z.string(),
    args_json: z.string(),
  })
  .strict();
export type ToolCallStarted = z.infer<typeof ToolCallStartedSchema>;

export const ToolCallEndedSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    tool_call_id: z.string(),
  })
  .strict();
export type ToolCallEnded = z.infer<typeof ToolCallEndedSchema>;

export const ToolResultReceivedSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    tool_call_id: z.string(),
    result: z.string(),
  })
  .strict();
export type ToolResultReceived = z.infer<typeof ToolResultReceivedSchema>;

// ── Run lifecycle ─────────────────────────────────────────────────────

export const RunStartedDomainSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    run_id: z.string(),
    thread_id: z.string(),
  })
  .strict();
export type RunStartedDomain = z.infer<typeof RunStartedDomainSchema>;

export const RunFinishedDomainSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    run_id: z.string(),
    thread_id: z.string(),
    error: z.string().nullable().default(null),
  })
  .strict();
export type RunFinishedDomain = z.infer<typeof RunFinishedDomainSchema>;

// ── State mutation (snapshot or JSON Patch delta) ─────────────────────

export const StateMutatedSchema = z
  .object({
    trace_id: traceId,
    timestamp,
    snapshot: z.record(z.unknown()).nullable().default(null),
    delta: z.array(z.record(z.unknown())).nullable().default(null),
  })
  .strict();
export type StateMutated = z.infer<typeof StateMutatedSchema>;

// ── DomainEvent union (parity with Python `DomainEvent` alias) ────────
//
// Note: Python uses isinstance dispatch, so the wire shapes have no `type`
// discriminator. We use `z.union` (linear matching) here. The TS translator
// also dispatches structurally.

export const DomainEventSchema = z.union([
  LLMTokenEmittedSchema,
  LLMMessageStartedSchema,
  LLMMessageEndedSchema,
  ToolCallStartedSchema,
  ToolCallEndedSchema,
  ToolResultReceivedSchema,
  RunStartedDomainSchema,
  RunFinishedDomainSchema,
  StateMutatedSchema,
]);

export type DomainEvent =
  | LLMTokenEmitted
  | LLMMessageStarted
  | LLMMessageEnded
  | ToolCallStarted
  | ToolCallEnded
  | ToolResultReceived
  | RunStartedDomain
  | RunFinishedDomain
  | StateMutated;
