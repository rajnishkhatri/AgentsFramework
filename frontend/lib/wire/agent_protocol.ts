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
    // Optional client-minted id (== the agent/checkpointer thread_id) so the
    // durable row keys by the same id the resume path reads. Absent → the
    // store mints its own. A provisional title flows via
    // `metadata.first_message`.
    thread_id: z.string().nullable().default(null),
    metadata: z.record(z.unknown()).default({}),
  })
  .strict();

export type ThreadCreateRequest = z.infer<typeof ThreadCreateRequestSchema>;
/**
 * Pre-parse shape: `thread_id`/`metadata` are optional (the schema defaults
 * them). The BFF passes a fully-parsed `ThreadCreateRequest`; internal callers
 * (tests, the client create helper) may omit the defaulted fields.
 */
export type ThreadCreateRequestInput = z.input<
  typeof ThreadCreateRequestSchema
>;

// ── ThreadState ────────────────────────────────────────────────────────

export const ThreadStateSchema = z
  .object({
    thread_id: z.string(),
    user_id: z.string(),
    // Sidebar label (Phase 3): deterministic from the first message,
    // user-renamable. archived_at is the soft-delete tombstone.
    title: z.string().default("New chat"),
    messages: z.array(z.record(z.unknown())).default([]),
    created_at: z.string(),
    updated_at: z.string(),
    archived_at: z.string().nullable().default(null),
  })
  .strict();

export type ThreadState = z.infer<typeof ThreadStateSchema>;

// ── ThreadListResponse / ThreadRenameRequest (Phase 3 sidebar) ──────────

export const ThreadListResponseSchema = z
  .object({
    threads: z.array(ThreadStateSchema).default([]),
    next_cursor: z.string().nullable().default(null),
  })
  .strict();
export type ThreadListResponse = z.infer<typeof ThreadListResponseSchema>;

export const ThreadRenameRequestSchema = z
  .object({
    title: z.string().min(1).max(200),
  })
  .strict();
export type ThreadRenameRequest = z.infer<typeof ThreadRenameRequestSchema>;

// ── ThreadAppendRequest (durable-transcript persist seam) ───────────────
//
// BFF-internal contract for `POST /api/threads/[id]/messages`: one completed
// turn persisted into the durable thread store. `turn_id` makes a retried POST
// idempotent. Not a Python-mirrored wire model (the persist seam is the BFF's
// own durable store, F-R9) — so it is intentionally NOT in the drift baseline.
export const ThreadAppendRequestSchema = z
  .object({
    user: z.string(),
    assistant: z.string(),
    turn_id: z.string().min(1),
  })
  .strict();
export type ThreadAppendRequest = z.infer<typeof ThreadAppendRequestSchema>;

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

// ── Task understanding edit (Phase 4 soft-gate card) ──────────────────
//
// Mirrors agent_ui_adapter/wire/agent_protocol.py
// TaskUnderstandingEditRequest. Bounds = components gates minus lexical
// grounding (user_edited skips it); trace_id echoed verbatim (F-R7).

export const TaskUnderstandingEditRequestSchema = z
  .object({
    trace_id: z.string().min(1),
    restated_intent: z.string().min(1).max(600),
    success_conditions: z.array(z.string().min(1).max(200)).min(2).max(7),
  })
  .strict();
export type TaskUnderstandingEditRequest = z.infer<
  typeof TaskUnderstandingEditRequestSchema
>;

// ── Memory panel (Phase 3) ─────────────────────────────────────────────
// Mirror of agent_ui_adapter/wire/agent_protocol.py MemoryItem /
// MemoryListResponse / MemoryCreateRequest. snake_case on the wire (W6).
// The panel shows the OWNER their own content by design; the privacy
// invariant (no content in logs/carriers) is unaffected. No user_id field on
// the create request — the subject is the verified bearer identity
// (cross-user-leak guard).

export const MemoryTypeSchema = z.enum([
  "semantic",
  "episodic",
  "procedural",
]);
export type MemoryType = z.infer<typeof MemoryTypeSchema>;

export const MemoryItemSchema = z
  .object({
    key: z.string(),
    type: MemoryTypeSchema.nullable().default(null),
    content: z.string(),
    salience: z.number().nullable().default(null),
  })
  .strict();
export type MemoryItem = z.infer<typeof MemoryItemSchema>;

export const MemoryListResponseSchema = z
  .object({
    items: z.array(MemoryItemSchema).default([]),
  })
  .strict();
export type MemoryListResponse = z.infer<typeof MemoryListResponseSchema>;

export const MemoryCreateRequestSchema = z
  .object({
    content: z.string().min(1).max(2000),
    type: MemoryTypeSchema.default("semantic"),
    key: z.string().max(200).nullable().default(null),
    // Optional salience (A3 provenance tiers): omitted → stored unmarked.
    salience: z.number().min(0).max(1).nullable().default(null),
  })
  .strict();
export type MemoryCreateRequest = z.infer<typeof MemoryCreateRequestSchema>;

// Body of PATCH /api/memory/{key} — soft-suppress / un-suppress one of the
// caller's own memories (chat-persistence Phase B, D5 reject). `suppressed:
// true` stops the memory being recalled/injected while RETAINING the row for
// audit; `false` un-suppresses (reversible). BFF-internal contract (the
// suppress hop is BFF→middleware over the bearer token; not in the strict
// drift baseline, like the other memory request models).
export const MemorySuppressRequestSchema = z
  .object({
    suppressed: z.boolean(),
  })
  .strict();
export type MemorySuppressRequest = z.infer<typeof MemorySuppressRequestSchema>;
