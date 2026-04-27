/**
 * AG-UI native event wire kernel -- 17 events as a Zod discriminated union.
 *
 * TypeScript / Zod mirror of `agent_ui_adapter/wire/ag_ui_events.py`. Hand-
 * authored (not codegen) per FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE §8.
 * The Python side is the single source of truth; the schema-drift CI
 * (S3.11.1) blocks merges that break parity.
 *
 * Per plan §4.3 Option B / W5: every emitted event carries the originating
 * `trace_id` in `raw_event.trace_id`. The schema does not require `raw_event`
 * to be present (Python: `raw_event: dict | None = None`); the SSE client
 * (X1/X2) is responsible for synthesizing a `RunErrorEvent` if `trace_id`
 * is missing on a structurally-valid event.
 *
 * Per W1: imports `zod` only. Per W3: `z.discriminatedUnion("type", [...])`
 * for variant routing. Per W6: snake_case on the wire. Per W7: schema +
 * inferred type co-export.
 */

import { z } from "zod";

// ── Pinned AG-UI version (parity with Python AGUI_PINNED_VERSION) ─────

export const AGUI_PINNED_VERSION: "0.1.18" = "0.1.18";

// ── Discriminator enum ────────────────────────────────────────────────

export const EventTypeSchema = z.enum([
  "RUN_STARTED",
  "RUN_FINISHED",
  "RUN_ERROR",
  "STEP_STARTED",
  "STEP_FINISHED",
  "TEXT_MESSAGE_START",
  "TEXT_MESSAGE_CONTENT",
  "TEXT_MESSAGE_END",
  "TOOL_CALL_START",
  "TOOL_CALL_ARGS",
  "TOOL_CALL_END",
  "TOOL_RESULT",
  "STATE_SNAPSHOT",
  "STATE_DELTA",
  "MESSAGES_SNAPSHOT",
  "RAW",
  "CUSTOM",
]);
export type EventType = z.infer<typeof EventTypeSchema>;

// ── Common header (raw_event carries trace_id per §4.3 Option B) ──────

const baseFields = {
  timestamp: z.string().datetime().optional(),
  raw_event: z
    .object({
      trace_id: z.string().optional(),
    })
    .passthrough()
    .nullable()
    .default(null),
};

// ── Lifecycle ─────────────────────────────────────────────────────────

export const RunStartedSchema = z
  .object({
    type: z.literal("RUN_STARTED"),
    ...baseFields,
    run_id: z.string(),
    thread_id: z.string(),
  })
  .strict();
export type RunStarted = z.infer<typeof RunStartedSchema>;

export const RunFinishedSchema = z
  .object({
    type: z.literal("RUN_FINISHED"),
    ...baseFields,
    run_id: z.string(),
    thread_id: z.string(),
  })
  .strict();
export type RunFinished = z.infer<typeof RunFinishedSchema>;

export const RunErrorSchema = z
  .object({
    type: z.literal("RUN_ERROR"),
    ...baseFields,
    run_id: z.string(),
    thread_id: z.string(),
    message: z.string(),
    code: z.string().nullable().default(null),
  })
  .strict();
export type RunError = z.infer<typeof RunErrorSchema>;

export const StepStartedSchema = z
  .object({
    type: z.literal("STEP_STARTED"),
    ...baseFields,
    step_name: z.string(),
  })
  .strict();
export type StepStarted = z.infer<typeof StepStartedSchema>;

export const StepFinishedSchema = z
  .object({
    type: z.literal("STEP_FINISHED"),
    ...baseFields,
    step_name: z.string(),
  })
  .strict();
export type StepFinished = z.infer<typeof StepFinishedSchema>;

// ── Text message stream ───────────────────────────────────────────────

export const TextMessageStartSchema = z
  .object({
    type: z.literal("TEXT_MESSAGE_START"),
    ...baseFields,
    message_id: z.string(),
    role: z.literal("assistant"),
  })
  .strict();
export type TextMessageStart = z.infer<typeof TextMessageStartSchema>;

