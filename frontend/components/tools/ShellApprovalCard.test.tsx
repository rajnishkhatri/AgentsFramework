/**
 * ShellApprovalCard (shell_severity_approval_hitl plan) — presentational
 * Approve / Edit / Reject card. Failure paths first: Reject resolves to a
 * decline; Approve resolves to the original command; Edit resolves to the
 * modified command. The card is pure (no CopilotKit); the useHumanInTheLoop
 * wiring connects `onResolve` to Command(resume=...) at the registration layer
 * (the ToolCard / tool_renderer split).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { ShellApprovalCard } from "./ShellApprovalCard";
import type { ApprovalRequestedEvent } from "@/lib/wire/ui_runtime_events";

function evt(overrides: Partial<ApprovalRequestedEvent> = {}): ApprovalRequestedEvent {
  return {
    type: "approval_requested",
    trace_id: "tr1",
    approval_id: "ap1",
    tool: "shell",
    command: "rm foo.txt",
    severity: "high",
    band: "ask",
    timeout_seconds: 120,
    ...overrides,
  };
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  root.unmount();
  container.remove();
});

const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

async function render(
  event: ApprovalRequestedEvent,
  onResolve: (d: { decision: string; edited_command?: string }) => void,
): Promise<void> {
  root.render(React.createElement(ShellApprovalCard, { event, onResolve }));
  await flush();
}

function byTestId(id: string): HTMLElement | null {
  return container.querySelector(`[data-testid='${id}']`);
}

function click(el: HTMLElement | null): void {
  (el as HTMLElement).dispatchEvent(
    new MouseEvent("click", { bubbles: true, cancelable: true }),
  );
}

describe("ShellApprovalCard", () => {
  it("renders the command, severity and tool", async () => {
    await render(evt(), vi.fn());
    const card = byTestId("shell-approval-card");
    expect(card).toBeTruthy();
    expect(card?.textContent).toContain("rm foo.txt");
    expect(card?.textContent?.toLowerCase()).toContain("high");
  });

  it("Reject resolves to a reject decision (failure path first)", async () => {
    const onResolve = vi.fn();
    await render(evt(), onResolve);
    click(byTestId("shell-approval-reject"));
    expect(onResolve).toHaveBeenCalledExactlyOnceWith({ decision: "reject" });
  });

  it("Approve resolves to approve with no edit", async () => {
    const onResolve = vi.fn();
    await render(evt(), onResolve);
    click(byTestId("shell-approval-approve"));
    expect(onResolve).toHaveBeenCalledExactlyOnceWith({ decision: "approve" });
  });

  it("Edit resolves to edit carrying the modified command", async () => {
    const onResolve = vi.fn();
    await render(evt({ command: "rm foo" }), onResolve);
    const input = byTestId("shell-approval-edit-input") as HTMLInputElement;
    // The edit field is seeded with the original command.
    expect(input.value).toBe("rm foo");
    input.value = "ls foo";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    click(byTestId("shell-approval-edit"));
    expect(onResolve).toHaveBeenCalledExactlyOnceWith({
      decision: "edit",
      edited_command: "ls foo",
    });
  });

  it("disables the buttons after a decision (no double-resolve)", async () => {
    const onResolve = vi.fn();
    await render(evt(), onResolve);
    click(byTestId("shell-approval-approve"));
    click(byTestId("shell-approval-reject"));
    // A second click after resolving must not fire onResolve again.
    expect(onResolve).toHaveBeenCalledTimes(1);
  });
});
