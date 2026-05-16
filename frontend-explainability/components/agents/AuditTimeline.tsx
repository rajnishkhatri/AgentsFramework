/**
 * AuditTimeline — chronological vertical timeline of audit entries.
 *
 * Server Component (no `'use client'`): purely presentational rendering of an
 * already-fetched `AgentAuditEntry[]`. The detail panel parent is responsible
 * for sorting; this component preserves the input order.
 *
 * Rule U6: every class merge runs through `cn()`.
 */
import { cn } from "@/lib/utils";
import type { AgentAuditEntry } from "@/lib/wire/responses";

export interface AuditTimelineProps {
  entries: readonly AgentAuditEntry[];
}

const ACTION_TONE: Record<string, string> = {
  register: "bg-green-50 text-green-700 ring-green-600/20",
  suspend: "bg-amber-50 text-amber-700 ring-amber-600/20",
  restore: "bg-blue-50 text-blue-700 ring-blue-600/20",
  revoke: "bg-red-50 text-red-700 ring-red-600/20",
};

function actionClass(action: string): string {
  return ACTION_TONE[action] ?? "bg-muted text-muted-foreground ring-border";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "short",
    timeStyle: "medium",
  });
}

export function AuditTimeline({ entries }: AuditTimelineProps) {
  if (entries.length === 0) {
    return (
      <div
        role="status"
        aria-label="No audit entries"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-10 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No audit entries recorded.</p>
      </div>
    );
  }

  return (
    <ol className="flex flex-col gap-3" aria-label="Audit trail">
      {entries.map((entry, idx) => (
        <li
          key={`${entry.timestamp}-${idx}`}
          className="rounded-lg border border-border bg-card p-4"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <span
                className={cn(
                  "inline-flex w-fit items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
                  actionClass(entry.action),
                )}
              >
                {entry.action}
              </span>
              <p className="text-xs text-muted-foreground">
                by{" "}
                <span className="font-mono text-foreground">
                  {entry.performed_by}
                </span>
              </p>
            </div>
            <time className="text-xs text-muted-foreground">
              {formatDate(entry.timestamp)}
            </time>
          </div>
          {Object.keys(entry.details).length > 0 && (
            <pre
              className={cn(
                "mt-2 overflow-x-auto rounded border border-border bg-background",
                "p-2 font-mono text-xs text-foreground",
              )}
            >
              {JSON.stringify(entry.details, null, 2)}
            </pre>
          )}
        </li>
      ))}
    </ol>
  );
}
