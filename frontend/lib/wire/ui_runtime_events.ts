/**
 * UI-runtime event kernel.
 *
 * These are the narrowed shapes the UI runtime (CopilotKit hooks, useFrontendTool,
 * useComponent, useCoAgentStateRender) consumes after translation. They are
 * frontend-only (no Python equivalent) and sit at the boundary between
 * `translators/ag_ui_to_ui_runtime.ts` and the React components.
 *
 * Design contract:
 * - Per F-R7 / W5: every event keeps `trace_id` forwarded from the wire so
 *   correlation survives the AG-UI -> UI-runtime hop.
 * - Per X2: `error_type` is a closed enum so the SSE client can synthesize
 *   `RunErrorEvent` deterministically when wire parsing fails.
 * - Per W1: imports `zod` only; no SDK, no React, no I/O.
 * - Per W3: `z.discriminatedUnion("type", [...])` for variant routing.
 */

import { z } from "zod";

const traceId = z.string().min(1, "trace_id must be non-empty (F-R7 / W5)");

// ── Run lifecycle ─────────────────────────────────────────────────────

export const RunStartedEventSchema = z
  .object({
    type: z.literal("run_started"),
    trace_id: traceId,
    run_id: z.string(),
    thread_id: z.string(),
  })
  .strict();
export type RunStartedEvent = z.infer<typeof RunStartedEventSchema>;

export const RunCompletedEventSchema = z
  .object({
    type: z.literal("run_completed"),
    trace_id: traceId,
    run_id: z.string(),
    thread_id: z.string(),
  })
  .strict();
export type RunCompletedEvent = z.infer<typeof RunCompletedEventSchema>;

export const RunErrorTypeSchema = z.enum([
  "wire_parse_error",
  "auth_error",
  "authorization_error",
  "rate_limit_error",
  "server_error",
  "network_error",
  "cancelled",
]);
export type RunErrorType = z.infer<typeof RunErrorTypeSchema>;

export const RunErrorEventSchema = z
  .object({
    type: z.literal("run_error"),
    trace_id: traceId,
    run_id: z.string(),
    error_type: RunErrorTypeSchema,
    message: z.string(),
  })
  .strict();
export type RunErrorEvent = z.infer<typeof RunErrorEventSchema>;

// ── Chat message stream (F2 streaming markdown) ───────────────────────

export const ChatMessageDeltaEventSchema = z
  .object({
    type: z.literal("chat_message_delta"),
    trace_id: traceId,
    message_id: z.string(),
    delta: z.string().min(1, "delta must be non-empty"),
  })
  .strict();
export type ChatMessageDeltaEvent = z.infer<typeof ChatMessageDeltaEventSchema>;

// ── Step / state render (F6 step meter, F7 model badge) ───────────────

export const StepProgressEventSchema = z
  .object({
    type: z.literal("step_progress"),
    trace_id: traceId,
    step: z.number().int().nonnegative(),
    step_name: z.string(),
  })
  .strict();
export type StepProgressEvent = z.infer<typeof StepProgressEventSchema>;

export const StateRenderEventSchema = z
  .object({
    type: z.literal("state_render"),
    trace_id: traceId,
    key: z.string(),
    value: z.unknown(),
  })
  .strict();
export type StateRenderEvent = z.infer<typeof StateRenderEventSchema>;

// ── Tool renderer request (F5 tool cards via useFrontendTool) ─────────

export const ToolCallRendererRequestSchema = z
  .object({
    trace_id: traceId,
    tool_call_id: z.string(),
    tool_name: z.string(),
    input: z.record(z.unknown()),
    status: z.enum(["running", "completed", "errored"]),
    output: z.union([z.string(), z.record(z.unknown())]).nullable(),
  })
  .strict();
export type ToolCallRendererRequest = z.infer<typeof ToolCallRendererRequestSchema>;

// ── UIRuntime discriminated union ─────────────────────────────────────

export const UIRuntimeEventSchema = z.discriminatedUnion("type", [
  RunStartedEventSchema,
  RunCompletedEventSchema,
  RunErrorEventSchema,
  ChatMessageDeltaEventSchema,
  StepProgressEventSchema,
  StateRenderEventSchema,
]);
export type UIRuntimeEvent = z.infer<typeof UIRuntimeEventSchema>;
