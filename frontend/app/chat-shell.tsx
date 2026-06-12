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
import { TaskList } from "@/components/chat/TaskList";
import { TaskUnderstandingCard } from "@/components/chat/TaskUnderstandingCard";
import { ThemeToggle } from "@/components/chat/ThemeToggle";
import { ToolCard } from "@/components/tools/ToolCard";
import { useAgentRun, type ChatTurn } from "@/components/chat/use_agent_run";
import { browserRuntimeClient } from "@/lib/composition_browser";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";
import type { AssistantRunView } from "@/lib/translators/run_view_reducer";
import { deriveRunPhase, type RunPhase } from "@/lib/translators/run_phase";
import { narrateTrajectory } from "@/lib/translators/run_narration";
import { synthesizeFallbackAnswer } from "@/lib/translators/fallback_answer";

const PHASE_LABEL: Record<RunPhase, string> = {
  connecting: "connecting…",
  thinking: "thinking…",
  tool: "using tools…",
  writing: "writing…",
  done: "done",
  error: "error",
};

/**
 * F2/F8/F10-T1 status slot: the in-progress feed lives in its OWN
 * aria-live region, never concatenated into the answer body. The phase
 * label derives from real events (deriveRunPhase, F8); beneath it the
 * free Tier-1 narration line tells the trajectory story
 * (narrateTrajectory, F10). Animation is gated by `evalMode` so frozen
 * eval captures stay deterministic (decision D-A). On `complete` the
 * slot collapses to a subtle done marker.
 */
function RunStatusLine(props: {
  view: AssistantRunView;
  phase: RunPhase;
  evalMode: boolean;
}): React.JSX.Element | null {
  const { view, phase } = props;
  if (view.status === "complete") {
    return (
      <p
        data-testid="terminal-marker"
        className="text-xs text-muted m-0"
        aria-label="Run complete"
      >
        ✓ done
      </p>
    );
  }
  if (view.status !== "streaming") return null;
  const runningTool = [...view.segments]
    .reverse()
    .find((s) => s.kind === "tool" && s.request.status === "running");
  const label =
    runningTool && runningTool.kind === "tool"
      ? `using ${runningTool.request.tool_name}…`
      : view.step && phase === "thinking"
        ? `step ${view.step.count} · ${view.step.name}…`
        : PHASE_LABEL[phase];
  const narration = narrateTrajectory(view.segments);
  return (
    <div
      data-testid="run-status"
      aria-live="polite"
      className="text-xs text-muted m-0 grid gap-0.5"
    >
      <p className={props.evalMode ? "m-0" : "m-0 animate-pulse"}>{label}</p>
      {narration ? (
        // Reasoning layer: sans italic muted (Appendix A) -- visually
        // distinct from the answer so thinking is never read as prose.
        <p data-testid="reasoning-narration" className="m-0 italic">
          {narration}
        </p>
      ) : null}
    </div>
  );
}

/**
 * F6: copyable trace_id chip -- one-click UI ↔ Langfuse correlation for
 * annotators. The trace_id is forwarded from the backend (F-R7), never
 * generated here. Gated to eval mode so prod chat stays clean.
 */
function TraceChip(props: { traceId: string }): React.JSX.Element {
  const [copied, setCopied] = React.useState(false);
  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(props.traceId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1_500);
    } catch {
      /* clipboard unavailable -- chip stays idle */
    }
  }
  return (
    <button
      type="button"
      data-testid="trace-chip"
      onClick={copy}
      aria-label="Copy trace id"
      className="justify-self-start font-mono text-xs text-muted bg-surface border border-border rounded-sm px-2 py-0.5 cursor-pointer hover:text-fg"
    >
      {copied ? "copied" : `trace ${props.traceId}`}
    </button>
  );
}

