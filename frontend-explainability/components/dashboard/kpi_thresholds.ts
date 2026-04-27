/**
 * Pure threshold logic for KPI traffic-light colour selection.
 *
 * Lives outside the component so the threshold is exhaustively unit-testable
 * (one test row per green/amber/red boundary) without touching the DOM.
 *
 * Rule T1 spirit: this file imports nothing — it is pure data + functions.
 */
import type { KpiTone } from "./KpiCard";

/** Total cost ($USD) per KPI tone. */
export function costTone(totalCostUsd: number): KpiTone {
  if (totalCostUsd >= 5.0) return "red";
  if (totalCostUsd >= 1.0) return "amber";
  return "green";
}

/** P95 latency tone — anything past 30 s is red. */
export function latencyTone(p95Ms: number): KpiTone {
  if (p95Ms >= 30_000) return "red";
  if (p95Ms >= 10_000) return "amber";
  if (p95Ms <= 0) return "neutral";
  return "green";
}

/**
 * Guardrail-reject % tone.  The displayed metric is the rejection rate so the
 * polarity here is "lower is better" — anything past a 10 % rejection rate is
 * red, 1–10 % is amber.
 *
 * The rejectRate comparison uses an epsilon to absorb the floating-point loss
 * at the boundary (e.g. `1 - 0.9 = 0.09999…`).
 */
export function guardrailRejectTone(passRate: number): KpiTone {
  if (passRate <= 0) return "neutral";
  const rejectRate = 1 - passRate;
  const eps = 1e-9;
  if (rejectRate >= 0.1 - eps) return "red";
  if (rejectRate >= 0.01 - eps) return "amber";
  return "green";
}

/** Hash-chain validity %. */
export function chainValidTone(validCount: number, invalidCount: number): KpiTone {
  const total = validCount + invalidCount;
  if (total === 0) return "neutral";
  const validPct = validCount / total;
  if (validPct < 1.0) return "red";
  return "green";
}

/** Run count tone is informational only — always neutral. */
export function runCountTone(): KpiTone {
  return "neutral";
}

/** Average cost per run; null when total_runs is zero. */
export function averageCost(totalCostUsd: number, totalRuns: number): number | null {
  if (totalRuns <= 0) return null;
  return totalCostUsd / totalRuns;
}