export const TextMessageContentSchema = z
  .object({
    type: z.literal("TEXT_MESSAGE_CONTENT"),
    ...baseFields,
    message_id: z.string(),
    delta: z.string(),
  })
  .strict();
export type TextMessageContent = z.infer<typeof TextMessageContentSchema>;

export const TextMessageEndSchema = z
  .object({
    type: z.literal("TEXT_MESSAGE_END"),
    ...baseFields,
    message_id: z.string(),
  })
  .strict();
export type TextMessageEnd = z.infer<typeof TextMessageEndSchema>;

// ── Tool calls ────────────────────────────────────────────────────────

export const ToolCallStartSchema = z
  .object({
    type: z.literal("TOOL_CALL_START"),
    ...baseFields,
    tool_call_id: z.string(),
    tool_call_name: z.string(),
    parent_message_id: z.string().nullable().default(null),
  })
  .strict();
export type ToolCallStart = z.infer<typeof ToolCallStartSchema>;

export const ToolCallArgsSchema = z
  .object({
    type: z.literal("TOOL_CALL_ARGS"),
    ...baseFields,
    tool_call_id: z.string(),
    delta: z.string(),
  })
  .strict();
export type ToolCallArgs = z.infer<typeof ToolCallArgsSchema>;

export const ToolCallEndSchema = z
  .object({
    type: z.literal("TOOL_CALL_END"),
    ...baseFields,
    tool_call_id: z.string(),
  })
  .strict();
export type ToolCallEnd = z.infer<typeof ToolCallEndSchema>;

export const ToolResultSchema = z
  .object({
    type: z.literal("TOOL_RESULT"),
    ...baseFields,
    tool_call_id: z.string(),
    content: z.string(),
    role: z.literal("tool"),
  })
  .strict();
export type ToolResult = z.infer<typeof ToolResultSchema>;

// ── State ─────────────────────────────────────────────────────────────

export const StateSnapshotSchema = z
  .object({
    type: z.literal("STATE_SNAPSHOT"),
    ...baseFields,
    snapshot: z.record(z.unknown()),
  })
  .strict();
export type StateSnapshot = z.infer<typeof StateSnapshotSchema>;

export const StateDeltaSchema = z
  .object({
    type: z.literal("STATE_DELTA"),
    ...baseFields,
    delta: z.array(z.record(z.unknown())),
  })
  .strict();
export type StateDelta = z.infer<typeof StateDeltaSchema>;

export const MessagesSnapshotSchema = z
  .object({
    type: z.literal("MESSAGES_SNAPSHOT"),
    ...baseFields,
    messages: z.array(z.record(z.unknown())),
  })
  .strict();
export type MessagesSnapshot = z.infer<typeof MessagesSnapshotSchema>;

// ── Special ───────────────────────────────────────────────────────────

export const RawSchema = z
  .object({
    type: z.literal("RAW"),
    ...baseFields,
    event: z.string(),
    source: z.string().nullable().default(null),
  })
  .strict();
export type Raw = z.infer<typeof RawSchema>;

export const CustomSchema = z
  .object({
    type: z.literal("CUSTOM"),
    ...baseFields,
    name: z.string(),
    value: z.record(z.unknown()),
  })
  .strict();
export type Custom = z.infer<typeof CustomSchema>;

// ── Discriminated union (W3) ──────────────────────────────────────────

export const AGUIEventSchema = z.discriminatedUnion("type", [
  RunStartedSchema,
  RunFinishedSchema,
  RunErrorSchema,
  StepStartedSchema,
  StepFinishedSchema,
  TextMessageStartSchema,
  TextMessageContentSchema,
  TextMessageEndSchema,
  ToolCallStartSchema,
  ToolCallArgsSchema,
  ToolCallEndSchema,
  ToolResultSchema,
  StateSnapshotSchema,
  StateDeltaSchema,
  MessagesSnapshotSchema,
  RawSchema,
  CustomSchema,
]);
export type AGUIEvent = z.infer<typeof AGUIEventSchema>;
