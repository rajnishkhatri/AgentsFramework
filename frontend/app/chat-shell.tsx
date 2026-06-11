/**
 * Chat shell -- client component wiring Composer, StreamingMarkdown,
 * ToolCard, and ThemeToggle into a working chat UI on the architecture's
 * runtime port (eval-UI F1; replaces the off-architecture placeholder).
 *
 * Per F-R1 this component holds NO run-lifecycle logic: `useAgentRun`
 * drives `AgentRuntimeClient.streamRun()` and folds events through the
 * pure run_view_reducer; this file only renders the resulting turns.
 * Per F-R7 trace ids are forwarded from the backend, never generated.
 *
 * `data-state` on each assistant message root is the deterministic
 * terminal-state hook (F2 expands its visual affordances): the batch
 * harness waits on `[data-state="complete"]` instead of text-settle
 * heuristics.
 */

"use client";

import * as React from "react";
import Link from "next/link";
import { Composer } from "@/components/chat/Composer";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";
import { ThemeToggle } from "@/components/chat/ThemeToggle";
import { ToolCard } from "@/components/tools/ToolCard";
import { useAgentRun, type ChatTurn } from "@/components/chat/use_agent_run";
import { browserRuntimeClient } from "@/lib/composition_browser";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";

function AssistantMessage(props: { turn: ChatTurn }): React.JSX.Element {
  const { assistant } = props.turn;
  const toolCount = assistant.segments.filter((s) => s.kind === "tool").length;
  return (
    <div
      data-state={assistant.status}
      data-tool-count={toolCount}
      data-testid="assistant-message"
      className="grid gap-2"
    >
      {assistant.segments.map((seg, i) =>
        seg.kind === "text" ? (
          <StreamingMarkdown key={`text-${i}`} text={seg.text} />
        ) : (
          <ToolCard key={seg.request.tool_call_id} request={seg.request} />
        ),
      )}
      {assistant.status === "error" ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400 m-0">
          {assistant.errorMessage ?? "The run failed."}
        </p>
      ) : null}
    </div>
  );
}

export function ChatShell(props: {
  userEmail: string;
  /** Test seam: defaults to the browser composition root's client. */
  runtime?: AgentRuntimeClient;
}): React.JSX.Element {
  const injected = props.runtime;
  const runtime = React.useMemo(
    () => injected ?? browserRuntimeClient(),
    [injected],
  );
  const { turns, busy, send } = useAgentRun(runtime);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  return (
    <div className="min-h-dvh grid grid-rows-[auto_1fr_auto]">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-border-light">
        <h1 className="text-lg font-semibold m-0">ReAct Agent</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted">{props.userEmail}</span>
          <ThemeToggle />
          <Link
            href="/api/auth/sign-out"
            prefetch={false}
            className="text-sm text-muted hover:text-fg no-underline"
          >
            Sign out
          </Link>
        </div>
      </header>

      {/* Messages area */}
      <main className="overflow-y-auto p-4">
        {turns.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted text-center">
            <div className="grid gap-2">
              <p className="text-2xl m-0">What can I help you with?</p>
              <p className="text-sm m-0">Send a message to start a conversation.</p>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto grid gap-4">
            {turns.map((turn) => (
              <React.Fragment key={turn.id}>
                <div className="justify-self-end bg-accent text-white rounded-lg px-4 py-2 max-w-[80%]">
                  <span className="whitespace-pre-wrap">{turn.user}</span>
                </div>
                <div className="justify-self-start max-w-[80%] w-full">
                  <AssistantMessage turn={turn} />
                </div>
              </React.Fragment>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </main>

      {/* Composer */}
      <div className="max-w-3xl mx-auto w-full">
        <Composer onSend={send} busy={busy} />
      </div>
    </div>
  );
}
