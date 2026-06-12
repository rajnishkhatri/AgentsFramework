/**
 * Live trajectory narration (eval-UI F10 Tier 1, decision D-B).
 *
 * A friendly present-tense line derived purely from the tool trajectory:
 * `reading notes.md → running \`sed\` → writing notes_clean.md`. This is
 * the free, deterministic, zero-latency tier -- no model call ever. The
 * optional Tier 2 polished recap (one cheap completion per run) rides the
 * Custom 'reasoning_summary' wire event and lands separately.
 *
 * Unknown tools degrade to a generic `running {name}` phrase
 * (failure-first contract).
 *
 * Imports: sibling translators only. No SDK, no React, no I/O.
 */

import type { MessageSegment } from "./run_view_reducer";
import type { ToolCallRendererRequest } from "../wire/ui_runtime_events";

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

function phrase(request: ToolCallRendererRequest): string {
  const input = request.input;
  switch (request.tool_name) {
    case "file_io": {
      const op = str(input["operation"]);
      const path = str(input["path"]);
      if (op && path) {
        const verb =
          op === "read" ? "reading" : op === "write" ? "writing" : `${op}ing`;
        return `${verb} ${path}`;
      }
      break;
    }
    case "shell": {
      const command = str(input["command"]);
      if (command) return `running \`${command}\``;
      break;
    }
    case "web_search": {
      const query = str(input["query"]);
      if (query) return `searching “${query}”`;
      break;
    }
    case "state_todo":
      return "updating the task list";
    default:
      break;
  }
  return `running ${request.tool_name}`;
}

/** Narrate the tool trajectory in order; "" when nothing tool-shaped. */
export function narrateTrajectory(
  segments: ReadonlyArray<MessageSegment>,
): string {
  const phrases: string[] = [];
  for (const seg of segments) {
    if (seg.kind === "tool") phrases.push(phrase(seg.request));
  }
  return phrases.join(" → ");
}
