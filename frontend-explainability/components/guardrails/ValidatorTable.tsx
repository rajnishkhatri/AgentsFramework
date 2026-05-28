/**
 * ValidatorTable — presentational, no `'use client'`.
 *
 * Per-validator breakdown for `/guardrails`. Columns: Validator, Total, Pass,
 * Fail, Pass %.  Empty state mirrors the workflows-table pattern.
 *
 * Rule U6: every class merge runs through `cn()`.
 */
import { cn } from "@/lib/utils";
import type { ValidatorStat } from "@/lib/wire/responses";

export interface ValidatorTableProps {
  validators: readonly ValidatorStat[];
}

function formatPct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

export function ValidatorTable({ validators }: ValidatorTableProps) {
  if (validators.length === 0) {
    return (
      <div
        role="status"
        aria-label="No validators"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-10 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No guardrail checks recorded.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-muted/50">
          <tr>
            {["Validator", "Total", "Pass", "Fail", "Pass %"].map((col) => (
              <th
                key={col}
                scope="col"
                className={cn(
                  "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide",
                  "text-muted-foreground",
                )}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-card">
          {validators.map((v) => (
            <tr key={v.name} className={cn("transition-colors hover:bg-accent/50")}>
              <td className="px-4 py-3 font-mono text-xs text-foreground">
                {v.name}
              </td>
              <td className="px-4 py-3 tabular-nums text-muted-foreground">
                {v.total_checks}
              </td>
              <td className="px-4 py-3 tabular-nums text-muted-foreground">
                {v.pass_count}
              </td>
              <td className="px-4 py-3 tabular-nums text-muted-foreground">
                {v.fail_count}
              </td>
              <td className="px-4 py-3 tabular-nums text-foreground">
                {formatPct(v.pass_rate)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
