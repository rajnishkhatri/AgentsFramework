/**
 * ShellApprovalCard (shell_severity_approval_hitl plan) — Cursor warm-neutral.
 *
 * Presentational Approve / Edit / Reject card for a severity-gated shell
 * command that the backend PEP paused behind a dynamic `interrupt()` (Part A
 * Opt 3). The human decides; `onResolve` carries the decision back, and the
 * CopilotKit `useHumanInTheLoop` wiring (at the registration layer, like the
 * tool_renderer split — this component does NOT import CopilotKit) turns it into
 * `Command(resume=...)` on the same thread.
 *
 * Fail-closed UX: the buttons disable after the first decision so a paused run
 * resolves exactly once (no double-resolve). The card never auto-runs anything —
 * the subprocess sits behind the interrupt server-side; this card only chooses
 * approve / edit / reject. A `timeout_seconds` ⇒ the backend defaults to deny.
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { ApprovalRequestedEvent } from "@/lib/wire/ui_runtime_events";

export interface ApprovalResolution {
  decision: "approve" | "edit" | "reject";
  edited_command?: string;
}

// Severity → Badge tone. MED/HIGH are the only bands that reach a card (auto
// runs silent, CRIT is hard-denied), but the map is total for safety.
const SEVERITY_BADGE: Record<
  ApprovalRequestedEvent["severity"],
  "default" | "warning" | "danger"
> = {
  low: "default",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

export function ShellApprovalCard(props: {
  event: ApprovalRequestedEvent;
  onResolve: (resolution: ApprovalResolution) => void;
}): React.JSX.Element {
  const { event, onResolve } = props;
  const [editValue, setEditValue] = React.useState(event.command);
  const [resolved, setResolved] = React.useState(false);
  // The resolve-once guard is a ref, not the `resolved` state: a synchronous
  // guard must hold even before React commits the re-render (e.g. two clicks in
  // the same tick), so the run resolves exactly once (fail-closed UX).
  const resolvedRef = React.useRef(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const resolve = React.useCallback(
    (resolution: ApprovalResolution) => {
      if (resolvedRef.current) return; // resolve exactly once
      resolvedRef.current = true;
      setResolved(true);
      onResolve(resolution);
    },
    [onResolve],
  );

  return (
    <section
      data-testid="shell-approval-card"
      data-approval-id={event.approval_id}
      data-severity={event.severity}
      className={cn(
        "surface-etched rounded-lg bg-surface px-3 py-2 my-1 grid gap-2",
      )}
    >
      <header className="flex gap-2 items-center text-sm">
        <span className="font-semibold">Approve shell command?</span>
        <Badge variant={SEVERITY_BADGE[event.severity]} className="ml-auto">
          {event.severity}
        </Badge>
      </header>

      <pre
        data-testid="shell-approval-command"
        className="overflow-auto my-1 text-sm font-mono"
      >
        {event.command}
      </pre>

      <label className="grid gap-1 text-xs text-muted">
        <span>Edit before running (optional)</span>
        <input
          ref={inputRef}
          data-testid="shell-approval-edit-input"
          className="text-sm font-mono bg-surface-sunken rounded-sm px-2 py-1 border border-border"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          disabled={resolved}
        />
      </label>

      <div className="flex gap-2">
        <button
          type="button"
          data-testid="shell-approval-approve"
          disabled={resolved}
          onClick={() => resolve({ decision: "approve" })}
          className="text-sm rounded-sm px-3 py-1 bg-accent-light text-accent disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          data-testid="shell-approval-edit"
          disabled={resolved}
          onClick={() =>
            // Read the live DOM value so the resolution reflects the latest
            // keystroke even if a controlled re-render hasn't committed yet.
            resolve({
              decision: "edit",
              edited_command: inputRef.current?.value ?? editValue,
            })
          }
          className="text-sm rounded-sm px-3 py-1 bg-surface-sunken disabled:opacity-50"
        >
          Run edited
        </button>
        <button
          type="button"
          data-testid="shell-approval-reject"
          disabled={resolved}
          onClick={() => resolve({ decision: "reject" })}
          className="text-sm rounded-sm px-3 py-1 ml-auto text-danger disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </section>
  );
}