function AssistantMessage(props: {
  turn: ChatTurn;
  evalMode?: boolean;
}): React.JSX.Element {
  const { assistant } = props.turn;
  const toolCount = assistant.segments.filter((s) => s.kind === "tool").length;
  const phase = deriveRunPhase(assistant);
  const fallbackAnswer = synthesizeFallbackAnswer(assistant);
  let firstTextSeen = false;
  return (
    <div
      data-state={assistant.status}
      data-run-phase={phase}
      data-tool-count={toolCount}
      data-testid="assistant-message"
      className="grid gap-2"
    >
      {assistant.understanding ? (
        // Phase 3 soft gate: the card shows the agent's restated intent +
        // success checklist while tokens keep streaming (FD5 — it must
        // never block the answer).
        <TaskUnderstandingCard understanding={assistant.understanding} />
      ) : null}
      {assistant.todos ? <TaskList view={assistant.todos} /> : null}
      {assistant.segments.map((seg, i) => {
        if (seg.kind !== "text") {
          return <ToolCard key={seg.request.tool_call_id} request={seg.request} />;
        }
        // F5: badge + meter render once, on the first text segment.
        const isFirstText = !firstTextSeen;
        firstTextSeen = true;
        return (
          <StreamingMarkdown
            key={`text-${i}`}
            text={seg.text}
            {...(isFirstText && assistant.modelBadge
              ? { modelBadge: assistant.modelBadge }
              : {})}
            {...(isFirstText && assistant.step ? { step: assistant.step } : {})}
          />
        );
      })}
      {fallbackAnswer !== null ? (
        <div data-testid="fallback-answer">
          <StreamingMarkdown text={fallbackAnswer} />
          <p className="text-xs text-muted m-0 italic">
            summary generated from tool results
          </p>
        </div>
      ) : null}
      {assistant.status === "error" ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400 m-0">
          {assistant.errorMessage ?? "The run failed."}
        </p>
      ) : null}
      {assistant.reasoning ? (
        // F10 Tier-2: progressive disclosure -- the recap stays collapsed
        // unless expanded. Eval mode pre-opens it so the settled recap is
        // part of the capture. Reasoning layer typography (Appendix A):
        // never styled like the answer.
        <details
          data-testid="reasoning-summary"
          open={props.evalMode ?? false}
          className="text-xs text-muted"
        >
          <summary className="cursor-pointer select-none">Show reasoning</summary>
          <p className="m-0 mt-1 italic">{assistant.reasoning}</p>
        </details>
      ) : null}
      <RunStatusLine
        view={assistant}
        phase={phase}
        evalMode={props.evalMode ?? false}
      />
      {props.evalMode && assistant.traceId ? (
        <TraceChip traceId={assistant.traceId} />
      ) : null}
    </div>
  );
}

export function ChatShell(props: {
  userEmail: string;
  /** Test seam: defaults to the browser composition root's client. */
  runtime?: AgentRuntimeClient;
  /**
   * F7 eval-mode capture surface: when a case id is pinned (`?eval=GJ-…`)
   * the UI freezes animation, pins the case id, and surfaces the trace
   * chip so batch and human captures are identical and admissible.
   */
  evalCase?: string | null;
}): React.JSX.Element {
  const injected = props.runtime;
  const runtime = React.useMemo(
    () => injected ?? browserRuntimeClient(),
    [injected],
  );
  const evalMode = Boolean(props.evalCase);
  const { turns, busy, send } = useAgentRun(runtime);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  return (
    <div
      className="min-h-dvh grid grid-rows-[auto_1fr_auto]"
      {...(props.evalCase ? { "data-eval-case": props.evalCase } : {})}
    >
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-border-light">
        <h1 className="text-lg font-semibold m-0">ReAct Agent</h1>
        <div className="flex items-center gap-3">
          {props.evalCase ? (
            <span
              data-testid="eval-banner"
              className="font-mono text-xs uppercase tracking-wide px-2 py-0.5 rounded-sm bg-accent-light text-accent"
            >
              eval · {props.evalCase}
            </span>
          ) : null}
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
                  <AssistantMessage turn={turn} evalMode={evalMode} />
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
