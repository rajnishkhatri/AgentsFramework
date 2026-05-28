/**
 * IntegrityStatusTable — server component, presentational only (S3.2.1).
 *
 * Shows one row per workflow with its chain integrity status.  Tampered
 * chains expose the offending event id so the operator can drill in via
 * /traces/[wf_id].  Empty state covers the "no workflows" snapshot test.
 *
 * Rule U6: every class merge runs through `cn()`.
 * Rule FD4.SEM: drill-in affordance is `<Link>` (anchor), never `<div onClick>`.
 */
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { IntegrityReport, WorkflowSummary } from "@/lib/wire/responses";

export interface IntegrityRow {
  workflow: WorkflowSummary;
  /** Null when the integrity check failed to load for this workflow. */
  report: IntegrityReport | null;
}

export interface IntegrityStatusTableProps {
  rows: readonly IntegrityRow[];
}

function StatusBadge({ chainValid }: { chainValid: boolean | null }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        chainValid === true && "bg-green-50 text-green-700 ring-green-600/20",
        chainValid === false && "bg-red-50 text-red-700 ring-red-600/20",
        chainValid === null && "bg-muted text-muted-foreground ring-border",
      )}
    >
      {chainValid === true && "valid"}
      {chainValid === false && "tampered"}
      {chainValid === null && "unknown"}
    </span>
  );
}

export function IntegrityStatusTable({ rows }: IntegrityStatusTableProps) {
  if (rows.length === 0) {
    return (
      <div
        role="status"
        aria-label="No workflows"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-16 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No workflows recorded yet.</p>
        <p className="mt-1 text-xs">
          Run{" "}
          <code className="font-mono">
            python -m explainability_app.dev_seed
          </code>{" "}
          to generate sample data.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-muted/50">
          <tr>
            {["Workflow", "Chain", "Break Location", "Events"].map((col) => (
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
          {rows.map(({ workflow, report }) => {
            const chainValid = report ? report.chain_valid : null;
            return (
              <tr
                key={workflow.workflow_id}
                className={cn("transition-colors hover:bg-accent/50")}
                data-chain-valid={String(chainValid)}
              >
                <td className="px-4 py-3 font-mono text-xs">
                  <Link
                    href={`/compliance/${workflow.workflow_id}`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    {workflow.workflow_id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge chainValid={chainValid} />
                </td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                  {report?.broken_at_event_id ?? "—"}
                </td>
                <td className="px-4 py-3 tabular-nums text-muted-foreground">
                  {workflow.event_count}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
