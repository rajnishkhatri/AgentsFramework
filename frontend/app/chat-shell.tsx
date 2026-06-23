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
import { ArrowDown, Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Composer } from "@/components/chat/Composer";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";
import { TaskList } from "@/components/chat/TaskList";
import { TaskUnderstandingCard } from "@/components/chat/TaskUnderstandingCard";
import { ThemeToggle } from "@/components/chat/ThemeToggle";
import { ToolCard } from "@/components/tools/ToolCard";
import { useAgentRun, type ChatTurn } from "@/components/chat/use_agent_run";
import {
  useChatSidebars,
  type ChatSidebarsState,
} from "@/components/chat/use_chat_sidebars";
import { SidebarPanel } from "@/components/chat/SidebarPanel";
import { useSidebarChrome } from "@/components/chat/use_sidebar_chrome";
import { useStickToBottom } from "@/components/chat/use_stick_to_bottom";
import { MessageActions, useLongPress } from "@/components/chat/MessageActions";
import { RecallIndicator } from "@/components/memory/RecallIndicator";
import { RecalledMemories } from "@/components/memory/RecalledMemories";
import { filterThreadsByTitle } from "@/lib/thread_grouping";
import { browserRuntimeClient } from "@/lib/composition_browser";
import { cn } from "@/lib/utils";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";
import type { AssistantRunView } from "@/lib/translators/run_view_reducer";
import { deriveRunPhase, type RunPhase } from "@/lib/translators/run_phase";
import { narrateTrajectory } from "@/lib/translators/run_narration";
import { synthesizeFallbackAnswer } from "@/lib/translators/fallback_answer";
import type { MemoryItem } from "@/lib/wire/agent_protocol";

/**
 * Phase B: resolve a turn's recalled memory KEYS against the owner's loaded
 * memory panel into displayable items (key + type + content). Pure + order-
 * preserving (recall order). A key with no matching panel item is dropped — the
 * recall wire event carries keys only (never content), so a key the panel hasn't
 * loaded simply isn't shown rather than rendering a contentless row.
 */
export function recalledItems(
  keys: ReadonlyArray<string>,
  memories: ReadonlyArray<MemoryItem>,
): ReadonlyArray<MemoryItem> {
  if (keys.length === 0) return [];
  const byKey = new Map(memories.map((m) => [m.key, m]));
  const out: MemoryItem[] = [];
  for (const key of keys) {
    const item = byKey.get(key);
    if (item) out.push(item);
  }
  return out;
}

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
      <div
        data-testid="terminal-marker"
        className="text-xs text-muted m-0 flex items-center gap-2"
        aria-label="Run complete"
      >
        {/* Model badge (design meta-row parity): the model that produced the
           answer, shown beside the done marker. */}
        {view.modelBadge ? (
          <span className="inline-flex items-center rounded-sm border border-border bg-surface px-2 py-0.5">
            {view.modelBadge}
          </span>
        ) : null}
        <span className="flex items-center gap-1.5">
          {/* Eval captures freeze animation (decision D-A): show ✓ instead of
             the pulsing orb so frozen captures stay deterministic. */}
          {props.evalMode ? (
            <span aria-hidden="true">✓</span>
          ) : (
            <span className="status-orb is-success" aria-hidden="true" />
          )}
          done
        </span>
      </div>
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
      {/* Streaming "alive" indicator: the pulsing status-orb carries the
         motion (reduced-motion safe via status-orb.css). In eval mode the
         orb's pulse is irrelevant — captures freeze on the static label. */}
      <p className="m-0 flex items-center gap-1.5">
        {props.evalMode ? null : <span className="status-orb" aria-hidden="true" />}
        {label}
      </p>
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

/** The settled answer prose for copy/regenerate: text segments joined, else
 *  the synthesized fallback recap, else empty (nothing to act on yet). */
function answerText(view: AssistantRunView): string {
  const text = view.segments
    .filter((s) => s.kind === "text")
    .map((s) => (s.kind === "text" ? s.text : ""))
    .join("")
    .trim();
  if (text.length > 0) return text;
  return synthesizeFallbackAnswer(view) ?? "";
}

