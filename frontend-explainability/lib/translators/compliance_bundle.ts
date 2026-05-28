/**
 * compliance_bundle translator (Sprint 3 review F5 fix).
 *
 * Pure helpers that turn a `ComplianceBundle` into the view-models
 * consumed by `WorkflowDeepDive`.  Domain/data-transformation logic does
 * NOT belong inside React components -- moving it here keeps the
 * component presentational and makes the derivation table-driven testable
 * (rule T1: translators import only from `@/lib/wire/`, no I/O, no React).
 *
 * Recognises the same three guardrail event shapes as the backend
 * aggregator (`accepted`, `verified`, `stage=output`+`blocked`) so the
 * Workflow Deep Dive Validation quadrant matches the orchestration
 * runtime instead of only counting prompt-injection rows.
 */
import type {
  BlackBoxEvent,
  ComplianceBundle,
} from "@/lib/wire/responses";

export interface GuardrailCounts {
  total: number;
  pass: number;
  fail: number;
}

/**
 * Return the pass/fail signal for a `guardrail_checked` event, or `null`
 * when the event shape is unrecognised.  Returning `null` (instead of
 * defaulting to `false`) keeps `pass + fail === total` honest.
 */
function eventAccepted(event: BlackBoxEvent): boolean | null {
  if (event.event_type !== "guardrail_checked") return null;
  const details = event.details ?? {};
  if (typeof details["accepted"] === "boolean") {
    return details["accepted"];
  }
  if (typeof details["verified"] === "boolean") {
    return details["verified"];
  }
  if (
    details["stage"] === "output" &&
    typeof details["blocked"] === "boolean"
  ) {
    return !(details["blocked"] as boolean);
  }
  return null;
}

export function countGuardrails(bundle: ComplianceBundle): GuardrailCounts {
  let total = 0;
  let pass = 0;
  for (const event of bundle.events) {
    const accepted = eventAccepted(event);
    if (accepted === null) continue;
    total += 1;
    if (accepted) pass += 1;
  }
  return { total, pass, fail: total - pass };
}
