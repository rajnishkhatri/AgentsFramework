/**
 * Sealed-envelope translator -- pure (T1).
 *
 * Frontend mirror of `agent_ui_adapter/translators/sealed_envelope.py`. Per
 * `frontend/lib/README.md`, the sealed-envelope rule states that any payload
 * carrying a cryptographic signature MUST be passed through bytewise
 * unchanged. This translator's job is to:
 *
 *   1. Validate the inbound JSON against the read-only `trust-view/` schema.
 *   2. Return a `Readonly<view>` AND the original JSON bytes the caller
 *      received, so the BFF can echo the bytes back to middleware without
 *      ever calling `JSON.stringify` on a parsed object (which would
 *      reorder keys and break the signature).
 *
 * The `view` is `Object.freeze`-d so accidental `view.signature_hash = ...`
 * mutations throw at runtime in addition to being a TS error.
 *
 * Imports: only `wire/` and `trust-view/`.
 */

import type { AgentFactsView, PolicyDecisionView } from "../trust-view/identity";
import {
  AgentFactsViewSchema,
  PolicyDecisionViewSchema,
} from "../trust-view/identity";

export type SealedAgentFactsView = {
  readonly view: Readonly<AgentFactsView>;
  readonly bytes: string;
};

export type SealedPolicyDecisionView = {
  readonly view: Readonly<PolicyDecisionView>;
  readonly bytes: string;
};

export function parseSealedAgentFacts(bytes: string): SealedAgentFactsView {
  const json: unknown = JSON.parse(bytes);
  const parsed = AgentFactsViewSchema.parse(json);
  if (!parsed.signature_hash || parsed.signature_hash.length === 0) {
    throw new Error(
      "AgentFacts envelope missing signature_hash -- not a sealed payload",
    );
  }
  const frozen = Object.freeze(parsed);
  return Object.freeze({ view: frozen, bytes });
}

export function parseSealedPolicyDecision(
  bytes: string,
): SealedPolicyDecisionView {
  const json: unknown = JSON.parse(bytes);
  const parsed = PolicyDecisionViewSchema.parse(json);
  const frozen = Object.freeze(parsed);
  return Object.freeze({ view: frozen, bytes });
}
