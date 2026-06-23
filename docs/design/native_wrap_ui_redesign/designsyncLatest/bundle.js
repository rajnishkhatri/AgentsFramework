/* @ds-bundle: {"format":3,"namespace":"AgentsFrameworkUI_f8ce5c","components":[{"name":"ChatShell","sourcePath":"app/chat-shell.tsx"},{"name":"RootLayout","sourcePath":"app/layout.tsx"},{"name":"HomePage","sourcePath":"app/page.tsx"},{"name":"ThemeProvider","sourcePath":"app/theme-provider.tsx"},{"name":"CodeBlock","sourcePath":"components/chat/CodeBlock.tsx"},{"name":"Composer","sourcePath":"components/chat/Composer.tsx"},{"name":"RunControls","sourcePath":"components/chat/RunControls.tsx"},{"name":"SidebarPanel","sourcePath":"components/chat/SidebarPanel.tsx"},{"name":"SidebarTabBar","sourcePath":"components/chat/SidebarTabBar.tsx"},{"name":"StreamingMarkdown","sourcePath":"components/chat/StreamingMarkdown.tsx"},{"name":"TaskList","sourcePath":"components/chat/TaskList.tsx"},{"name":"TaskUnderstandingCard","sourcePath":"components/chat/TaskUnderstandingCard.tsx"},{"name":"ThemeToggle","sourcePath":"components/chat/ThemeToggle.tsx"},{"name":"ThreadSidebar","sourcePath":"components/chat/ThreadSidebar.tsx"},{"name":"PyramidPanel","sourcePath":"components/generative/PyramidPanel.tsx"},{"name":"SandboxedCanvas","sourcePath":"components/generative/SandboxedCanvas.tsx"},{"name":"MemoryPanel","sourcePath":"components/memory/MemoryPanel.tsx"},{"name":"RecallIndicator","sourcePath":"components/memory/RecallIndicator.tsx"},{"name":"RecalledMemories","sourcePath":"components/memory/RecalledMemories.tsx"},{"name":"ToolCard","sourcePath":"components/tools/ToolCard.tsx"},{"name":"Button","sourcePath":"components/ui/button.tsx"},{"name":"AdapterProvider","sourcePath":"lib/composition_react.tsx"}],"sourceHashes":{"app/chat-shell.tsx":"59e8b6e85367","app/layout.tsx":"39b3f9eefcce","app/page.tsx":"10cc09dc228f","app/theme-provider.tsx":"8472228d5ada","components/chat/CodeBlock.tsx":"a97b9c0e9149","components/chat/Composer.tsx":"70d502fa1640","components/chat/RunControls.tsx":"e913b4aa4b78","components/chat/SidebarPanel.tsx":"2290c8de8932","components/chat/SidebarTabBar.tsx":"de55cf9572f9","components/chat/StreamingMarkdown.tsx":"db603f991052","components/chat/TaskList.tsx":"de6f3a0fc148","components/chat/TaskUnderstandingCard.tsx":"ce9b7412dbf6","components/chat/ThemeToggle.tsx":"7afeff075290","components/chat/ThreadSidebar.tsx":"c8dfad962095","components/generative/PyramidPanel.tsx":"7b2716829f0f","components/generative/SandboxedCanvas.tsx":"aba6ac8c630e","components/memory/MemoryPanel.tsx":"8bba55b7c687","components/memory/RecallIndicator.tsx":"44c3d38069cd","components/memory/RecalledMemories.tsx":"30ad213cbd01","components/tools/ToolCard.tsx":"4634346a4bd6","components/ui/button.tsx":"79949f7b292f","lib/composition_react.tsx":"1b05fbe07951"},"inlinedExternals":[],"unexposedExports":[{"name":"dynamic","sourcePath":"app/page.tsx"},{"name":"metadata","sourcePath":"app/layout.tsx"},{"name":"recalledItems","sourcePath":"app/chat-shell.tsx"},{"name":"useAdapters","sourcePath":"lib/composition_react.tsx"}]} */

