/**
 * run_narration tests (eval-UI F10 Tier 1). Pure, free, deterministic
 * narration from the trajectory -- zero model calls.
 *
 * Failure path first: unknown tools get graceful generic phrasing.
 */

import { describe, expect, it } from "vitest";
import type { MessageSegment } from "./run_view_reducer";
import { narrateTrajectory } from "./run_narration";

function toolSeg(
  tool_name: string,
  input: Record<string, unknown>,
  status: "running" | "completed" | "errored" = "completed",
): MessageSegment {
  return {
    kind: "tool",
    request: {
      trace_id: "tr1",
      tool_call_id: `tc-${tool_name}-${Math.random()}`,
      tool_name,
      input,
      status,
      output: null,
    },
  };
}

describe("narrateTrajectory — failure paths first", () => {
  it("unknown tool falls back to a generic 'running {name}' phrase", () => {
    const line = narrateTrajectory([toolSeg("quantum_flux", { q: 1 })]);
    expect(line).toBe("running quantum_flux");
  });

  it("empty trajectory narrates as empty string", () => {
    expect(narrateTrajectory([])).toBe("");
  });

  it("text-only segments narrate as empty string (nothing tool-shaped to tell)", () => {
    expect(narrateTrajectory([{ kind: "text", text: "hi" }])).toBe("");
  });

  it("an errored call keeps its phrase (the trajectory is evidence)", () => {
    const line = narrateTrajectory([
      toolSeg("shell", { command: "cat /etc/shadow" }, "errored"),
    ]);
    expect(line).toContain("cat /etc/shadow");
  });
});

describe("narrateTrajectory — friendly phrasing", () => {
  it("file_io read/write phrases with the path", () => {
    const line = narrateTrajectory([
      toolSeg("file_io", { operation: "read", path: "notes.md" }),
      toolSeg("file_io", { operation: "write", path: "notes_clean.md" }),
    ]);
    expect(line).toBe("reading notes.md → writing notes_clean.md");
  });

  it("shell phrases with the command", () => {
    const line = narrateTrajectory([toolSeg("shell", { command: "ls -la" })]);
    expect(line).toBe("running `ls -la`");
  });

  it("web_search phrases with the query", () => {
    const line = narrateTrajectory([
      toolSeg("web_search", { query: "Austin weather" }),
    ]);
    expect(line).toBe("searching “Austin weather”");
  });

  it("chains steps with arrows in trajectory order", () => {
    const line = narrateTrajectory([
      toolSeg("file_io", { operation: "read", path: "a.txt" }),
      toolSeg("shell", { command: "wc -l a.txt" }),
    ]);
    expect(line).toBe("reading a.txt → running `wc -l a.txt`");
  });

  it("is deterministic for a fixed segment list", () => {
    const segs = [toolSeg("file_io", { operation: "read", path: "x" })];
    expect(narrateTrajectory(segs)).toBe(narrateTrajectory(segs));
  });
});
