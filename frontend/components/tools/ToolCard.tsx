/**
 * Generic tool card (S3.8.2, F5) — Cursor warm-neutral (§2.6).
 *
 * Renders one ToolCallRendererRequest as a collapsible card. The root stays a
 * native <details> for zero-JS, fully-accessible collapsibility — and because
 * the e2e suite selects `details[data-testid='tool-card']` and reads its
 * `pre` blocks, that shape is contractual (do not swap to a div Card).
 *
 * The chrome is token-driven Card styling: soft `radius-lg`, hairline border,
 * recessed `surface` fill. The status reads as a Badge; a running tool shows
 * the pulsing status-orb so an in-flight call looks alive.
 *
 * Per F-R2: this component does NOT import CopilotKit. Tool registration
 * happens in `lib/adapters/tool_renderer/`; the registry returns this
 * component (or a tool-specific specialization) as the renderer.
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { ToolCallRendererRequest } from "@/lib/wire/ui_runtime_events";

const STATUS_LABEL: Record<ToolCallRendererRequest["status"], string> = {
  running: "running",
  completed: "completed",
  errored: "errored",
};

// Map tool status → Badge tone + status-orb state class. running = the live
// accent orb, completed = success, errored = danger.
const STATUS_BADGE: Record<
  ToolCallRendererRequest["status"],
  "default" | "accent" | "outline"
> = {
  running: "accent",
  completed: "outline",
  errored: "default",
};

function StatusOrb(props: {
  status: ToolCallRendererRequest["status"];
}): React.JSX.Element {
  return (
    <span
      className={cn(
        "status-orb",
        props.status === "completed" && "is-success",
        props.status === "errored" && "is-danger",
      )}
      aria-hidden="true"
    />
  );
}

export function ToolCard(props: {
  request: ToolCallRendererRequest;
  defaultOpen?: boolean;
}): React.JSX.Element {
  const { request } = props;
  const isString = typeof request.output === "string";
  return (
    <details
      open={props.defaultOpen ?? request.status === "running"}
      data-testid="tool-card"
      data-status={request.status}
      data-tool-call-id={request.tool_call_id}
      className={cn(
        "rounded-lg border border-border bg-surface px-3 py-2 my-1",
        "[&[open]]:bg-surface-sunken transition-colors",
      )}
    >
      <summary className="cursor-pointer flex gap-2 items-center font-mono text-sm list-none">
        <StatusOrb status={request.status} />
        <span className="font-semibold">{request.tool_name}</span>
        <Badge variant={STATUS_BADGE[request.status]} className="ml-auto">
          {STATUS_LABEL[request.status]}
        </Badge>
      </summary>
      <section className="mt-2 grid gap-2">
        <div>
          <strong className="text-xs text-muted">input</strong>
          <pre className="overflow-auto my-1 text-sm">
            {JSON.stringify(request.input, null, 2)}
          </pre>
        </div>
        {request.output != null ? (
          <div>
            <strong className="text-xs text-muted">output</strong>
            <pre className="overflow-auto my-1 text-sm">
              {isString
                ? (request.output as string)
                : JSON.stringify(request.output, null, 2)}
            </pre>
          </div>
        ) : null}
      </section>
    </details>
  );
}