(() => {

const __ds_ns = (window.AgentsFrameworkUI_f8ce5c = window.AgentsFrameworkUI_f8ce5c || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// app/chat-shell.tsx
try { (() => {
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

function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Phase B: resolve a turn's recalled memory KEYS against the owner's loaded
 * memory panel into displayable items (key + type + content). Pure + order-
 * preserving (recall order). A key with no matching panel item is dropped — the
 * recall wire event carries keys only (never content), so a key the panel hasn't
 * loaded simply isn't shown rather than rendering a contentless row.
 */
function recalledItems(keys, memories) {
  if (keys.length === 0) return [];
  const byKey = new Map(memories.map(m => [m.key, m]));
  const out = [];
  for (const key of keys) {
    const item = byKey.get(key);
    if (item) out.push(item);
  }
  return out;
}
const PHASE_LABEL = {
  connecting: "connecting…",
  thinking: "thinking…",
  tool: "using tools…",
  writing: "writing…",
  done: "done",
  error: "error"
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
function RunStatusLine(props) {
  const {
    view,
    phase
  } = props;
  if (view.status === "complete") {
    return /*#__PURE__*/React.createElement("p", {
      "data-testid": "terminal-marker",
      className: "text-xs text-muted m-0",
      "aria-label": "Run complete"
    }, "\u2713 done");
  }
  if (view.status !== "streaming") return null;
  const runningTool = [...view.segments].reverse().find(s => s.kind === "tool" && s.request.status === "running");
  const label = runningTool && runningTool.kind === "tool" ? `using ${runningTool.request.tool_name}…` : view.step && phase === "thinking" ? `step ${view.step.count} · ${view.step.name}…` : PHASE_LABEL[phase];
  const narration = narrateTrajectory(view.segments);
  return /*#__PURE__*/React.createElement("div", {
    "data-testid": "run-status",
    "aria-live": "polite",
    className: "text-xs text-muted m-0 grid gap-0.5"
  }, /*#__PURE__*/React.createElement("p", {
    className: props.evalMode ? "m-0" : "m-0 animate-pulse"
  }, label), narration ?
  /*#__PURE__*/
  // Reasoning layer: sans italic muted (Appendix A) -- visually
  // distinct from the answer so thinking is never read as prose.
  React.createElement("p", {
    "data-testid": "reasoning-narration",
    className: "m-0 italic"
  }, narration) : null);
}

/**
 * F6: copyable trace_id chip -- one-click UI ↔ Langfuse correlation for
 * annotators. The trace_id is forwarded from the backend (F-R7), never
 * generated here. Gated to eval mode so prod chat stays clean.
 */
function TraceChip(props) {
  const [copied, setCopied] = React.useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(props.traceId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1_500);
    } catch {
      /* clipboard unavailable -- chip stays idle */
    }
  }
  return /*#__PURE__*/React.createElement("button", {
    type: "button",
    "data-testid": "trace-chip",
    onClick: copy,
    "aria-label": "Copy trace id",
    className: "justify-self-start font-mono text-xs text-muted bg-surface border border-border rounded-sm px-2 py-0.5 cursor-pointer hover:text-fg"
  }, copied ? "copied" : `trace ${props.traceId}`);
}
function AssistantMessage(props) {
  const {
    assistant
  } = props.turn;
  const toolCount = assistant.segments.filter(s => s.kind === "tool").length;
  const phase = deriveRunPhase(assistant);
  const fallbackAnswer = synthesizeFallbackAnswer(assistant);
  let firstTextSeen = false;
  return /*#__PURE__*/React.createElement("div", {
    "data-state": assistant.status,
    "data-run-phase": phase,
    "data-tool-count": toolCount,
    "data-testid": "assistant-message",
    className: "grid gap-2"
  }, assistant.understanding ?
  /*#__PURE__*/
  // Phase 3 soft gate: the card shows the agent's restated intent +
  // success checklist while tokens keep streaming (FD5 — it must
  // never block the answer). Phase 4: on the live turn the card is
  // editable — Edit pauses the run, Save POSTs + resumes.
  React.createElement(TaskUnderstandingCard, _extends({
    understanding: assistant.understanding
  }, props.understandingEdit ? {
    editable: true,
    editError: props.understandingEdit.editError,
    onEditStart: props.understandingEdit.onEditStart,
    onSave: props.understandingEdit.onSave,
    onCancel: props.understandingEdit.onCancel
  } : {})) : null, assistant.todos ? /*#__PURE__*/React.createElement(TaskList, {
    view: assistant.todos
  }) : null, assistant.segments.map((seg, i) => {
    if (seg.kind !== "text") {
      return /*#__PURE__*/React.createElement(ToolCard, {
        key: seg.request.tool_call_id,
        request: seg.request
      });
    }
    // F5: badge + meter render once, on the first text segment.
    const isFirstText = !firstTextSeen;
    firstTextSeen = true;
    return /*#__PURE__*/React.createElement(StreamingMarkdown, _extends({
      key: `text-${i}`,
      text: seg.text
    }, isFirstText && assistant.modelBadge ? {
      modelBadge: assistant.modelBadge
    } : {}, isFirstText && assistant.step ? {
      step: assistant.step
    } : {}));
  }), fallbackAnswer !== null ? /*#__PURE__*/React.createElement("div", {
    "data-testid": "fallback-answer"
  }, /*#__PURE__*/React.createElement(StreamingMarkdown, {
    text: fallbackAnswer
  }), /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-muted m-0 italic"
  }, "summary generated from tool results")) : null, assistant.status === "error" ? /*#__PURE__*/React.createElement("p", {
    role: "alert",
    className: "text-sm text-red-600 dark:text-red-400 m-0"
  }, assistant.errorMessage ?? "The run failed.") : null, assistant.reasoning ?
  /*#__PURE__*/
  // F10 Tier-2: progressive disclosure -- the recap stays collapsed
  // unless expanded. Eval mode pre-opens it so the settled recap is
  // part of the capture. Reasoning layer typography (Appendix A):
  // never styled like the answer.
  React.createElement("details", {
    "data-testid": "reasoning-summary",
    open: props.evalMode ?? false,
    className: "text-xs text-muted"
  }, /*#__PURE__*/React.createElement("summary", {
    className: "cursor-pointer select-none"
  }, "Show reasoning"), /*#__PURE__*/React.createElement("p", {
    className: "m-0 mt-1 italic"
  }, assistant.reasoning)) : null, /*#__PURE__*/React.createElement(RunStatusLine, {
    view: assistant,
    phase: phase,
    evalMode: props.evalMode ?? false
  }), props.evalMode && assistant.traceId ? /*#__PURE__*/React.createElement(TraceChip, {
    traceId: assistant.traceId
  }) : null);
}
function ChatShell(props) {
  const injected = props.runtime;
  const runtime = React.useMemo(() => injected ?? browserRuntimeClient(), [injected]);
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
  const persist = React.useMemo(() => ({
    onFirstSend: (threadId, firstMessage) => {
      void sidebars.createThread(threadId, props.userEmail, firstMessage);
    },
    onTurnComplete: (threadId, turn) => {
      void sidebars.persistTurn(threadId, turn);
    }
  }), [sidebars, props.userEmail]);
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
    startNewChat
  } = useAgentRun(runtime, persist);
  // Left-panel chrome (collapse / search / active tab). Cosmetic state only;
  // collapse persists to localStorage, search filters client-side.
  const chrome = useSidebarChrome();
  const [activeThreadId, setActiveThreadId] = React.useState(undefined);

  // Recents filtered by the live search query (pure; empty query → all).
  const visibleThreads = React.useMemo(() => filterThreadsByTitle(sidebars.threads, chrome.searchQuery), [sidebars.threads, chrome.searchQuery]);

  // New chat: reset the run to a blank conversation and drop any active-thread
  // highlight so no Recents row reads as current.
  const onNewChat = React.useCallback(() => {
    startNewChat();
    setActiveThreadId(undefined);
  }, [startNewChat]);

  // Click-to-resume: fetch the selected thread's persisted history (sidebars
  // owns the BFF fetch, F-R1), replay it into the chat view, and bind the run
  // hook's thread id to it so the next `send` continues that checkpoint.
  const onSelectThread = React.useCallback(id => {
    setActiveThreadId(id);
    void sidebars.loadThreadTurns(id).then(replayTurns => {
      resumeThread(id, replayTurns);
    });
  }, [sidebars, resumeThread]);
  const bottomRef = React.useRef(null);

  // The understanding card is editable only on the latest turn while its
  // run is live (streaming or paused for this edit) — late edits are
  // rejected server-side anyway (409).
  const lastTurn = turns[turns.length - 1];
  const editableTurnId = lastTurn && lastTurn.assistant.understanding && lastTurn.assistant.status === "streaming" && (busy || pausedTurnId === lastTurn.id) ? lastTurn.id : null;
  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth"
    });
  }, [turns]);

  // Eval disclosure joins recalled KEYS against the owner's loaded memory panel.
  // Reload when a turn recalls so CRUD-seeded / newly stored rows are present
  // (Mem0 list is authoritative; the mount-time fetch may be stale).
  const recalledKeySignature = React.useMemo(() => {
    if (!evalMode) return "";
    return turns.flatMap(t => [...t.assistant.recalledKeys]).join(",");
  }, [evalMode, turns]);
  React.useEffect(() => {
    if (!recalledKeySignature) return;
    void sidebars.reloadMemories();
  }, [recalledKeySignature, sidebars]);
  return /*#__PURE__*/React.createElement("div", _extends({
    className: "min-h-dvh grid grid-rows-[auto_1fr]"
  }, props.evalCase ? {
    "data-eval-case": props.evalCase
  } : {}), /*#__PURE__*/React.createElement("header", {
    className: "flex items-center justify-between px-4 py-3 border-b border-border-light"
  }, /*#__PURE__*/React.createElement("h1", {
    className: "text-lg font-semibold m-0"
  }, "ReAct Agent"), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-3"
  }, props.evalCase ? /*#__PURE__*/React.createElement("span", {
    "data-testid": "eval-banner",
    className: "font-mono text-xs uppercase tracking-wide px-2 py-0.5 rounded-sm bg-accent-light text-accent"
  }, "eval \xB7 ", props.evalCase) : null, /*#__PURE__*/React.createElement("span", {
    className: "text-sm text-muted"
  }, props.userEmail), /*#__PURE__*/React.createElement(ThemeToggle, null), /*#__PURE__*/React.createElement(Link, {
    href: "/api/auth/sign-out",
    prefetch: false,
    className: "text-sm text-muted hover:text-fg no-underline"
  }, "Sign out"))), /*#__PURE__*/React.createElement("div", {
    className: "grid lg:grid-cols-[auto_1fr] overflow-hidden"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hidden lg:block overflow-y-auto"
  }, /*#__PURE__*/React.createElement(SidebarPanel, _extends({
    threads: visibleThreads
  }, activeThreadId ? {
    activeThreadId
  } : {}, {
    collapsed: chrome.collapsed,
    searchOpen: chrome.searchOpen,
    searchQuery: chrome.searchQuery,
    activeTab: chrome.activeTab,
    onToggleCollapsed: chrome.toggleCollapsed,
    onToggleSearch: chrome.toggleSearch,
    onSearchQueryChange: chrome.setSearchQuery,
    onCloseSearch: chrome.closeSearch,
    onSelectTab: chrome.setActiveTab,
    onNewChat: onNewChat,
    onSelectThread: onSelectThread,
    onRenameThread: (id, title) => void sidebars.renameThread(id, title),
    onDeleteThread: id => void sidebars.deleteThread(id)
  }))), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-rows-[1fr_auto] overflow-hidden"
  }, /*#__PURE__*/React.createElement("main", {
    className: "overflow-y-auto p-4"
  }, turns.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-center h-full text-muted text-center"
  }, /*#__PURE__*/React.createElement("div", {
    className: "grid gap-2"
  }, /*#__PURE__*/React.createElement("p", {
    className: "text-2xl m-0"
  }, "What can I help you with?"), /*#__PURE__*/React.createElement("p", {
    className: "text-sm m-0"
  }, "Send a message to start a conversation."))) : /*#__PURE__*/React.createElement("div", {
    className: "max-w-3xl mx-auto grid gap-4"
  }, turns.map(turn => /*#__PURE__*/React.createElement(React.Fragment, {
    key: turn.id
  }, /*#__PURE__*/React.createElement("div", {
    className: "justify-self-end bg-accent text-white rounded-lg px-4 py-2 max-w-[80%]"
  }, /*#__PURE__*/React.createElement("span", {
    className: "whitespace-pre-wrap"
  }, turn.user)), /*#__PURE__*/React.createElement("div", {
    className: "justify-self-start max-w-[80%] w-full grid gap-1"
  }, /*#__PURE__*/React.createElement(RecallIndicator, {
    count: turn.assistant.recalledCount
  }), evalMode ? /*#__PURE__*/React.createElement(RecalledMemories, {
    items: recalledItems(turn.assistant.recalledKeys, sidebars.memories),
    onReject: key => void sidebars.suppressMemory(key, true),
    defaultOpen: true
  }) : null, /*#__PURE__*/React.createElement(AssistantMessage, _extends({
    turn: turn,
    evalMode: evalMode
  }, turn.id === editableTurnId ? {
    understandingEdit: {
      editError: pausedTurnId === turn.id ? editError : null,
      onEditStart: () => pauseForEdit(turn.id),
      onSave: draft => void saveUnderstanding(turn.id, {
        restated_intent: draft.restated_intent,
        success_conditions: [...draft.success_conditions]
      }),
      onCancel: () => void cancelEditAndResume(turn.id)
    }
  } : {}))))), /*#__PURE__*/React.createElement("div", {
    ref: bottomRef
  }))), /*#__PURE__*/React.createElement("div", {
    className: "max-w-3xl mx-auto w-full p-2"
  }, /*#__PURE__*/React.createElement(Composer, {
    onSend: send,
    busy: busy || pausedTurnId !== null
  })))));
}
Object.assign(__ds_scope, { recalledItems, ChatShell });
})(); } catch (e) { __ds_ns.__errors.push({ path: "app/chat-shell.tsx", error: String((e && e.message) || e) }); }

