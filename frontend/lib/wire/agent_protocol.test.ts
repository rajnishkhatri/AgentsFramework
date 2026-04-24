/**
 * L1 (Deterministic Foundations) tests for the Agent Protocol wire module.
 *
 * Mirrors the Python source of truth at `agent_ui_adapter/wire/agent_protocol.py`.
 * Per the TDD-Agentic-Systems prompt §Protocol A and Pattern 1 (Property-Based
 * Schema Test): for every model, write rejection tests BEFORE acceptance tests
 * (failure paths first, Anti-Pattern 6 / Check 4). Tests are pure -- no I/O,
 * no network, no SDK imports.
 */

import { describe, expect, it } from "vitest";
import {
  HealthResponseSchema,
  RunCreateRequestSchema,
  RunStateViewSchema,
  ThreadCreateRequestSchema,
  ThreadStateSchema,
} from "./agent_protocol";
import type {
  HealthResponse,
  RunCreateRequest,
  RunStateView,
  ThreadCreateRequest,
  ThreadState,
} from "./agent_protocol";

// ── ThreadCreateRequest ────────────────────────────────────────────────

describe("ThreadCreateRequestSchema", () => {
  // --- rejection paths (failure paths first, FD6.ADAPTER) ---
  it("rejects payload missing user_id", () => {
    const result = ThreadCreateRequestSchema.safeParse({});
    expect(result.success).toBe(false);
  });

  it("rejects payload with extra fields (extra='forbid' parity)", () => {
    const result = ThreadCreateRequestSchema.safeParse({
      user_id: "u1",
      metadata: {},
      surprise: 1,
    });
    expect(result.success).toBe(false);
  });

  it("rejects non-string user_id", () => {
    const result = ThreadCreateRequestSchema.safeParse({ user_id: 123 });
    expect(result.success).toBe(false);
  });

  // --- acceptance ---
  it("accepts a minimal payload and defaults metadata to {}", () => {
    const parsed = ThreadCreateRequestSchema.parse({ user_id: "u1" });
    expect(parsed.user_id).toBe("u1");
    expect(parsed.metadata).toEqual({});
  });

  it("preserves the inferred TypeScript type shape", () => {
    const value: ThreadCreateRequest = { user_id: "u1", metadata: { tag: "x" } };
    expect(ThreadCreateRequestSchema.parse(value)).toEqual(value);
  });
});

// ── ThreadState ────────────────────────────────────────────────────────

describe("ThreadStateSchema", () => {
  it("rejects payload missing thread_id", () => {
    const result = ThreadStateSchema.safeParse({
      user_id: "u1",
      messages: [],
      created_at: "2026-04-24T00:00:00Z",
      updated_at: "2026-04-24T00:00:00Z",
    });
    expect(result.success).toBe(false);
  });

  it("rejects extra fields", () => {
    const result = ThreadStateSchema.safeParse({
      thread_id: "t1",
      user_id: "u1",
      messages: [],
      created_at: "2026-04-24T00:00:00Z",
      updated_at: "2026-04-24T00:00:00Z",
      surprise: true,
    });
    expect(result.success).toBe(false);
  });

  it("accepts a complete payload (snake_case wire, W6)", () => {
    const value: ThreadState = {
      thread_id: "t1",
      user_id: "u1",
      messages: [{ role: "user", content: "hi" }],
      created_at: "2026-04-24T00:00:00Z",
      updated_at: "2026-04-24T00:01:00Z",
    };
    expect(ThreadStateSchema.parse(value)).toEqual(value);
  });
});

// ── RunCreateRequest ───────────────────────────────────────────────────

describe("RunCreateRequestSchema", () => {
  it("rejects payload missing thread_id", () => {
    const r = RunCreateRequestSchema.safeParse({ input: {} });
    expect(r.success).toBe(false);
  });

  it("rejects payload missing input", () => {
    const r = RunCreateRequestSchema.safeParse({ thread_id: "t1" });
    expect(r.success).toBe(false);
  });

  it("accepts agent_id when provided (optional in Python)", () => {
    const v: RunCreateRequest = { thread_id: "t1", input: {}, agent_id: "agent-001" };
    expect(RunCreateRequestSchema.parse(v).agent_id).toBe("agent-001");
  });
});

// ── RunStateView ───────────────────────────────────────────────────────

describe("RunStateViewSchema", () => {
  const base = {
    run_id: "r1",
    thread_id: "t1",
    started_at: "2026-04-24T00:00:00Z",
    completed_at: null,
  };

  it("rejects status not in the Literal union", () => {
    const r = RunStateViewSchema.safeParse({ ...base, status: "weird" });
    expect(r.success).toBe(false);
  });

  it("accepts each Literal status value", () => {
    for (const status of ["running", "completed", "cancelled", "errored"] as const) {
      const v: RunStateView = { ...base, status };
      expect(RunStateViewSchema.parse(v).status).toBe(status);
    }
  });
});

// ── HealthResponse ─────────────────────────────────────────────────────

describe("HealthResponseSchema", () => {
  it("rejects status other than 'ok'", () => {
    const r = HealthResponseSchema.safeParse({ status: "degraded", adapter_version: "0.1" });
    expect(r.success).toBe(false);
  });

  it("accepts the canonical healthy response", () => {
    const v: HealthResponse = { status: "ok", adapter_version: "0.1.0" };
    expect(HealthResponseSchema.parse(v)).toEqual(v);
  });
});
