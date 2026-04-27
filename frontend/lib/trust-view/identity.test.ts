/**
 * L1 tests for the read-only trust-view kernel (S3.1.2 / Epic 3.1).
 *
 * `trust-view/` exports only `z.infer<...>` types and Zod schemas for parsing
 * inbound trust shapes (W8, F-R6). It MUST NOT export functions that mutate,
 * sign, or verify -- those live in the Python middleware. The frontend can
 * read identity claims and policy decisions, never modify them.
 */

import { describe, expect, it } from "vitest";
import {
  AgentFactsViewSchema,
  IdentityClaimSchema,
  PolicyDecisionViewSchema,
  RunIdentitySchema,
} from "./identity";

// ── IdentityClaim (verified WorkOS claim, narrowed for the UI) ────────

describe("IdentityClaimSchema", () => {
  it("rejects missing sub", () => {
    const r = IdentityClaimSchema.safeParse({ org_id: "o1", roles: ["admin"] });
    expect(r.success).toBe(false);
  });

  it("rejects roles that are not strings", () => {
    const r = IdentityClaimSchema.safeParse({
      sub: "u1",
      org_id: "o1",
      roles: [1],
    });
    expect(r.success).toBe(false);
  });

  it("accepts a complete WorkOS-derived identity claim", () => {
    const v = IdentityClaimSchema.parse({
      sub: "user_01",
      org_id: "org_01",
      roles: ["admin", "beta"],
      email: "alice@example.com",
    });
    expect(v.sub).toBe("user_01");
    expect(v.roles).toContain("admin");
  });
});

// ── AgentFactsView (read-only mirror of trust.models.AgentFacts) ──────

describe("AgentFactsViewSchema [F-R6 read-only]", () => {
  it("rejects payload missing agent_id", () => {
    const r = AgentFactsViewSchema.safeParse({
      agent_name: "Bot",
      owner: "team",
      version: "1.0",
      capabilities: [],
      policies: [],
    });
    expect(r.success).toBe(false);
  });

  it("rejects an unknown status string", () => {
    const r = AgentFactsViewSchema.safeParse({
      agent_id: "a1",
      agent_name: "Bot",
      owner: "team",
      version: "1.0",
      capabilities: [],
      policies: [],
      status: "limbo",
    });
    expect(r.success).toBe(false);
  });

  it("accepts the canonical AgentFacts shape and exposes signature_hash", () => {
    const v = AgentFactsViewSchema.parse({
      agent_id: "a1",
      agent_name: "Bot",
      owner: "team",
      version: "1.0",
      capabilities: [{ name: "write", description: "", parameters: {} }],
      policies: [{ name: "max_tokens", description: "", rules: { value: 4096 } }],
      status: "active",
      signature_hash: "deadbeef",
    });
    expect(v.signature_hash).toBe("deadbeef");
  });
});

// ── PolicyDecisionView (audit_entry signature-bearing) ────────────────

describe("PolicyDecisionViewSchema", () => {
  it("rejects an unknown enforcement value", () => {
    const r = PolicyDecisionViewSchema.safeParse({
      enforcement: "ignore",
      reason: "n/a",
      backend: "embedded",
      audit_entry: {},
    });
    expect(r.success).toBe(false);
  });

  it("accepts each Literal enforcement decision", () => {
    for (const enforcement of ["allow", "deny", "require_approval", "throttle"] as const) {
      const v = PolicyDecisionViewSchema.parse({
        enforcement,
        reason: "test",
        backend: "embedded",
        audit_entry: { rule: "x" },
      });
      expect(v.enforcement).toBe(enforcement);
    }
  });
});

// ── RunIdentity (binds run -> agent -> user) ──────────────────────────

describe("RunIdentitySchema", () => {
  it("rejects missing trace_id (every UI shape carries trace_id, F-R7)", () => {
    const r = RunIdentitySchema.safeParse({
      run_id: "r1",
      thread_id: "t1",
      agent_id: "a1",
      user_id: "u1",
    });
    expect(r.success).toBe(false);
  });

  it("accepts a complete RunIdentity", () => {
    const v = RunIdentitySchema.parse({
      run_id: "r1",
      thread_id: "t1",
      agent_id: "a1",
      user_id: "u1",
      trace_id: "trace-001",
    });
    expect(v.trace_id).toBe("trace-001");
  });
});

// ── Module-shape invariant: only schemas + types, no mutators ─────────

describe("trust-view module shape [W8 / F-R6]", () => {
  it("does not export functions that could mutate or sign", async () => {
    const mod: Record<string, unknown> = await import("./identity");
    // Only Zod schemas (objects with `parse`) are allowed.
    for (const [name, value] of Object.entries(mod)) {
      if (typeof value === "function") {
        throw new Error(
          `trust-view exported function '${name}' -- it is a read-only kernel; ` +
            `signing/verification belongs in the middleware (F-R6).`,
        );
      }
    }
    expect(Object.keys(mod).length).toBeGreaterThan(0);
  });
});