// app/layout.tsx
try { (() => {
/**
 * Root layout (S3.7.1).
 *
 * RSC by default (no "use client" -- B1, U1). Reads the per-request CSP
 * nonce via `await headers()` (B3 / FD3.CSP3) so any inline script we
 * inject is whitelisted by the strict CSP set in `middleware.ts`.
 *
 * Per FE-AP-12 (AUTO-REJECT): the nonce is exposed via a `<meta>` tag,
 * NEVER via `dangerouslySetInnerHTML`. Client components read it through
 * `document.querySelector('meta[name="csp-nonce"]')?.getAttribute('content')`.
 *
 * Theme management uses `next-themes` per Style Guide §2 prescription.
 * The `ThemeProvider` is a client component wrapper imported from a leaf
 * file to keep the root layout as RSC.
 */

const metadata = {
  title: "Agent",
  description: "Claude-class chat with the ReAct agent"
};
async function RootLayout({
  children
}) {
  const h = await headers();
  const nonce = h.get("x-nonce") ?? "";
  return /*#__PURE__*/React.createElement("html", {
    lang: "en",
    suppressHydrationWarning: true,
    className: `${GeistSans.variable} ${GeistMono.variable}`
  }, /*#__PURE__*/React.createElement("head", null, /*#__PURE__*/React.createElement("meta", {
    name: "csp-nonce",
    content: nonce
  })), /*#__PURE__*/React.createElement("body", null, /*#__PURE__*/React.createElement(ThemeProvider, {
    attribute: "data-theme",
    defaultTheme: "system",
    enableSystem: true
  }, children)));
}
Object.assign(__ds_scope, { metadata, RootLayout });
})(); } catch (e) { __ds_ns.__errors.push({ path: "app/layout.tsx", error: String((e && e.message) || e) }); }

// app/page.tsx
try { (() => {
/**
 * Landing page (S3.7.1 / S3.8.1).
 *
 * RSC by default. Renders a sign-in CTA when no WorkOS session is present;
 * otherwise it renders the chat shell with Composer, streaming output,
 * thread sidebar, theme toggle, and run controls.
 *
 * Test escape hatch (`E2E_BYPASS_AUTH=1`): renders the chat shell with a
 * synthetic user when the env flag is set AND `NODE_ENV !== "production"`.
 * The double gate ensures this branch can never be enabled in a
 * production build. Used by `e2e/visual/` to capture chat-shell baselines
 * without going through WorkOS. See `e2e/visual/README.md`.
 */

const dynamic = "force-dynamic";
const E2E_BYPASS_AUTH = process.env.NODE_ENV !== "production" && process.env.E2E_BYPASS_AUTH === "1";
async function HomePage(props) {
  // F7 eval-mode capture surface: `?eval=GJ-…` pins the case id and
  // freezes the UI for deterministic, admissible captures.
  const {
    eval: evalCase
  } = await props.searchParams;
  if (E2E_BYPASS_AUTH) {
    return /*#__PURE__*/React.createElement(__ds_scope.ChatShell, {
      userEmail: "e2e@example.com",
      evalCase: evalCase ?? null
    });
  }
  const {
    user
  } = await withAuth();
  if (user) {
    return /*#__PURE__*/React.createElement(__ds_scope.ChatShell, {
      userEmail: user.email ?? user.firstName ?? "Agent",
      evalCase: evalCase ?? null
    });
  }
  return /*#__PURE__*/React.createElement("main", {
    className: "min-h-dvh flex items-center justify-center p-8"
  }, /*#__PURE__*/React.createElement("section", {
    className: "max-w-lg text-center grid gap-4"
  }, /*#__PURE__*/React.createElement("h1", {
    className: "text-3xl leading-tight m-0"
  }, "ReAct Agent"), /*#__PURE__*/React.createElement("p", {
    className: "text-muted m-0"
  }, "Claude-class chat with a self-hosted LangGraph runtime."), /*#__PURE__*/React.createElement(Button, {
    asChild: true,
    className: "justify-self-center"
  }, /*#__PURE__*/React.createElement(Link, {
    href: "/api/auth/sign-in"
  }, "Sign in with WorkOS"))));
}
Object.assign(__ds_scope, { dynamic, HomePage });
})(); } catch (e) { __ds_ns.__errors.push({ path: "app/page.tsx", error: String((e && e.message) || e) }); }

// app/theme-provider.tsx
try { (() => {
// B1: 'use client' required — ThemeProvider from next-themes uses React context.
"use client";

function ThemeProvider(props) {
  return /*#__PURE__*/React.createElement(NextThemesProvider, props);
}
Object.assign(__ds_scope, { ThemeProvider });
})(); } catch (e) { __ds_ns.__errors.push({ path: "app/theme-provider.tsx", error: String((e && e.message) || e) }); }

// components/chat/CodeBlock.tsx
try { (() => {
/**
 * Fenced code block with language tag + copy button (eval-UI F4).
 *
 * Leaf "use client" boundary: the copy interaction needs
 * `navigator.clipboard`. No syntax-highlighting dependency -- mono
 * rendering per the Appendix A type system; highlighting can layer on
 * later without changing this surface.
 */

"use client";

function CodeBlock(props) {
  const [copied, setCopied] = React.useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(props.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1_500);
    } catch {
      // Clipboard unavailable (permissions / insecure context) -- the
      // button simply stays in its idle state.
    }
  }
  return /*#__PURE__*/React.createElement("div", {
    "data-testid": "code-block",
    className: "border border-border rounded-md my-2 bg-surface overflow-hidden"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-between px-3 py-1 border-b border-border-light"
  }, /*#__PURE__*/React.createElement("span", {
    className: "font-mono text-xs text-muted uppercase tracking-wide"
  }, props.language ?? "text"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    "data-testid": "copy-code",
    onClick: copy,
    "aria-label": "Copy code",
    className: "font-mono text-xs text-muted hover:text-fg bg-transparent border-0 cursor-pointer"
  }, copied ? "copied" : "copy")), /*#__PURE__*/React.createElement("pre", {
    className: "overflow-auto m-0 px-3 py-2 font-mono text-sm leading-normal"
  }, /*#__PURE__*/React.createElement("code", null, props.code)));
}
Object.assign(__ds_scope, { CodeBlock });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/CodeBlock.tsx", error: String((e && e.message) || e) }); }

