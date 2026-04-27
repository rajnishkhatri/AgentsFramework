/**
 * trust-view -- read-only Zod schemas + types for trust shapes consumed by
 * the UI. This module is the frontend mirror of `trust/models.py` minus the
 * mutators. Per F-R6 / W8 it MUST NOT export functions that mutate, sign, or
 * verify -- those live in the Python middleware. The frontend can read
 * identity claims and policy decisions, never modify them.
 *
 * Per W1: imports `zod` only. No I/O, no React, no SDK.
 *
 * The only allowed exports are:
 *   - Zod schemas (so the BFF route handlers can `safeParse` inbound trust
 *     data before handing it to the UI)
 *   - `z.infer<...>` types (so React components can type their props)
 *
 * Anything function-shaped here is a bug; `identity.test.ts` enforces this.
 */

import { z } from "zod";

// ── IdentityClaim (verified WorkOS claim, narrowed for the UI) ────────

export const IdentityClaimSchema = z
  .object({
    sub: z.string(),
    org_id: z.string().nullable().default(null),
    roles: z.array(z.string()).default([]),
    email: z.string().nullable().default(null),
  })
  .strict();
export type IdentityClaim = z.infer<typeof IdentityClaimSchema>;

// ── AgentFactsView (read-only mirror of trust.models.AgentFacts) ──────
//
// Mirrors the Python `AgentFacts` shape EXCEPT we never expose mutators
// (no model_copy, no signature recompute). Signed fields land here
// bytewise unchanged so the BFF can echo them back to the middleware
// without breaking the signature (sealed-envelope rule, frontend/lib/README.md).

const CapabilityViewSchema = z
  .object({
    name: z.string(),
    description: z.string().default(""),
    parameters: z.record(z.unknown()).default({}),
  })
  .strict();
export type CapabilityView = z.infer<typeof CapabilityViewSchema>;

const PolicyViewSchema = z
  .object({
    name: z.string(),
    description: z.string().default(""),
    rules: z.record(z.unknown()).default({}),
  })
  .strict();
export type PolicyView = z.infer<typeof PolicyViewSchema>;

const IdentityStatusSchema = z.enum(["active", "suspended", "revoked"]);
export type IdentityStatusView = z.infer<typeof IdentityStatusSchema>;

export const AgentFactsViewSchema = z
  .object({
    agent_id: z.string(),
    agent_name: z.string(),
    owner: z.string(),
    version: z.string(),
    description: z.string().default(""),
    capabilities: z.array(CapabilityViewSchema).default([]),
    policies: z.array(PolicyViewSchema).default([]),
    signed_metadata: z.record(z.unknown()).default({}),
    metadata: z.record(z.unknown()).default({}),
    status: IdentityStatusSchema.default("active"),
    valid_until: z.string().nullable().default(null),
    parent_agent_id: z.string().nullable().default(null),
    signature_hash: z.string().default(""),
    created_at: z.string().optional(),
    updated_at: z.string().optional(),
  })
  .strict();
export type AgentFactsView = z.infer<typeof AgentFactsViewSchema>;

// ── PolicyDecisionView (audit_entry signature-bearing) ────────────────

export const PolicyDecisionViewSchema = z
  .object({
    enforcement: z.enum(["allow", "deny", "require_approval", "throttle"]),
    reason: z.string(),
    backend: z.enum(["embedded", "opa", "cedar", "yaml"]),
    audit_entry: z.record(z.unknown()),
  })
  .strict();
export type PolicyDecisionView = z.infer<typeof PolicyDecisionViewSchema>;

// ── RunIdentity (binds run -> agent -> user with trace_id) ────────────

export const RunIdentitySchema = z
  .object({
    run_id: z.string(),
    thread_id: z.string(),
    agent_id: z.string(),
    user_id: z.string(),
    trace_id: z.string().min(1, "trace_id is required (F-R7)"),
  })
  .strict();
export type RunIdentity = z.infer<typeof RunIdentitySchema>;
