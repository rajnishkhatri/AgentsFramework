/**
 * Storybook stories for ToolCard (FD6.STORY, S3.8.2).
 *
 * Covers the three tool-call statuses (running, completed, errored) plus
 * string vs. JSON output variants.
 */

import * as React from "react";
import { ToolCard } from "./ToolCard";
import type { ToolCallRendererRequest } from "@/lib/wire/ui_runtime_events";

export default {
  title: "tools/ToolCard",
  component: ToolCard,
};

const BASE: ToolCallRendererRequest = {
  trace_id: "story-trace-001",
  tool_call_id: "tc_1",
  tool_name: "shell",
  input: { command: "ls -la" },
  status: "running",
  output: null,
};

export function Running(): React.JSX.Element {
  return <ToolCard request={BASE} />;
}

export function CompletedString(): React.JSX.Element {
  return (
    <ToolCard
      request={{
        ...BASE,
        tool_name: "web_search",
        status: "completed",
        output: "Found 3 results for 'LangGraph best practices'.",
      }}
      defaultOpen
    />
  );
}

export function CompletedJSON(): React.JSX.Element {
  return (
    <ToolCard
      request={{
        ...BASE,
        tool_name: "file_io",
        status: "completed",
        input: { path: "/workspace/src/main.py", action: "read" },
        output: { lines: 42, truncated: false },
      }}
      defaultOpen
    />
  );
}

export function Errored(): React.JSX.Element {
  return (
    <ToolCard
      request={{
        ...BASE,
        status: "errored",
        output: "Permission denied: /etc/shadow",
      }}
      defaultOpen
    />
  );
}

export function CollapsedByDefault(): React.JSX.Element {
  return (
    <ToolCard
      request={{
        ...BASE,
        status: "completed",
        output: "done",
      }}
    />
  );
}
