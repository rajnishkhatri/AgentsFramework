/**
 * WorkflowsTable — presentational component (no 'use client').
 *
 * AC2: columns — Workflow ID, Started, Status, Event Count, Primary Agent.
 * AC3: empty state when workflows is [].
 * AC4: row click navigates to /traces/[wf_id] via <Link>.
 * AC5: all class merging via cn() only — no template-string ternary (rule U6).
 */
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { WorkflowSummary } from "@/lib/wire/responses";

interface WorkflowsTableProps {
  workflows: WorkflowSummary[];
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function StatusBadge({ status }: { status: string }) {
  const isCompleted = status === "completed";
  const isInProgress = status === "in_progress";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        isCompleted && "bg-green-50 text-green-700 ring-green-600/20",
        isInProgress && "bg-blue-50 text-blue-700 ring-blue-600/20",
        !isCompleted && !isInProgress && "bg-muted text-muted-foreground ring-border",
      )}
    >
      {status}
    </span>
  );
}

export function WorkflowsTable({ workflows }: WorkflowsTableProps) {
  if (workflows.length === 0) {
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
          Run <code className="font-mono">python -m explainability_app.dev_seed</code> to
          generate sample data.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-muted/50">
          <tr>
            {["Workflow ID", "Started", "Status", "Events", "Primary Agent"].map(
              (col) => (
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
              ),
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-card">
          {workflows.map((wf) => (
            <tr
              key={wf.workflow_id}
              className={cn("transition-colors hover:bg-accent/50")}
            >
              <td className="px-4 py-3 font-mono text-xs">
                <Link
                  href={`/traces/${wf.workflow_id}`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {wf.workflow_id}
                </Link>
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {formatDate(wf.started_at)}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={wf.status} />
              </td>
              <td className="px-4 py-3 tabular-nums text-muted-foreground">
                {wf.event_count}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                {wf.primary_agent_id ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