// components/chat/Composer.tsx
try { (() => {
/**
 * Mobile-first responsive composer (S3.8.5, F4).
 *
 * Keyboard shortcuts: Enter submits. ⌘↩ / Ctrl↩ / Shift↩ insert a newline.
 *
 * IME guard (FD2.U_IME): the submit branch is suppressed while an IME
 * composition session is in flight (`e.nativeEvent.isComposing === true`).
 * Without the guard, the Enter key that confirms a kana/hangul/pinyin
 * candidate selection would also fire Enter and double-fire onSend.
 *
 * Autosize (FD2.U_AUTOSIZE): the textarea uses CSS `field-sizing: content`
 * (Tailwind v4 arbitrary property) to grow with content up to a documented
 * max of 6 lines, then scrolls. `min-h-[2.5rem]` and `max-h-[12rem]`
 * (~6 × 2rem line-height) bracket the autosize range. `resize-y` is kept
 * as a secondary manual-drag override so the user can still nudge the
 * height when desired; CSS field-sizing is the primary growth signal so
 * mobile keyboards never see a fixed-height textarea (F4).
 */

// B1: 'use client' required — useState for body text, useRef for textarea,
// onKeyDown / onChange / onSubmit event handlers are browser-only APIs.
"use client";

function Composer(props) {
  const [body, setBody] = React.useState("");
  const taRef = React.useRef(null);
  function submit() {
    const trimmed = body.trim();
    if (!trimmed || props.busy) return;
    void props.onSend(trimmed);
    setBody("");
  }
  function onKeyDown(e) {
    const isSubmit = e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey && !e.nativeEvent.isComposing;
    if (isSubmit) {
      e.preventDefault();
      submit();
    }
  }
  return /*#__PURE__*/React.createElement("form", {
    onSubmit: e => {
      e.preventDefault();
      submit();
    },
    className: "flex gap-2 p-3 border-t border-border-light bg-bg"
  }, /*#__PURE__*/React.createElement("textarea", {
    ref: taRef,
    rows: 1,
    value: body,
    placeholder: props.placeholder ?? "Send a message… (⌘↩ for newline)",
    onChange: e => setBody(e.target.value),
    onKeyDown: onKeyDown,
    "aria-label": "Compose message",
    className: cn("flex-1 bg-transparent text-fg border border-border", "rounded-md px-3 py-2 text-[0.95rem] font-[inherit]", "[field-sizing:content] min-h-[2.5rem] max-h-[12rem]", "resize-y")
  }), /*#__PURE__*/React.createElement("button", {
    type: "submit",
    disabled: props.busy || body.trim().length === 0,
    "aria-label": "Send",
    className: cn("bg-accent text-white border-0 rounded-md px-4", "font-semibold cursor-pointer", "disabled:cursor-not-allowed disabled:opacity-60")
  }, "Send"));
}
Object.assign(__ds_scope, { Composer });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/Composer.tsx", error: String((e && e.message) || e) }); }

// components/chat/RunControls.tsx
try { (() => {
/**
 * Stop / regenerate / edit-and-resend controls (S3.8.7, F3).
 *
 * Pure presentation. The handler callbacks come from the chat page, which
 * routes them into `UIRuntime.{stop,regenerate,editAndResend}` via the
 * adapter context (composition).
 */

// B1: 'use client' required — onClick event handlers are non-serializable
// props that cannot cross the RSC boundary.
"use client";

function RunControls(props) {
  return /*#__PURE__*/React.createElement("div", {
    role: "toolbar",
    "aria-label": "Run controls",
    className: "flex gap-2"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    size: "sm",
    onClick: props.onStop,
    disabled: !props.isRunning
  }, "Stop"), /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    size: "sm",
    onClick: props.onRegenerate
  }, "Regenerate"), /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    size: "sm",
    onClick: props.onEditResend
  }, "Edit & resend"));
}
Object.assign(__ds_scope, { RunControls });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/RunControls.tsx", error: String((e && e.message) || e) }); }

// components/chat/SidebarTabBar.tsx
try { (() => {
// Pure presentational leaf (F-R1): renders the nav tab group from a data table
// and reports selection via onSelect. No state, no lifecycle — the chrome hook
// at the shell level owns `activeTab`. Adding Cowork/Code later is appending to
// TABS, not a rewrite (UI refresh plan §D4).
"use client";

const TABS = [{
  id: "chat",
  label: "Chat"
}];
function SidebarTabBar(props) {
  return /*#__PURE__*/React.createElement("div", {
    role: "tablist",
    "aria-label": "Sidebar sections",
    "data-testid": "sidebar-tabbar",
    className: "flex items-center gap-1"
  }, TABS.map(tab => {
    const selected = tab.id === props.activeTab;
    return /*#__PURE__*/React.createElement("button", {
      key: tab.id,
      type: "button",
      role: "tab",
      "aria-selected": selected,
      "data-testid": `sidebar-tab-${tab.id}`,
      onClick: () => props.onSelect?.(tab.id),
      className: cn("px-2.5 py-1 rounded-sm text-sm cursor-pointer bg-transparent border-0", selected ? "text-fg font-medium bg-accent-light" : "text-muted hover:text-fg")
    }, tab.label);
  }));
}
Object.assign(__ds_scope, { SidebarTabBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/SidebarTabBar.tsx", error: String((e && e.message) || e) }); }

// components/chat/StreamingMarkdown.tsx
try { (() => {
/**
 * Streaming markdown surface (S3.8.1, F2; full rendering eval-UI F4).
 *
 * RSC by default? No -- streaming display needs client state, so this is a
 * leaf "use client" boundary (B1, U2). The parent shell is RSC.
 *
 * - ARIA live region uses `aria-live="polite"` (NEVER `assertive`,
 *   FE-AP-5 AUTO-REJECT).
 * - Focus does not move on incoming tokens (U5).
 * - No `dangerouslySetInnerHTML` (FE-AP-5 family auto-reject):
 *   react-markdown renders a React element tree, never raw HTML, and raw
 *   HTML in the source text is NOT enabled (no rehype-raw).
 * - Mid-stream safety: `stabilizeStreamingMarkdown` closes dangling
 *   code fences before each parse so partial tokens never flash broken
 *   markup.
 * - Typography per Appendix A: answer = sans/base, headings = sans
 *   semibold, inline code = mono chip on a tinted background, fenced
 *   code = CodeBlock (language tag + copy button), tables = clean
 *   bordered rows.
 */

"use client";

function extractText(node) {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (React.isValidElement(node)) {
    return extractText(node.props.children);
  }
  return "";
}
const MD_COMPONENTS = {
  h1: p => /*#__PURE__*/React.createElement("h1", {
    className: "text-2xl font-semibold mt-4 mb-2"
  }, p.children),
  h2: p => /*#__PURE__*/React.createElement("h2", {
    className: "text-xl font-semibold mt-4 mb-2"
  }, p.children),
  h3: p => /*#__PURE__*/React.createElement("h3", {
    className: "text-lg font-semibold mt-3 mb-1"
  }, p.children),
  p: p => /*#__PURE__*/React.createElement("p", {
    className: "my-2 leading-relaxed"
  }, p.children),
  ul: p => /*#__PURE__*/React.createElement("ul", {
    className: "my-2 pl-6 list-disc grid gap-1"
  }, p.children),
  ol: p => /*#__PURE__*/React.createElement("ol", {
    className: "my-2 pl-6 list-decimal grid gap-1"
  }, p.children),
  a: p => /*#__PURE__*/React.createElement("a", {
    href: p.href,
    className: "text-accent underline",
    rel: "noreferrer noopener"
  }, p.children),
  table: p => /*#__PURE__*/React.createElement("div", {
    className: "overflow-x-auto my-2"
  }, /*#__PURE__*/React.createElement("table", {
    className: "border-collapse w-full text-sm"
  }, p.children)),
  th: p => /*#__PURE__*/React.createElement("th", {
    className: "border border-border px-3 py-1.5 text-left font-semibold bg-surface"
  }, p.children),
  td: p => /*#__PURE__*/React.createElement("td", {
    className: "border border-border px-3 py-1.5"
  }, p.children),
  blockquote: p => /*#__PURE__*/React.createElement("blockquote", {
    className: "border-l-2 border-border pl-3 my-2 text-muted"
  }, p.children),
  pre: p => {
    // react-markdown wraps fenced blocks as <pre><code class="language-x">.
    const child = React.Children.toArray(p.children)[0];
    if (React.isValidElement(child)) {
      const childProps = child.props;
      const match = /language-(\S+)/.exec(childProps.className ?? "");
      return /*#__PURE__*/React.createElement(CodeBlock, {
        language: match?.[1] ?? null,
        code: extractText(childProps.children).replace(/\n$/, "")
      });
    }
    return /*#__PURE__*/React.createElement("pre", null, p.children);
  },
  code: p =>
  /*#__PURE__*/
  // Inline code only -- fenced blocks are intercepted at `pre` above.
  React.createElement("code", {
    className: "font-mono text-sm bg-accent-light text-fg rounded-sm px-1 py-0.5"
  }, p.children)
};
function StreamingMarkdown(props) {
  return /*#__PURE__*/React.createElement("article", {
    className: "grid gap-2 p-3 bg-bg text-fg"
  }, /*#__PURE__*/React.createElement("header", {
    className: "flex gap-2 items-center text-xs text-muted"
  }, props.modelBadge ? /*#__PURE__*/React.createElement("span", {
    "data-testid": "model-badge",
    className: cn("px-2 py-0.5 rounded-sm font-mono uppercase tracking-wide", "bg-accent-light text-accent font-semibold")
  }, props.modelBadge) : null, props.step ? /*#__PURE__*/React.createElement("span", {
    "data-testid": "step-meter",
    className: "font-mono"
  }, "step ", props.step.count, " \xB7 ", props.step.name) : null), /*#__PURE__*/React.createElement("div", {
    "aria-live": "polite",
    "aria-atomic": "false",
    className: "leading-relaxed"
  }, /*#__PURE__*/React.createElement(Markdown, {
    remarkPlugins: [remarkGfm],
    components: MD_COMPONENTS
  }, stabilizeStreamingMarkdown(props.text))));
}
Object.assign(__ds_scope, { StreamingMarkdown });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/StreamingMarkdown.tsx", error: String((e && e.message) || e) }); }

// components/chat/TaskList.tsx
try { (() => {
/**
 * Live task / todo checklist (eval-UI F9).
 *
 * Renders the `state_todo`-backed checklist projected by
 * `todo_list_projection`: one row per TodoItem with a status icon,
 * completed rows struck/dimmed, and a compact progress count. For the
 * wave-2 adversarial gold-set cells a visibly not-done row (pending /
 * cancelled) is primary `goal_met` evidence -- cancelled is NEVER
 * rendered as done.
 *
 * Deterministic hooks: `data-todo-count`, `data-todo-done`,
 * `data-testid="todo-{id}"`. Long lists collapse behind a native
 * <details> expander (progressive disclosure) with the first items
 * always visible.
 *
 * Per F-R2/F-R8: consumes wire types only; no SDK imports.
 */

const STATUS_ICON = {
  pending: "○",
  in_progress: "◐",
  completed: "✓",
  cancelled: "⊘"
};
const VISIBLE_CAP = 7;
function TodoRow(props) {
  const {
    todo
  } = props;
  return /*#__PURE__*/React.createElement("li", {
    "data-testid": `todo-${todo.id}`,
    "data-status": todo.status,
    className: cn("flex gap-2 items-baseline text-sm", todo.status === "completed" && "line-through text-muted", todo.status === "cancelled" && "text-muted", todo.status === "in_progress" && "font-medium")
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true"
  }, STATUS_ICON[todo.status]), /*#__PURE__*/React.createElement("span", null, todo.content));
}
function TaskList(props) {
  const {
    view
  } = props;
  const overflow = view.todos.length > VISIBLE_CAP;
  const head = overflow ? view.todos.slice(0, VISIBLE_CAP) : view.todos;
  const tail = overflow ? view.todos.slice(VISIBLE_CAP) : [];
  return /*#__PURE__*/React.createElement("section", {
    "data-testid": "task-list",
    "data-todo-count": view.total,
    "data-todo-done": view.done,
    "aria-label": "Task list",
    className: "border border-border rounded-md px-3 py-2 my-1 bg-surface grid gap-1"
  }, /*#__PURE__*/React.createElement("header", {
    className: "flex justify-between text-xs text-muted"
  }, /*#__PURE__*/React.createElement("span", null, "Tasks"), /*#__PURE__*/React.createElement("span", {
    "data-testid": "todo-progress"
  }, view.done, "/", view.total, " done")), /*#__PURE__*/React.createElement("ul", {
    className: "list-none m-0 p-0 grid gap-1"
  }, head.map(todo => /*#__PURE__*/React.createElement(TodoRow, {
    key: todo.id,
    todo: todo
  }))), overflow ? /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", {
    className: "cursor-pointer text-xs text-muted"
  }, "show all ", view.total), /*#__PURE__*/React.createElement("ul", {
    className: "list-none m-0 p-0 grid gap-1"
  }, tail.map(todo => /*#__PURE__*/React.createElement(TodoRow, {
    key: todo.id,
    todo: todo
  })))) : null);
}
Object.assign(__ds_scope, { TaskList });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/TaskList.tsx", error: String((e && e.message) || e) }); }

// components/chat/TaskUnderstandingCard.tsx
try { (() => {
/**
 * "Here's my understanding" soft-gate card (task_understanding plan §4.6,
 * Phase 3 display + Phase 4 edit mode).
 *
 * Renders the plan-time TaskUnderstanding artifact -- the restated intent
 * plus the success checklist the judge will score against -- while the run
 * keeps streaming (soft gate: it never blocks tokens). The provenance badge
 * tells the user whether the checklist was LLM-generated, the deterministic
 * floor, or their own edit.
 *
 * Edit mode (Phase 4): when `editable`, an Edit affordance pauses the run
 * (`onEditStart`), the intent + conditions become a small form, and Save
 * hands the draft to `onSave` (the hook POSTs it and resumes the thread).
 * Bounds mirror TaskUnderstandingEditRequest: intent 1..600, 2..7
 * conditions of 1..200 chars -- Save stays disabled outside them. All
 * lifecycle logic lives in the parent hook (F-R1): this component only
 * holds the draft.
 *
 * Deterministic hooks: `data-testid="task-understanding-card"`,
 * `data-source`, `data-condition-count`, `understanding-condition-{i}`,
 * `understanding-edit`, `understanding-intent-input`,
 * `understanding-condition-input-{i}`, `understanding-save`,
 * `understanding-cancel-edit`, `understanding-edit-error`.
 *
 * Per F-R1/F-R2/F-R8: typed props in, markup out -- no business logic, no
 * SDK imports, wire types only.
 */

const SOURCE_LABEL = {
  deterministic: "derived from task",
  generated: "AI-restated",
  user_edited: "edited by you"
};
const MAX_INTENT_LEN = 600;
const MAX_CONDITION_LEN = 200;
const MIN_CONDITIONS = 2;
const MAX_CONDITIONS = 7;
function draftIsValid(intent, conditions) {
  if (intent.trim().length === 0 || intent.length > MAX_INTENT_LEN) return false;
  if (conditions.length < MIN_CONDITIONS || conditions.length > MAX_CONDITIONS) {
    return false;
  }
  return conditions.every(c => c.trim().length > 0 && c.length <= MAX_CONDITION_LEN);
}
function TaskUnderstandingCard(props) {
  const {
    understanding
  } = props;
  // Edit mode is keyed to the artifact identity the draft was opened
  // against: a fresh artifact event (e.g. the post-resume user_edited
  // re-emit) supersedes the draft by derivation. Deliberately NOT an
  // effect -- a passive `setEditing(false)` reset races a fast Edit click
  // (the mount-commit effect can flush after the click and silently close
  // the form the user just opened).
  const [editingFor, setEditingFor] = React.useState(null);
  const [intent, setIntent] = React.useState("");
  const [conditions, setConditions] = React.useState([]);
  const editing = editingFor === understanding;
  function startEdit() {
    setIntent(understanding.restated_intent);
    setConditions(understanding.success_conditions);
    setEditingFor(understanding);
    props.onEditStart?.();
  }
  function setCondition(i, value) {
    setConditions(prev => prev.map((c, idx) => idx === i ? value : c));
  }
  if (editing) {
    const valid = draftIsValid(intent, conditions);
    return /*#__PURE__*/React.createElement("aside", {
      "data-testid": "task-understanding-card",
      "data-source": understanding.source,
      "data-condition-count": conditions.length,
      "data-editing": "true",
      role: "note",
      "aria-label": "Edit the agent's understanding of your task",
      className: "rounded-md border border-border bg-muted/30 p-3 text-sm grid gap-2"
    }, /*#__PURE__*/React.createElement("p", {
      className: "m-0 font-medium"
    }, "Correct my understanding"), /*#__PURE__*/React.createElement("textarea", {
      "data-testid": "understanding-intent-input",
      "aria-label": "Restated intent",
      value: intent,
      maxLength: MAX_INTENT_LEN,
      onChange: e => setIntent(e.target.value),
      className: "w-full rounded-sm border border-border bg-surface p-1 text-sm",
      rows: 2
    }), /*#__PURE__*/React.createElement("ul", {
      className: "m-0 list-none p-0 grid gap-1"
    }, conditions.map((condition, i) => /*#__PURE__*/React.createElement("li", {
      key: `draft-${i}`,
      className: "flex gap-2 items-center text-xs"
    }, /*#__PURE__*/React.createElement("span", {
      "aria-hidden": "true"
    }, "\u2610"), /*#__PURE__*/React.createElement("input", {
      "data-testid": `understanding-condition-input-${i}`,
      "aria-label": `Success condition ${i + 1}`,
      value: condition,
      maxLength: MAX_CONDITION_LEN,
      onChange: e => setCondition(i, e.target.value),
      className: "w-full rounded-sm border border-border bg-surface p-1 text-xs"
    }), /*#__PURE__*/React.createElement("button", {
      type: "button",
      "data-testid": `understanding-remove-condition-${i}`,
      "aria-label": `Remove condition ${i + 1}`,
      disabled: conditions.length <= MIN_CONDITIONS,
      onClick: () => setConditions(prev => prev.filter((_, idx) => idx !== i)),
      className: "text-muted hover:text-fg disabled:opacity-40 cursor-pointer bg-transparent border-0"
    }, "\u2715")))), /*#__PURE__*/React.createElement("div", {
      className: "flex gap-2 items-center"
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      "data-testid": "understanding-add-condition",
      disabled: conditions.length >= MAX_CONDITIONS,
      onClick: () => setConditions(prev => [...prev, ""]),
      className: "text-xs text-muted hover:text-fg disabled:opacity-40 cursor-pointer bg-transparent border border-border rounded-sm px-2 py-0.5"
    }, "+ condition"), /*#__PURE__*/React.createElement("span", {
      className: "flex-1"
    }), /*#__PURE__*/React.createElement("button", {
      type: "button",
      "data-testid": "understanding-cancel-edit",
      onClick: () => {
        setEditingFor(null);
        props.onCancel?.();
      },
      className: "text-xs text-muted hover:text-fg cursor-pointer bg-transparent border border-border rounded-sm px-2 py-0.5"
    }, "Cancel"), /*#__PURE__*/React.createElement("button", {
      type: "button",
      "data-testid": "understanding-save",
      disabled: !valid,
      onClick: () => props.onSave?.({
        restated_intent: intent.trim(),
        success_conditions: conditions.map(c => c.trim())
      }),
      className: "text-xs font-medium text-white bg-accent rounded-sm px-2 py-0.5 disabled:opacity-40 cursor-pointer border-0"
    }, "Save & resume")), props.editError ? /*#__PURE__*/React.createElement("p", {
      "data-testid": "understanding-edit-error",
      role: "alert",
      className: "m-0 text-xs text-red-600 dark:text-red-400"
    }, props.editError) : null);
  }
  return /*#__PURE__*/React.createElement("aside", {
    "data-testid": "task-understanding-card",
    "data-source": understanding.source,
    "data-condition-count": understanding.success_conditions.length,
    role: "note",
    "aria-label": "Agent's understanding of your task",
    className: "rounded-md border border-border bg-muted/30 p-3 text-sm grid gap-1"
  }, /*#__PURE__*/React.createElement("p", {
    className: "m-0 font-medium"
  }, "Here's my understanding", /*#__PURE__*/React.createElement("span", {
    className: "ml-2 text-xs font-normal text-muted"
  }, SOURCE_LABEL[understanding.source] ?? understanding.source), props.editable ? /*#__PURE__*/React.createElement("button", {
    type: "button",
    "data-testid": "understanding-edit",
    onClick: startEdit,
    "aria-label": "Edit the agent's understanding",
    className: "ml-2 text-xs font-normal text-muted hover:text-fg cursor-pointer bg-transparent border border-border rounded-sm px-1.5 py-0"
  }, "Edit") : null), /*#__PURE__*/React.createElement("p", {
    className: "m-0 italic"
  }, understanding.restated_intent), /*#__PURE__*/React.createElement("ul", {
    className: "m-0 mt-1 list-none p-0 grid gap-0.5"
  }, understanding.success_conditions.map((condition, i) => /*#__PURE__*/React.createElement("li", {
    key: `cond-${i}`,
    "data-testid": `understanding-condition-${i}`,
    className: "flex gap-2 items-baseline text-xs"
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true"
  }, "\u2610"), /*#__PURE__*/React.createElement("span", null, condition)))));
}
Object.assign(__ds_scope, { TaskUnderstandingCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/TaskUnderstandingCard.tsx", error: String((e && e.message) || e) }); }

// components/chat/ThemeToggle.tsx
try { (() => {
/**
 * Theme toggle (S3.8.8, F9).
 *
 * Uses `next-themes` for theme management per Style Guide §2 prescription.
 * CSS variables in `app/globals.css` are flipped via `[data-theme="dark"]`.
 */

// B1: 'use client' required — useTheme hook from next-themes, onClick handler.
"use client";

function ThemeToggle() {
  const {
    resolvedTheme,
    setTheme
  } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  if (!mounted) {
    return /*#__PURE__*/React.createElement("button", {
      className: cn("bg-transparent text-fg border border-border", "rounded-sm px-2.5 py-1 cursor-pointer"),
      "aria-label": "Toggle theme"
    }, "\xA0");
  }
  const isDark = resolvedTheme === "dark";
  return /*#__PURE__*/React.createElement("button", {
    onClick: () => setTheme(isDark ? "light" : "dark"),
    "aria-label": `Switch to ${isDark ? "light" : "dark"} theme`,
    className: cn("bg-transparent text-fg border border-border", "rounded-sm px-2.5 py-1 cursor-pointer")
  }, isDark ? "Light" : "Dark");
}
Object.assign(__ds_scope, { ThemeToggle });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/ThemeToggle.tsx", error: String((e && e.message) || e) }); }

// components/chat/ThreadSidebar.tsx
try { (() => {
// Justification (B1, U2): thread rows attach onClick/onSelect handlers (event
// handlers are not serialisable from RSC -> client), so this stays a leaf
// "use client" boundary. The parent page (RSC) fetches the thread list through
// the ThreadStore port and passes it in; all time-bucketing is the pure
// `groupThreadsByTime` helper, so the component holds no domain logic (F-R1).
"use client";

/**
 * Thread sidebar (Phase 3 — chat history).
 *
 * Renders the caller's threads grouped Today / Yesterday / Previous 7 days /
 * Older (via `groupThreadsByTime`), each row showing its TITLE (not the raw
 * thread_id). Click resumes (onSelect); per-row rename (onRename) and delete
 * (onDelete) affordances call back to the parent hook, which owns the
 * BFF/runtime lifecycle.
 *
 * Deterministic hooks: data-testid="thread-sidebar", "thread-empty",
 * "thread-group-{label}", "thread-row-{id}", "thread-rename-{id}",
 * "thread-delete-{id}".
 */
function groupTestId(label) {
  return `thread-group-${label.toLowerCase().replace(/\s+/g, "-")}`;
}
function ThreadSidebar(props) {
  const groups = groupThreadsByTime(props.threads, props.now);
  return /*#__PURE__*/React.createElement("nav", {
    "data-testid": "thread-sidebar",
    "aria-label": "Chat history",
    className: "grid gap-3 p-3 border-r border-border-light bg-bg min-w-64"
  }, props.threads.length === 0 ? props.isFiltered ? /*#__PURE__*/React.createElement("p", {
    "data-testid": "thread-search-empty",
    className: "text-xs text-muted m-0"
  }, "No conversations match.") : /*#__PURE__*/React.createElement("p", {
    "data-testid": "thread-empty",
    className: "text-xs text-muted m-0"
  }, "No conversations yet.") : groups.map(group => /*#__PURE__*/React.createElement("div", {
    key: group.label,
    "data-testid": groupTestId(group.label)
  }, /*#__PURE__*/React.createElement("h3", {
    className: "text-xs uppercase tracking-wide text-muted m-0 mb-1"
  }, group.label), /*#__PURE__*/React.createElement("ul", {
    className: "grid gap-0.5 list-none p-0 m-0"
  }, group.threads.map(t => {
    const active = props.activeThreadId === t.thread_id;
    return /*#__PURE__*/React.createElement("li", {
      key: t.thread_id,
      className: "group flex items-center justify-between gap-1"
    }, /*#__PURE__*/React.createElement("a", {
      "data-testid": `thread-row-${t.thread_id}`,
      href: `/threads/${t.thread_id}`,
      "aria-current": active ? "page" : undefined,
      onClick: e => {
        if (props.onSelect) {
          e.preventDefault();
          props.onSelect(t.thread_id);
        }
      },
      className: cn("flex-1 block px-3 py-2 rounded-sm text-fg no-underline truncate text-sm", active ? "bg-accent-light" : "bg-transparent"),
      title: t.title
    }, t.title), props.onRename ? /*#__PURE__*/React.createElement("button", {
      type: "button",
      "data-testid": `thread-rename-${t.thread_id}`,
      "aria-label": `Rename: ${t.title}`,
      onClick: () => {
        const next = window.prompt("Rename conversation", t.title);
        if (next && next.trim()) {
          props.onRename?.(t.thread_id, next.trim());
        }
      },
      className: "text-muted hover:text-fg text-xs opacity-0 group-hover:opacity-100"
    }, "\u270E") : null, props.onDelete ? /*#__PURE__*/React.createElement("button", {
      type: "button",
      "data-testid": `thread-delete-${t.thread_id}`,
      "aria-label": `Delete: ${t.title}`,
      onClick: () => props.onDelete?.(t.thread_id),
      className: "text-muted hover:text-red-500 text-xs opacity-0 group-hover:opacity-100"
    }, "\u2715") : null);
  })))));
}
Object.assign(__ds_scope, { ThreadSidebar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/ThreadSidebar.tsx", error: String((e && e.message) || e) }); }

// components/chat/SidebarPanel.tsx
try { (() => {
/**
 * SidebarPanel — the left-rail CHROME wrapper (UI refresh Phase 1-4).
 *
 * Pure presentational leaf (F-R1): all state (collapsed / search / activeTab)
 * is owned by `useSidebarChrome` at the shell level and passed in as props;
 * thread DATA is owned by `useChatSidebars`. This component only lays out the
 * affordances — collapse toggle, tab bar, New chat, Search — above the existing
 * `ThreadSidebar` list, and forwards every interaction via callbacks.
 *
 * Collapse animates the panel's own WIDTH (w-64 ↔ w-12), not the parent grid
 * template (cross-browser-unreliable); the collapsible body is clipped and
 * aria-hidden when collapsed. The transition is disabled under
 * `prefers-reduced-motion` (design doc §5).
 *
 * No icon dependency — inline glyphs (☰ + 🔍) per the repo convention.
 */

"use client";

function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function SidebarPanel(props) {
  const isFiltered = props.searchQuery.trim().length > 0;
  return /*#__PURE__*/React.createElement("div", {
    "data-testid": "sidebar-panel",
    className: cn("h-full overflow-hidden border-r border-border-light bg-bg", "transition-[width] duration-200 ease-out motion-reduce:transition-none", props.collapsed ? "w-12" : "w-64")
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2 p-2"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    "data-testid": "sidebar-toggle",
    "aria-label": props.collapsed ? "Expand sidebar" : "Collapse sidebar",
    "aria-expanded": !props.collapsed,
    "aria-controls": "sidebar-body",
    onClick: props.onToggleCollapsed,
    className: "text-fg bg-transparent border-0 cursor-pointer text-lg leading-none px-1 hover:text-accent"
  }, "\u2630"), !props.collapsed ? /*#__PURE__*/React.createElement(__ds_scope.SidebarTabBar, {
    activeTab: props.activeTab,
    onSelect: props.onSelectTab
  }) : null), /*#__PURE__*/React.createElement("div", {
    id: "sidebar-body",
    "data-testid": "sidebar-body",
    "aria-hidden": props.collapsed,
    className: cn("grid gap-2 transition-opacity duration-150 ease-out motion-reduce:transition-none", props.collapsed ? "opacity-0 pointer-events-none" : "opacity-100")
  }, /*#__PURE__*/React.createElement("div", {
    className: "px-2"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    "data-testid": "new-thread",
    onClick: props.onNewChat,
    className: "w-full flex items-center gap-2 px-3 py-2 rounded-sm text-sm text-fg bg-surface border border-border cursor-pointer hover:border-accent"
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": true,
    className: "text-accent"
  }, "+"), "New chat")), /*#__PURE__*/React.createElement("div", {
    className: "px-2 grid gap-1"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    "data-testid": "sidebar-search-toggle",
    "aria-expanded": props.searchOpen,
    "aria-controls": "sidebar-search",
    onClick: props.onToggleSearch,
    className: "flex items-center gap-2 px-3 py-1.5 rounded-sm text-sm text-muted bg-transparent border-0 cursor-pointer hover:text-fg"
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": true
  }, "\uD83D\uDD0D"), "Search"), props.searchOpen ? /*#__PURE__*/React.createElement("input", {
    id: "sidebar-search",
    "data-testid": "sidebar-search-input",
    type: "text",
    "aria-label": "Search conversations",
    placeholder: "Search conversations\u2026",
    value: props.searchQuery,
    onChange: e => props.onSearchQueryChange(e.target.value),
    onKeyDown: e => {
      if (e.key === "Escape") props.onCloseSearch();
    },
    className: "w-full px-3 py-2 rounded-md text-sm text-fg bg-surface border border-border focus:outline-none focus:border-accent"
  }) : null), /*#__PURE__*/React.createElement(__ds_scope.ThreadSidebar, _extends({
    threads: props.threads,
    isFiltered: isFiltered
  }, props.activeThreadId ? {
    activeThreadId: props.activeThreadId
  } : {}, props.now !== undefined ? {
    now: props.now
  } : {}, props.onSelectThread ? {
    onSelect: props.onSelectThread
  } : {}, props.onRenameThread ? {
    onRename: props.onRenameThread
  } : {}, props.onDeleteThread ? {
    onDelete: props.onDeleteThread
  } : {}))));
}
Object.assign(__ds_scope, { SidebarPanel });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/SidebarPanel.tsx", error: String((e && e.message) || e) }); }

// components/generative/PyramidPanel.tsx
try { (() => {
/**
 * Pyramid panel (S3.8.4, F14, feature-flagged).
 *
 * Renders `StructuredReasoning` analysis_output as an interactive issue
 * tree. Hidden by default behind the `pyramid_panel` feature flag (the
 * caller checks `featureFlagProvider.isEnabled('pyramid_panel')` before
 * mounting this component, P5 sync read).
 */

function PyramidPanel(props) {
  return /*#__PURE__*/React.createElement("aside", {
    className: "border border-border rounded-md px-4 py-3 bg-bg",
    "aria-label": "Reasoning pyramid"
  }, /*#__PURE__*/React.createElement(PyramidTree, {
    node: props.root
  }));
}
function PyramidTree({
  node
}) {
  return /*#__PURE__*/React.createElement("details", {
    open: true
  }, /*#__PURE__*/React.createElement("summary", {
    className: "cursor-pointer font-semibold"
  }, node.title), node.summary ? /*#__PURE__*/React.createElement("p", {
    className: "text-muted my-1"
  }, node.summary) : null, node.children?.length ? /*#__PURE__*/React.createElement("ul", {
    className: "pl-4 m-0"
  }, node.children.map((c, i) => /*#__PURE__*/React.createElement("li", {
    key: i
  }, /*#__PURE__*/React.createElement(PyramidTree, {
    node: c
  })))) : null);
}
Object.assign(__ds_scope, { PyramidPanel });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/generative/PyramidPanel.tsx", error: String((e && e.message) || e) }); }

// components/generative/SandboxedCanvas.tsx
try { (() => {
/**
 * Generative-UI canvas (S3.8.3, F13).
 *
 * AUTO-REJECT guards encoded in the type:
 *   - sandbox is hard-coded to "allow-scripts" (FE-AP-4)
 *   - content arrives via `srcDoc`, NEVER `dangerouslySetInnerHTML`
 *     (FE-AP-12)
 *
 * `srcDoc` is a string the agent emits inside an `analysis_output`
 * `useComponent` slot; the iframe's `allow-scripts`-only sandbox prevents
 * the script from accessing the parent document, cookies, or storage.
 */

function SandboxedCanvas(props) {
  return /*#__PURE__*/React.createElement("iframe", {
    title: props.title,
    sandbox: "allow-scripts",
    srcDoc: props.srcDoc,
    className: "w-full border border-border rounded-md bg-bg",
    style: {
      height: `${props.height ?? 320}px`
    }
  });
}
Object.assign(__ds_scope, { SandboxedCanvas });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/generative/SandboxedCanvas.tsx", error: String((e && e.message) || e) }); }

// components/memory/MemoryPanel.tsx
try { (() => {
/**
 * Memory panel (Phase 3, F1) -- the user-visible, editable view of their own
 * long-term memory. The visible/editable panel is the 2026 trust norm
 * (research §4): the user can see what the agent remembers, add a fact, delete
 * one, and toggle memory off entirely.
 *
 * Per F-R1/F-R2/F-R8: typed props in, markup out. NO business logic, NO SDK
 * imports, wire types only. All lifecycle (fetching the list, POST/DELETE,
 * persisting the toggle) lives in the parent hook/adapter -- this component
 * only renders the passed state and calls the passed callbacks.
 *
 * Deterministic hooks: data-testid="memory-panel", "memory-empty",
 * "memory-group-{type}", "memory-item-{key}", "memory-delete-{key}",
 * "memory-add-input", "memory-add-type", "memory-add-submit",
 * "memory-enabled-toggle".
 */

const TYPE_ORDER = ["semantic", "episodic", "procedural"];
const TYPE_LABEL = {
  semantic: "Facts about you",
  episodic: "Past tasks",
  procedural: "Strategies that worked"
};
const MAX_CONTENT_LEN = 2000;
function groupByType(items) {
  const groups = {
    semantic: [],
    episodic: [],
    procedural: []
  };
  for (const item of items) {
    // Items with no/unknown type fall under "facts about you" (semantic) so
    // they are never silently hidden.
    const t = item.type === "episodic" || item.type === "procedural" ? item.type : "semantic";
    groups[t].push(item);
  }
  return groups;
}
function MemoryPanel(props) {
  const [draft, setDraft] = React.useState("");
  const [draftType, setDraftType] = React.useState("semantic");
  const groups = groupByType(props.items);
  const canAdd = draft.trim().length > 0 && draft.length <= MAX_CONTENT_LEN;
  const submit = () => {
    if (!canAdd || !props.onAdd) return;
    props.onAdd(draft.trim(), draftType);
    setDraft("");
  };
  return /*#__PURE__*/React.createElement("section", {
    "data-testid": "memory-panel",
    "aria-label": "Your memory",
    className: "grid gap-4 p-4 border-l border-border-light bg-bg min-w-72"
  }, /*#__PURE__*/React.createElement("header", {
    className: "flex items-center justify-between"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-fg text-sm font-semibold m-0"
  }, "What I remember"), /*#__PURE__*/React.createElement("label", {
    className: "flex items-center gap-2 text-xs text-muted"
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    "data-testid": "memory-enabled-toggle",
    checked: props.enabled,
    onChange: e => props.onToggleEnabled?.(e.target.checked)
  }), "Memory ", props.enabled ? "on" : "off")), props.items.length === 0 ? /*#__PURE__*/React.createElement("p", {
    "data-testid": "memory-empty",
    className: "text-xs text-muted m-0"
  }, "Nothing remembered yet.") : TYPE_ORDER.map(type => groups[type].length === 0 ? null : /*#__PURE__*/React.createElement("div", {
    key: type,
    "data-testid": `memory-group-${type}`
  }, /*#__PURE__*/React.createElement("h3", {
    className: "text-xs uppercase tracking-wide text-muted m-0 mb-1"
  }, TYPE_LABEL[type]), /*#__PURE__*/React.createElement("ul", {
    className: "grid gap-1 list-none p-0 m-0"
  }, groups[type].map(item => /*#__PURE__*/React.createElement("li", {
    key: item.key,
    "data-testid": `memory-item-${item.key}`,
    className: "flex items-start justify-between gap-2 text-sm text-fg"
  }, /*#__PURE__*/React.createElement("span", {
    className: "flex-1"
  }, item.content), /*#__PURE__*/React.createElement("button", {
    type: "button",
    "data-testid": `memory-delete-${item.key}`,
    "aria-label": `Forget: ${item.content}`,
    onClick: () => props.onDelete?.(item.key),
    className: "text-muted hover:text-red-500 text-xs"
  }, "\u2715")))))), /*#__PURE__*/React.createElement("form", {
    className: "grid gap-2",
    onSubmit: e => {
      e.preventDefault();
      submit();
    }
  }, /*#__PURE__*/React.createElement("input", {
    "data-testid": "memory-add-input",
    value: draft,
    maxLength: MAX_CONTENT_LEN,
    placeholder: "Add something to remember\u2026",
    onChange: e => setDraft(e.target.value),
    className: "px-2 py-1 rounded-sm border border-border-light bg-bg text-fg text-sm"
  }), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("select", {
    "data-testid": "memory-add-type",
    value: draftType,
    onChange: e => setDraftType(e.target.value),
    className: "px-2 py-1 rounded-sm border border-border-light bg-bg text-fg text-xs"
  }, TYPE_ORDER.map(t => /*#__PURE__*/React.createElement("option", {
    key: t,
    value: t
  }, TYPE_LABEL[t]))), /*#__PURE__*/React.createElement("button", {
    type: "submit",
    "data-testid": "memory-add-submit",
    disabled: !canAdd,
    className: cn("px-3 py-1 rounded-sm text-xs", canAdd ? "bg-accent text-white" : "bg-transparent text-muted cursor-not-allowed")
  }, "Remember"))));
}
Object.assign(__ds_scope, { MemoryPanel });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/memory/MemoryPanel.tsx", error: String((e && e.message) || e) }); }

// components/memory/RecallIndicator.tsx
try { (() => {
/**
 * Transparent-recall indicator (Phase 3, research §4) -- the Claude/ChatGPT
 * "searched past conversations" affordance. Shows, in the chat, how many
 * memories the agent recalled for the current turn.
 *
 * Sourced from the `MEMORY_RECALLED` governance carrier (count only -- NEVER
 * content; the privacy invariant holds end to end). This component is purely
 * presentational (F-R1): it takes the count as a typed prop. The parent wires
 * the count from the recall domain event / run view; this file invents no
 * transport and reads no state.
 *
 * Renders nothing when count is 0 (no recall happened) so it never adds noise
 * to a memory-off or no-hit run.
 *
 * Deterministic hook: data-testid="recall-indicator".
 */

function RecallIndicator(props) {
  if (!Number.isFinite(props.count) || props.count <= 0) return null;
  const label = props.count === 1 ? "Recalled 1 memory about you" : `Recalled ${props.count} memories about you`;
  return /*#__PURE__*/React.createElement("div", {
    "data-testid": "recall-indicator",
    className: "flex items-center gap-1 text-xs text-muted"
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": true
  }, "\uD83E\uDDE0"), /*#__PURE__*/React.createElement("span", null, label));
}
Object.assign(__ds_scope, { RecallIndicator });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/memory/RecallIndicator.tsx", error: String((e && e.message) || e) }); }

// components/memory/RecalledMemories.tsx
try { (() => {
/**
 * Recalled-memories eval disclosure (chat-persistence Phase B, B2). Under an
 * assistant turn, a collapsible "memories recalled here" list of the items the
 * agent recalled for THIS turn (key + type + content), each with a Reject
 * button that soft-suppresses the memory globally (D5).
 *
 * Gated to a dev/eval surface by the parent (`evalMode`) so production chat
 * stays clean — this component itself is purely presentational (F-R1): it
 * takes the resolved items + an `onReject` callback as typed props, invents no
 * transport, and reads no state. The parent JOINS the run view's recalled KEYS
 * against the owner's loaded memory panel to produce `items` (content never
 * rides the recall wire event — the privacy invariant holds; the owner already
 * has their own content in the panel).
 *
 * Renders nothing when there are no recalled items (no recall / flag off) so it
 * never adds noise.
 *
 * Deterministic hooks (design §6 testid contract):
 *   data-testid="recalled-memories"        the disclosure
 *   data-testid="recalled-memory-{key}"    one recalled item row
 *   data-testid="reject-memory-{key}"      the Reject (soft-suppress) button
 */

function RecalledMemories(props) {
  if (props.items.length === 0) return null;
  const n = props.items.length;
  return /*#__PURE__*/React.createElement("details", {
    "data-testid": "recalled-memories",
    className: "text-xs text-muted",
    open: props.defaultOpen ?? false
  }, /*#__PURE__*/React.createElement("summary", {
    className: "cursor-pointer select-none"
  }, n === 1 ? "1 memory recalled here" : `${n} memories recalled here`), /*#__PURE__*/React.createElement("ul", {
    className: "m-0 mt-1 list-none p-0 grid gap-1"
  }, props.items.map(item => /*#__PURE__*/React.createElement("li", {
    key: item.key,
    "data-testid": `recalled-memory-${item.key}`,
    className: "flex items-start justify-between gap-2"
  }, /*#__PURE__*/React.createElement("span", {
    className: "min-w-0"
  }, item.type ? /*#__PURE__*/React.createElement("span", {
    className: "uppercase tracking-wide opacity-70 mr-1"
  }, item.type) : null, /*#__PURE__*/React.createElement("span", {
    className: "break-words"
  }, item.content)), /*#__PURE__*/React.createElement("button", {
    type: "button",
    "data-testid": `reject-memory-${item.key}`,
    onClick: () => props.onReject(item.key),
    className: "shrink-0 underline hover:no-underline text-red-600 dark:text-red-400",
    "aria-label": `Reject this memory`
  }, "Reject")))));
}
Object.assign(__ds_scope, { RecalledMemories });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/memory/RecalledMemories.tsx", error: String((e && e.message) || e) }); }

// components/tools/ToolCard.tsx
try { (() => {
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

const STATUS_LABEL = {
  running: "running",
  completed: "completed",
  errored: "errored"
};
function ToolCard(props) {
  const {
    request
  } = props;
  const isString = typeof request.output === "string";
  return /*#__PURE__*/React.createElement("details", {
    open: props.defaultOpen ?? request.status === "running",
    "data-testid": "tool-card",
    "data-status": request.status,
    "data-tool-call-id": request.tool_call_id,
    className: "border border-border rounded-md px-3 py-2 my-1 bg-surface"
  }, /*#__PURE__*/React.createElement("summary", {
    className: "cursor-pointer flex gap-2 items-center font-mono text-sm"
  }, /*#__PURE__*/React.createElement("span", {
    className: "font-bold"
  }, request.tool_name), /*#__PURE__*/React.createElement("span", {
    className: "text-muted"
  }, STATUS_LABEL[request.status])), /*#__PURE__*/React.createElement("section", {
    className: "mt-2 grid gap-2"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", {
    className: "text-xs text-muted"
  }, "input"), /*#__PURE__*/React.createElement("pre", {
    className: "overflow-auto my-1"
  }, JSON.stringify(request.input, null, 2))), request.output != null ? /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", {
    className: "text-xs text-muted"
  }, "output"), /*#__PURE__*/React.createElement("pre", {
    className: "overflow-auto my-1"
  }, isString ? request.output : JSON.stringify(request.output, null, 2))) : null));
}
Object.assign(__ds_scope, { ToolCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/tools/ToolCard.tsx", error: String((e && e.message) || e) }); }

// components/ui/button.tsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function buttonClasses(variant = "default", size = "md", className) {
  return cn("inline-flex items-center justify-center font-semibold transition-opacity", "rounded-md disabled:cursor-not-allowed disabled:opacity-60 no-underline", variant === "default" && "bg-accent text-white border-0", variant === "outline" && "bg-transparent text-fg border border-border", variant === "ghost" && "bg-transparent text-fg border-0", size === "sm" && "px-2.5 py-1 text-sm rounded-sm", size === "md" && "px-4 py-2 text-base", className);
}
const Button = React.forwardRef(({
  className,
  variant = "default",
  size = "md",
  asChild,
  ...props
}, ref) => {
  if (asChild && React.isValidElement(props.children)) {
    return React.cloneElement(props.children, {
      className: buttonClasses(variant, size, className),
      ref
    });
  }
  return /*#__PURE__*/React.createElement("button", _extends({
    ref: ref,
    className: buttonClasses(variant, size, className)
  }, props));
});
Button.displayName = "Button";
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/ui/button.tsx", error: String((e && e.message) || e) }); }

// lib/composition_react.tsx
try { (() => {
/**
 * React-side of the composition root: AdapterProvider context + useAdapters hook.
 *
 * Lives next to `composition.ts` because it depends on the same concrete
 * adapter classes through the `PortBag` shape. Components consume the
 * context exclusively (no direct adapter imports anywhere else, statically
 * enforced by `tests/architecture/test_frontend_layering.test.ts`).
 */

"use client";

const AdapterContext = React.createContext(null);
function AdapterProvider(props) {
  return /*#__PURE__*/React.createElement(AdapterContext.Provider, {
    value: props.bag
  }, props.children);
}
function useAdapters() {
  const ctx = React.useContext(AdapterContext);
  if (!ctx) {
    throw new Error("useAdapters() must be called inside <AdapterProvider> -- ensure the " + "root layout wraps the app with the composed PortBag.");
  }
  return ctx;
}
Object.assign(__ds_scope, { AdapterProvider, useAdapters });
})(); } catch (e) { __ds_ns.__errors.push({ path: "lib/composition_react.tsx", error: String((e && e.message) || e) }); }

__ds_ns.ChatShell = __ds_scope.ChatShell;

__ds_ns.RootLayout = __ds_scope.RootLayout;

__ds_ns.HomePage = __ds_scope.HomePage;

__ds_ns.ThemeProvider = __ds_scope.ThemeProvider;

__ds_ns.CodeBlock = __ds_scope.CodeBlock;

__ds_ns.Composer = __ds_scope.Composer;

__ds_ns.RunControls = __ds_scope.RunControls;

__ds_ns.SidebarPanel = __ds_scope.SidebarPanel;

__ds_ns.SidebarTabBar = __ds_scope.SidebarTabBar;

__ds_ns.StreamingMarkdown = __ds_scope.StreamingMarkdown;

__ds_ns.TaskList = __ds_scope.TaskList;

__ds_ns.TaskUnderstandingCard = __ds_scope.TaskUnderstandingCard;

__ds_ns.ThemeToggle = __ds_scope.ThemeToggle;

__ds_ns.ThreadSidebar = __ds_scope.ThreadSidebar;

__ds_ns.PyramidPanel = __ds_scope.PyramidPanel;

__ds_ns.SandboxedCanvas = __ds_scope.SandboxedCanvas;

__ds_ns.MemoryPanel = __ds_scope.MemoryPanel;

__ds_ns.RecallIndicator = __ds_scope.RecallIndicator;

__ds_ns.RecalledMemories = __ds_scope.RecalledMemories;

__ds_ns.ToolCard = __ds_scope.ToolCard;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.AdapterProvider = __ds_scope.AdapterProvider;

})();
