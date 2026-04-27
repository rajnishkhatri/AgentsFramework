/**
 * Generic tool card (S3.8.2, F5).
 *
 * Renders one ToolCallRendererRequest as a collapsible card. Uses a
 * native <details> for collapsibility -- zero JS, fully accessible.
 *
 * Per F-R2: this component does NOT import CopilotKit. Tool registration
 * happens in `lib/adapters/tool_renderer/`; the registry returns this
 * component (or a tool-specific specialization) as the renderer.
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import type { ToolCallRendererRequest } from "@/lib/wire/ui_runtime_events";

const STATUS_LABEL: Record<ToolCallRendererRequest["status"], string> = {
  running: "running",
  completed: "completed",
  errored: "errored",
};

export function ToolCard(props: {
  request: ToolCallRendererRequest;
  defaultOpen?: boolean;
}): React.JSX.Element {
  const { request } = props;
  const isString = typeof request.output === "string";
  return (
    <details
      open={props.defaultOpen ?? request.status === "running"}
      className="border border-border rounded-md px-3 py-2 my-1 bg-surface"
    >
      <summary className="cursor-pointer flex gap-2 items-center font-mono text-sm">
        <span className="font-bold">{request.tool_name}</span>
        <span className="text-muted">{STATUS_LABEL[request.status]}</span>
      </summary>
      <section className="mt-2 grid gap-2">
        <div>
          <strong className="text-xs text-muted">input</strong>
          <pre className="overflow-auto my-1">
            {JSON.stringify(request.input, null, 2)}
          </pre>
        </div>
        {request.output != null ? (
          <div>
            <strong className="text-xs text-muted">output</strong>
            <pre className="overflow-auto my-1">
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
