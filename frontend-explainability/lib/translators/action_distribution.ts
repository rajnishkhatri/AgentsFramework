/**
 * Pure translator: GuardrailSummary.fail_action_distribution -> ActionSlice[]
 * for the action-distribution pie on `/guardrails`.
 *
 * Rule T1: this file imports nothing — pure data + functions.
 *
 * Sort order:
 *   - count desc (largest slice first), then
 *   - alphabetical action name (deterministic for ties).
 *
 * Empty buckets and the "" key are normalised to the explicit "unspecified"
 * label so downstream charts never render an unlabelled wedge.
 */

export type ActionColor = "danger" | "warning" | "info" | "neutral";

export interface ActionSlice {
  /** Display label for the slice. */
  action: string;
  /** Failures that took this action. */
  count: number;
  /** Fraction of the total (0..1). */
  share: number;
  /** Semantic colour token consumed by the chart. */
  color: ActionColor;
}

/**
 * Static mapping from a fail_action name to a presentation colour.
 * Adding a new action upstream requires a new row here AND a new test row.
 */
const ACTION_COLOR: Record<string, ActionColor> = {
  reject: "danger",
  redact: "warning",
  escalate: "warning",
  retry: "info",
  unspecified: "neutral",
};

export function failActionDistributionToSlices(
  distribution: Readonly<Record<string, number>>,
): ActionSlice[] {
  const cleaned: Array<{ action: string; count: number }> = [];
  for (const [rawAction, count] of Object.entries(distribution)) {
    if (typeof count !== "number" || !Number.isFinite(count) || count <= 0) continue;
    const action = rawAction.trim() === "" ? "unspecified" : rawAction;
    cleaned.push({ action, count });
  }

  if (cleaned.length === 0) return [];

  const total = cleaned.reduce((acc, s) => acc + s.count, 0);
  cleaned.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return a.action.localeCompare(b.action);
  });

  return cleaned.map((s) => ({
    action: s.action,
    count: s.count,
    share: s.count / total,
    color: ACTION_COLOR[s.action] ?? "neutral",
  }));
}
