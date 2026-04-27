/**
 * L1 tests for the sealed-envelope translator.
 *
 * Per FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE §16 and the rule documented in
 * `frontend/lib/README.md`: signed payloads must be passed through bytewise
 * unchanged. The translator's job is to produce a Readonly view + the raw
 * JSON bytes the BFF echoed in, so the round-trip back to middleware never
 * mutates the signature.
 *
 * Anti-Pattern guard:
 *   - FE-AP-6 AUTO-REJECT: no spread/re-serialize. Tests assert that
 *     `bytes` equals the original input bytes character-for-character.
 *   - F-R6 read-only: `parse()` returns a frozen value (any mutation throws).
 */

import { describe, expect, it } from "vitest";
import {
  parseSealedAgentFacts,
  parseSealedPolicyDecision,
  type SealedAgentFactsView,
} from "./sealed_envelope";

const FIXTURE_FACTS_JSON = JSON.stringify({
  agent_id: "a1",
  agent_name: "Bot",
  owner: "team",
  version: "1.0",
  description: "",
  capabilities: [],
  policies: [],
  signed_metadata: {},
  metadata: {},
  status: "active",
  valid_until: null,
  parent_agent_id: null,
  signature_hash: "deadbeef",
});

describe("parseSealedAgentFacts (sealed-envelope rule)", () => {
  it("rejects malformed JSON before any verification (FE-AP-6 guard)", () => {
    expect(() => parseSealedAgentFacts("{not-json")).toThrowError();
  });

  it("rejects payload missing signature_hash (sealed envelopes are signed)", () => {
    const raw = JSON.stringify({
      agent_id: "a1",
      agent_name: "Bot",
      owner: "team",
      version: "1.0",
    });
    expect(() => parseSealedAgentFacts(raw)).toThrowError(/signature_hash/);
  });

  it("preserves the original bytes character-for-character", () => {
    const env = parseSealedAgentFacts(FIXTURE_FACTS_JSON);
    expect(env.bytes).toBe(FIXTURE_FACTS_JSON);
  });

  it("freezes the parsed view so spread/assignment cannot mutate it [F-R6]", () => {
    const env = parseSealedAgentFacts(FIXTURE_FACTS_JSON);
    expect(Object.isFrozen(env.view)).toBe(true);
    expect(() => {
      // @ts-expect-error -- tests that runtime freeze prevents mutation
      env.view.signature_hash = "tampered";
    }).toThrow();
  });

  it("is idempotent on repeat parse (same bytes -> equal view)", () => {
    const a = parseSealedAgentFacts(FIXTURE_FACTS_JSON);
    const b = parseSealedAgentFacts(FIXTURE_FACTS_JSON);
    expect(a.view).toEqual(b.view);
    expect(a.bytes).toBe(b.bytes);
  });

  it("returns a Readonly view typed correctly", () => {
    const env: SealedAgentFactsView = parseSealedAgentFacts(FIXTURE_FACTS_JSON);
    expect(env.view.agent_id).toBe("a1");
  });
});

describe("parseSealedPolicyDecision", () => {
  const FIXTURE = JSON.stringify({
    enforcement: "allow",
    reason: "ok",
    backend: "embedded",
    audit_entry: { rule: "x" },
  });

  it("rejects a policy decision with invalid enforcement", () => {
    const raw = JSON.stringify({
      enforcement: "weird",
      reason: "ok",
      backend: "embedded",
      audit_entry: {},
    });
    expect(() => parseSealedPolicyDecision(raw)).toThrowError();
  });

  it("preserves bytes and freezes the view", () => {
    const env = parseSealedPolicyDecision(FIXTURE);
    expect(env.bytes).toBe(FIXTURE);
    expect(Object.isFrozen(env.view)).toBe(true);
  });
});