function AssistantMessage(props: {
  turn: ChatTurn;
  evalMode?: boolean;
  /** Re-run this turn from its user prompt; omitted while any run is live. */
  onRegenerate?: () => void;
  /** Phase 4 edit seam: present only on the editable (latest live) turn. */
  understandingEdit?: {
    editError: string | null;
    onEditStart: () => void;
    onSave: (draft: {
      restated_intent: string;
      success_conditions: ReadonlyArray<string>;
    }) => void;
    onCancel: () => void;
  };
}): React.JSX.Element {
  const { assistant } = props.turn;
  const toolCount = assistant.segments.filter((s) => s.kind === "tool").length;
  const phase = deriveRunPhase(assistant);
  const fallbackAnswer = synthesizeFallbackAnswer(assistant);
  let firstTextSeen = false;

  // Per-message actions (§6): show once there's settled prose to act on.
  const settledAnswer = answerText(assistant);
  const showActions = settledAnswer.length > 0;
  const [menuOpen, setMenuOpen] = React.useState(false);
  const longPress = useLongPress(() => setMenuOpen(true));

  return (
    <div
      data-state={assistant.status}
      data-run-phase={phase}
      data-tool-count={toolCount}
      data-testid="assistant-message"
      className="group grid gap-2"
      {...(showActions ? longPress : {})}
    >
      {assistant.understanding ? (
        // Phase 3 soft gate: the card shows the agent's restated intent +
        // success checklist while tokens keep streaming (FD5 — it must
        // never block the answer). Phase 4: on the live turn the card is
        // editable — Edit pauses the run, Save POSTs + resumes.
        <TaskUnderstandingCard
          understanding={assistant.understanding}
          {...(props.understandingEdit
            ? {
                editable: true,
                editError: props.understandingEdit.editError,
                onEditStart: props.understandingEdit.onEditStart,
                onSave: props.understandingEdit.onSave,
                onCancel: props.understandingEdit.onCancel,
              }
            : {})}
        />
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
      {showActions ? (
        <MessageActions
          text={settledAnswer}
          menuOpen={menuOpen}
          onMenuOpenChange={setMenuOpen}
          {...(props.onRegenerate ? { onRegenerate: props.onRegenerate } : {})}
        />
      ) : null}
    </div>
  );
}

export function ChatShell(props: {
  userEmail: string;
  /** Test seam: defaults to the browser composition root's client. */
  runtime?: AgentRuntimeClient;
  /**
   * Test seam: the thread-history + memory side panels' data source. Defaults
   * to the real `useChatSidebars` hook (fetches the same-origin BFF routes).
   * Injected in SSR/unit tests so the shell renders without a network.
   */
  sidebars?: ChatSidebarsState;
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
  // Left panel: thread history. The hook owns all lifecycle (F-R1); the shell
  // only renders + forwards callbacks. The injected `props.sidebars` overrides
  // it in tests. (The right "What I remember" column was removed in the UI
  // refresh — Phase 0 — though the memory half of the hook is retained.)
  const liveSidebars = useChatSidebars();
  const sidebars = props.sidebars ?? liveSidebars;
  // Durable persistence seam (plan §A3): on the first send auto-create the
  // thread row; on each completed turn persist it. Both delegate the BFF write
  // to the sidebars hook (F-R2/F-R9) and are fire-and-forget — the live chat
  // never blocks on a persistence miss. The BFF scopes storage to the verified
  // owner, so the client `user_id` here is non-authoritative.
  const persist = React.useMemo(
    () => ({
      onFirstSend: (threadId: string, firstMessage: string): void => {
        void sidebars.createThread(threadId, props.userEmail, firstMessage);
      },
      onTurnComplete: (
        threadId: string,
        turn: { user: string; assistant: string; turnId: string },
      ): void => {
        void sidebars.persistTurn(threadId, turn);
      },
    }),
    [sidebars, props.userEmail],
  );
  const {
    turns,
    busy,
    send,
    pausedTurnId,
    editError,
    pauseForEdit,
    saveUnderstanding,
    cancelEditAndResume,
    resumeThread,
    startNewChat,
  } = useAgentRun(runtime, persist);
  // Left-panel chrome (collapse / search / active tab). Cosmetic state only;
  // collapse persists to localStorage, search filters client-side.
  const chrome = useSidebarChrome();
  const [activeThreadId, setActiveThreadId] = React.useState<string | undefined>(
    undefined,
  );

  // Recents filtered by the live search query (pure; empty query → all).
  const visibleThreads = React.useMemo(
    () => filterThreadsByTitle(sidebars.threads, chrome.searchQuery),
    [sidebars.threads, chrome.searchQuery],
  );

  // New chat: reset the run to a blank conversation and drop any active-thread
  // highlight so no Recents row reads as current.
  const onNewChat = React.useCallback((): void => {
    startNewChat();
    setActiveThreadId(undefined);
  }, [startNewChat]);

  // Click-to-resume: fetch the selected thread's persisted history (sidebars
  // owns the BFF fetch, F-R1), replay it into the chat view, and bind the run
  // hook's thread id to it so the next `send` continues that checkpoint.
  const onSelectThread = React.useCallback(
    (id: string): void => {
      setActiveThreadId(id);
      void sidebars.loadThreadTurns(id).then((replayTurns) => {
        resumeThread(id, replayTurns);
      });
    },
    [sidebars, resumeThread],
  );

  // P3 §5: on phone the rail lives in an overlay drawer; picking a thread or
  // starting a new chat should dismiss it so the chat is visible immediately.
  // (Harmless at desktop widths where the drawer is never open.)
  const onSelectThreadMobile = React.useCallback(
    (id: string): void => {
      onSelectThread(id);
      chrome.setDrawerOpen(false);
    },
    [onSelectThread, chrome],
  );
  const onNewChatMobile = React.useCallback((): void => {
    onNewChat();
    chrome.setDrawerOpen(false);
  }, [onNewChat, chrome]);
  // Scroll container + stickiness: auto-scroll new turns into view only while
  // the user is already at the bottom; otherwise reveal the scroll-to-latest
  // button (P4 §6) and leave their scroll position alone.
  const { ref: scrollRef, isAtBottom, scrollToBottom } = useStickToBottom();

  // The understanding card is editable only on the latest turn while its
  // run is live (streaming or paused for this edit) — late edits are
  // rejected server-side anyway (409).
  const lastTurn = turns[turns.length - 1];
  const editableTurnId =
    lastTurn &&
    lastTurn.assistant.understanding &&
    lastTurn.assistant.status === "streaming" &&
    (busy || pausedTurnId === lastTurn.id)
      ? lastTurn.id
      : null;

  React.useEffect(() => {
    // Only follow the stream if the user hasn't scrolled up to read history.
    if (isAtBottom) scrollToBottom("smooth");
  }, [turns, isAtBottom, scrollToBottom]);

  // Eval disclosure joins recalled KEYS against the owner's loaded memory panel.
  // Reload when a turn recalls so CRUD-seeded / newly stored rows are present
  // (Mem0 list is authoritative; the mount-time fetch may be stale).
  const recalledKeySignature = React.useMemo(() => {
    if (!evalMode) return "";
    return turns
      .flatMap((t) => [...t.assistant.recalledKeys])
      .join(",");
  }, [evalMode, turns]);

  React.useEffect(() => {
    if (!recalledKeySignature) return;
    void sidebars.reloadMemories();
  }, [recalledKeySignature, sidebars]);

  return (
    <div
      className="min-h-dvh grid grid-rows-[auto_auto_1fr]"
      {...(props.evalCase ? { "data-eval-case": props.evalCase } : {})}
    >
      {/* Header (spans the full width above the three columns) */}
      {/* P4 §4a: pad the top + horizontal safe-area insets so the header clears
         the notch / Dynamic Island when wrapped (no-op off-device). */}
      {/* `data-tauri-drag-region` makes the header bar drag the native window in
         the Tauri shell (ignored as an unknown attr in the browser). Interactive
         children below opt out automatically (their own pointer handlers win).
         The `.tauri-shell` left-pad (globals.css) clears the overlay traffic
         lights — applied only when the shell injects that html class. */}
      <header
        data-tauri-drag-region
        className="flex items-center justify-between px-4 py-3 pt-[max(0.75rem,var(--safe-top))] pl-[max(1rem,var(--safe-left))] pr-[max(1rem,var(--safe-right))]"
      >
        <div className="flex items-center gap-2">
          {/* P3 §5: hamburger opens the thread-rail drawer on phone. Hidden at
             lg where the inline rail is shown side-by-side. */}
          <button
            type="button"
            data-testid="drawer-toggle"
            aria-label="Open conversations"
            aria-expanded={chrome.drawerOpen}
            aria-controls="thread-drawer"
            onClick={() => chrome.setDrawerOpen(true)}
            // 44×44 touch target (§4c/HIG) — the icon is size-5, the hit area
            // is the full button.
            className="lg:hidden -ml-2 size-11 text-fg bg-transparent border-0 cursor-pointer hover:text-accent flex items-center justify-center"
          >
            <Menu className="size-5" aria-hidden="true" />
          </button>
          <h1 className="text-lg font-semibold m-0">ReAct Agent</h1>
        </div>
        <div className="flex items-center gap-3">
          {props.evalCase ? (
            <span
              data-testid="eval-banner"
              className="font-mono text-xs uppercase tracking-wide px-2 py-0.5 rounded-sm bg-accent-light text-accent"
            >
              eval · {props.evalCase}
            </span>
          ) : null}
          {/* Email crowds the phone header — hidden below sm (§5 compact). */}
          <span className="hidden sm:inline text-sm text-muted">
            {props.userEmail}
          </span>
          <ThemeToggle />
          {/* §4c/HIG: the visible text is unchanged, but the hit area is padded
             to a 44pt-tall tap target (min-h-11 + horizontal padding). */}
          <Link
            href="/api/auth/sign-out"
            prefetch={false}
            className="inline-flex min-h-11 items-center px-2 text-sm text-muted hover:text-fg no-underline"
          >
            Sign out
          </Link>
        </div>
      </header>
      {/* Etched groove under the header (design .separator-etched), flush. */}
      <div className="separator-etched" aria-hidden="true" />

      {/*
       * Body: thread history (left) · chat (center). The right "What I
       * remember" column was removed in the UI refresh (Phase 0); MemoryPanel
       * is retained on disk but no longer mounted here. The left panel hides
       * on small screens (hidden lg:grid) so the chat column stays usable; the
       * center is always present.
       */}

      {/* P3 §5: mobile thread-rail drawer. Below lg the inline rail is hidden;
         the hamburger opens this left overlay Sheet with the same SidebarPanel.
         Radix handles overlay dismiss + focus trap + Escape; reduced-motion is
         honored by the Sheet primitive. Auto-closes on select/new-chat via the
         *Mobile handlers. */}
      <Sheet open={chrome.drawerOpen} onOpenChange={chrome.setDrawerOpen}>
        <SheetContent
          side="left"
          id="thread-drawer"
          data-testid="thread-drawer"
          className="w-[18rem] p-0 bg-surface-sunken lg:hidden"
          aria-label="Conversations"
        >
          <SheetTitle className="sr-only">Conversations</SheetTitle>
          <SidebarPanel
            threads={visibleThreads}
            {...(activeThreadId ? { activeThreadId } : {})}
            collapsed={false}
            searchOpen={chrome.searchOpen}
            searchQuery={chrome.searchQuery}
            activeTab={chrome.activeTab}
            onToggleCollapsed={chrome.toggleCollapsed}
            onToggleSearch={chrome.toggleSearch}
            onSearchQueryChange={chrome.setSearchQuery}
            onCloseSearch={chrome.closeSearch}
            onSelectTab={chrome.setActiveTab}
            onNewChat={onNewChatMobile}
            onSelectThread={onSelectThreadMobile}
            onRenameThread={(id, title) => void sidebars.renameThread(id, title)}
            onDeleteThread={(id) => void sidebars.deleteThread(id)}
          />
        </SheetContent>
      </Sheet>

      <div className="grid lg:grid-cols-[auto_2px_1fr] overflow-hidden">
        {/* Recessed rail (§2.6): surface-sunken keeps the thread history a
           half-step behind the chat canvas, Cursor-style. The rail↔chat divide
           is the etched groove below (separator-etched-v), not a flat border. */}
        <div className="hidden lg:block overflow-y-auto bg-surface-sunken">
          <SidebarPanel
            threads={visibleThreads}
            {...(activeThreadId ? { activeThreadId } : {})}
            collapsed={chrome.collapsed}
            searchOpen={chrome.searchOpen}
            searchQuery={chrome.searchQuery}
            activeTab={chrome.activeTab}
            onToggleCollapsed={chrome.toggleCollapsed}
            onToggleSearch={chrome.toggleSearch}
            onSearchQueryChange={chrome.setSearchQuery}
            onCloseSearch={chrome.closeSearch}
            onSelectTab={chrome.setActiveTab}
            onNewChat={onNewChat}
            onSelectThread={onSelectThread}
            onRenameThread={(id, title) => void sidebars.renameThread(id, title)}
            onDeleteThread={(id) => void sidebars.deleteThread(id)}
          />
        </div>

        {/* Etched groove between the rail and the chat (design
           .separator-etched-v). Hidden below lg where the rail itself hides. */}
        <div
          aria-hidden="true"
          className="separator-etched-v hidden lg:block"
        />

        {/* Chat column: scrollable messages + the pinned composer. The
           `relative` wrapper anchors the floating scroll-to-latest button. */}
        <div className="relative grid grid-rows-[1fr_auto] overflow-hidden">
          <main ref={scrollRef} className="overflow-y-auto p-3 sm:p-4">
            {turns.length === 0 ? (
              <div className="flex items-center justify-center h-full text-muted text-center">
                <div className="grid gap-2">
                  <p className="text-2xl m-0">What can I help you with?</p>
                  <p className="text-sm m-0">
                    Send a message to start a conversation.
                  </p>
                </div>
              </div>
            ) : (
              <div className="max-w-3xl mx-auto grid gap-4">
                {turns.map((turn) => (
                  <React.Fragment key={turn.id}>
                    <div className="bubble-user justify-self-end rounded-lg px-4 py-2 max-w-[80%]">
                      <span className="whitespace-pre-wrap">{turn.user}</span>
                    </div>
                    <div className="justify-self-start max-w-[80%] w-full grid gap-1">
                      {/*
                       * Transparent-recall affordance. The count is the
                       * per-turn recalledCount folded onto the run view from the
                       * memory_recalled domain event (backend route node →
                       * Custom 'memory_recalled' → reducer). Count only, never
                       * content; renders nothing at 0.
                       */}
                      <RecallIndicator count={turn.assistant.recalledCount} />
                      {/*
                       * Phase B (B2): per-turn recalled-memories eval/reject
                       * disclosure. Gated to the dev/eval surface so prod chat
                       * stays clean. The recalled KEYS (folded onto the run
                       * view) are joined against the owner's loaded memory
                       * panel to show content; Reject soft-suppresses globally.
                       */}
                      {evalMode ? (
                        <RecalledMemories
                          items={recalledItems(
                            turn.assistant.recalledKeys,
                            sidebars.memories,
                          )}
                          onReject={(key) =>
                            void sidebars.suppressMemory(key, true)
                          }
                          defaultOpen
                        />
                      ) : null}
                      <AssistantMessage
                        turn={turn}
                        evalMode={evalMode}
                        {...(busy || pausedTurnId !== null
                          ? {}
                          : { onRegenerate: () => void send(turn.user) })}
                        {...(turn.id === editableTurnId
                          ? {
                              understandingEdit: {
                                editError:
                                  pausedTurnId === turn.id ? editError : null,
                                onEditStart: () => pauseForEdit(turn.id),
                                onSave: (draft) =>
                                  void saveUnderstanding(turn.id, {
                                    restated_intent: draft.restated_intent,
                                    success_conditions: [
                                      ...draft.success_conditions,
                                    ],
                                  }),
                                onCancel: () =>
                                  void cancelEditAndResume(turn.id),
                              },
                            }
                          : {})}
                      />
                    </div>
                  </React.Fragment>
                ))}
              </div>
            )}
          </main>

          {/* Scroll-to-latest: appears when the user has scrolled up off the
             bottom during a conversation. Floats just above the composer,
             centered. 44pt hit area (§4c); motion-reduce safe. */}
          {!isAtBottom && turns.length > 0 ? (
            <button
              type="button"
              onClick={() => scrollToBottom("smooth")}
              aria-label="Scroll to latest"
              data-testid="scroll-to-bottom"
              className={cn(
                "absolute bottom-24 left-1/2 -translate-x-1/2 z-10",
                "flex size-11 items-center justify-center rounded-full",
                "bg-surface text-fg border border-border shadow-lg",
                "transition-colors cursor-pointer hover:bg-selected",
                "animate-in fade-in motion-reduce:animate-none",
              )}
            >
              <ArrowDown className="size-5" aria-hidden="true" />
            </button>
          ) : null}

          {/* Composer (pinned to the bottom of the chat column) */}
          {/* P4 §4a: pad the bottom safe-area inset so the composer sits above
             the home indicator / keyboard when wrapped (no-op off-device). */}
          <div className="max-w-3xl mx-auto w-full p-2 pb-[max(0.5rem,var(--safe-bottom))] pl-[max(0.5rem,var(--safe-left))] pr-[max(0.5rem,var(--safe-right))]">
            <Composer onSend={send} busy={busy || pausedTurnId !== null} />
          </div>
        </div>
      </div>
    </div>
  );
}
