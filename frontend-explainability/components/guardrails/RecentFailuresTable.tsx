/**
 * RecentFailuresTable — links each failure back to /traces/[wf_id] so the
 * operator can drill into the offending workflow timeline (S2.1.2 AC).
 *
 * Server Component (no `'use client'`) — purely presentational.
 */
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { GuardrailFailure } from "@/lib/wire/responses";

export interface RecentFailuresTableProps {
  failures: readonly GuardrailFailure[];
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "short",
    timeStyle: "medium",
  });
}

export function RecentFailuresTable({ failures }: RecentFailuresTableProps) {
  if (failures.length === 0) {
    return (
      <div
        role="status"
        aria-label="No recent failures"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-10 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No guardrail rejections in this window.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-muted/50">
          <tr>
            {["Workflow", "Validator", "Action", "When"].map((col) => (
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
          {failures.map((f, idx) => (
            <tr
              key={`${f.workflow_id}-${idx}`}
              className={cn("transition-colors hover:bg-accent/50")}
            >
              <td className="px-4 py-3 font-mono text-xs">
                <Link
                  href={`/traces/${f.workflow_id}`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {f.workflow_id}
                </Link>
              </td>
              <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                {f.validator}
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {f.fail_action ?? "—"}
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {formatDate(f.timestamp)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
