/**
 * Agent Protocol wire models -- TypeScript / Zod mirror of
 * `agent_ui_adapter/wire/agent_protocol.py` (the single source of truth).
 *
 * Per W1: this module imports only `zod` and stdlib. No SDK, no React, no I/O.
 * Per W6: snake_case on the wire (matches Pydantic JSON output).
 * Per W7: schema const + inferred type co-export so consumers spell either.
 *
 * If you change a shape here, regenerate the Python <-> TS schema baseline
 * via `make wire-schema-snapshot` (S3.11.1) so the drift CI stays green.
 */

import { z } from "zod";

// ── ThreadCreateRequest ────────────────────────────────────────────────

export const ThreadCreateRequestSchema = z
  .object({
    user_id: z.string(),
    metadata: z.record(z.unknown()).default({}),
  })
  .strict();

export type ThreadCreateRequest = z.infer<typeof ThreadCreateRequestSchema>;

// ── ThreadState ────────────────────────────────────────────────────────

export const ThreadStateSchema = z
  .object({
    thread_id: z.string(),
    user_id: z.string(),
    messages: z.array(z.record(z.unknown())).default([]),
    created_at: z.string(),
    updated_at: z.string(),
  })
  .strict();

export type ThreadState = z.infer<typeof ThreadStateSchema>;

// ── RunCreateRequest ───────────────────────────────────────────────────

export const RunCreateRequestSchema = z
  .object({
    thread_id: z.string(),
    input: z.record(z.unknown()),
    agent_id: z.string().nullish(),
  })
  .strict();

export type RunCreateRequest = z.infer<typeof RunCreateRequestSchema>;

// ── RunStateView ───────────────────────────────────────────────────────

export const RunStateViewSchema = z
  .object({
    run_id: z.string(),
    thread_id: z.string(),
    status: z.enum(["running", "completed", "cancelled", "errored"]),
    started_at: z.string(),
    completed_at: z.string().nullable(),
  })
  .strict();

export type RunStateView = z.infer<typeof RunStateViewSchema>;

// ── HealthResponse ─────────────────────────────────────────────────────

export const HealthResponseSchema = z
  .object({
    status: z.literal("ok"),
    adapter_version: z.string(),
  })
  .strict();

export type HealthResponse = z.infer<typeof HealthResponseSchema>;
