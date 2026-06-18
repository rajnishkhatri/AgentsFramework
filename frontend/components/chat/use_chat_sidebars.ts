/**
 * useChatSidebars — the chat shell's seam onto the thread-history and memory
 * BFF routes (Phase 3 mount).
 *
 * The browser→BFF leg is same-origin and cookie-authed by the WorkOS session,
 * so these calls send NO bearer token (the bearer/credential hop is BFF→
 * middleware, owned server-side — F-R9). This mirrors `composition_browser`'s
 * runtime client, which likewise fetches `/api/...` directly from the browser.
 *
 * Per F-R1 the panels (ThreadSidebar, MemoryPanel) hold no lifecycle: this
 * hook owns list state + the load/mutate calls and hands the panels typed
 * props + callbacks. The load/mutate logic is exported as pure async functions
 * driven by an injected `fetch` so they are node-testable without a DOM
 * (mirrors `consumeRunStream`).
 *
 * Responses are Zod-validated with the wire schemas: a malformed upstream
 * payload is a typed `ChatSidebarsError`, never silent corruption.
 */

"use client";

import * as React from "react";
import {
  MemoryItemSchema,
  MemoryListResponseSchema,
  ThreadListResponseSchema,
  ThreadStateSchema,
  type MemoryItem,
  type MemoryType,
  type ThreadState,
} from "@/lib/wire/agent_protocol";
import { emptyRunView } from "@/lib/translators/run_view_reducer";
import type { ChatTurn } from "./use_agent_run";

export class ChatSidebarsError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "ChatSidebarsError";
  }
}

const JSON_HEADERS = { "content-type": "application/json" } as const;

function wrap(e: unknown): ChatSidebarsError {
  return e instanceof ChatSidebarsError
    ? e
    : new ChatSidebarsError(e instanceof Error ? e.message : String(e), {
        cause: e,
      });
}

// ── pure fetch functions (node-testable) ───────────────────────────────

export async function fetchThreadList(
  fetchImpl: typeof fetch,
): Promise<ReadonlyArray<ThreadState>> {
  try {
    const res = await fetchImpl("/api/threads", { method: "GET" });
    if (!res.ok) throw new ChatSidebarsError(`thread list failed (${res.status})`);
    const parsed = ThreadListResponseSchema.safeParse(await res.json());
    if (!parsed.success) {
      throw new ChatSidebarsError("malformed thread list response");
    }
    return parsed.data.threads;
  } catch (e) {
    throw wrap(e);
  }
}

/**
 * Fetch one thread (its persisted message history) for click-to-resume.
 * Same-origin cookie auth, no bearer (the credential hop is BFF→middleware).
 * The BFF GET handler collapses missing/not-owned to 404 (no existence
 * oracle), which surfaces here as a `ChatSidebarsError`.
 */
export async function fetchThread(
  fetchImpl: typeof fetch,
  threadId: string,
): Promise<ThreadState> {
  try {
    const res = await fetchImpl(
      `/api/threads/${encodeURIComponent(threadId)}`,
      { method: "GET" },
    );
    if (!res.ok) throw new ChatSidebarsError(`thread fetch failed (${res.status})`);
    const parsed = ThreadStateSchema.safeParse(await res.json());
    if (!parsed.success) {
      throw new ChatSidebarsError("malformed thread response");
    }
    return parsed.data;
  } catch (e) {
    throw wrap(e);
  }
}

/**
 * Replay a thread's persisted history into the chat view's turn list.
 *
 * The backend persists LangGraph messages as `{role, content}` dicts
 * (langgraph_runtime.get_state); we pair each `user` line with the next
 * `assistant` line into one `ChatTurn`. Non user/assistant roles (system,
 * tool) are dropped — they are not part of the human-readable transcript.
 *
 * Each replayed assistant view is `complete` (frozen): a resumed turn is
 * history, never a live run, so it must not animate a phantom phase. Content
 * is coerced defensively (a non-string content collapses to "") so a quirky
 * stored message can never crash the resume. Keys are positional + content-
 * derived, stable across re-renders and unique per turn.
 */
export function threadMessagesToTurns(
  messages: ReadonlyArray<Record<string, unknown>>,
): ReadonlyArray<ChatTurn> {
  const text = (m: Record<string, unknown>): string =>
    typeof m.content === "string" ? m.content : "";
  const turns: ChatTurn[] = [];
  let pending: { id: string; user: string } | null = null;
  let i = 0;
  for (const m of messages) {
    const role = m.role;
    if (role === "user") {
      if (pending) {
        // Two users in a row (no assistant reply): flush the first as a
        // bare turn so nothing is lost.
        turns.push({ ...pending, assistant: completeView("") });
      }
      pending = { id: `replay-${i}`, user: text(m) };
    } else if (role === "assistant" && pending) {
      turns.push({ ...pending, assistant: completeView(text(m)) });
      pending = null;
    }
    i += 1;
  }
  if (pending) turns.push({ ...pending, assistant: completeView("") });
  return turns;
}

/** A frozen, complete assistant view holding one text segment (or none). */
function completeView(content: string): ChatTurn["assistant"] {
  const base = emptyRunView();
  return {
    ...base,
    status: "complete",
    segments: content ? [{ kind: "text", text: content }] : [],
  };
}

export async function fetchMemoryList(
  fetchImpl: typeof fetch,
): Promise<ReadonlyArray<MemoryItem>> {
  try {
    const res = await fetchImpl("/api/memory", { method: "GET" });
    if (!res.ok) throw new ChatSidebarsError(`memory list failed (${res.status})`);
    const parsed = MemoryListResponseSchema.safeParse(await res.json());
    if (!parsed.success) {
      throw new ChatSidebarsError("malformed memory list response");
    }
    return parsed.data.items;
  } catch (e) {
    throw wrap(e);
  }
}

export async function renameThreadRequest(
  fetchImpl: typeof fetch,
  threadId: string,
  title: string,
): Promise<ThreadState> {
  try {
    const res = await fetchImpl(
      `/api/threads/${encodeURIComponent(threadId)}`,
      { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify({ title }) },
    );
    if (!res.ok) throw new ChatSidebarsError(`rename failed (${res.status})`);
    const parsed = ThreadStateSchema.safeParse(await res.json());
    if (!parsed.success) {
      throw new ChatSidebarsError("malformed rename response");
    }
    return parsed.data;
  } catch (e) {
    throw wrap(e);
  }
}

export async function archiveThreadRequest(
  fetchImpl: typeof fetch,
  threadId: string,
): Promise<void> {
  try {
    const res = await fetchImpl(
      `/api/threads/${encodeURIComponent(threadId)}`,
      { method: "DELETE" },
    );
    // 404 is idempotent-OK from the caller's view (already archived).
    if (res.ok || res.status === 404) return;
    throw new ChatSidebarsError(`archive failed (${res.status})`);
  } catch (e) {
    throw wrap(e);
  }
}

export async function addMemoryRequest(
  fetchImpl: typeof fetch,
  content: string,
  type: MemoryType,
): Promise<MemoryItem> {
  try {
    const res = await fetchImpl("/api/memory", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ content, type, key: null }),
    });
    if (!res.ok) throw new ChatSidebarsError(`memory add failed (${res.status})`);
    const parsed = MemoryItemSchema.safeParse(await res.json());
    if (!parsed.success) {
      throw new ChatSidebarsError("malformed memory add response");
    }
    return parsed.data;
  } catch (e) {
    throw wrap(e);
  }
}

export async function deleteMemoryRequest(
  fetchImpl: typeof fetch,
  key: string,
): Promise<void> {
  try {
    const res = await fetchImpl(`/api/memory/${encodeURIComponent(key)}`, {
      method: "DELETE",
    });
    if (res.ok || res.status === 404) return;
    throw new ChatSidebarsError(`memory remove failed (${res.status})`);
  } catch (e) {
    throw wrap(e);
  }
}

// ── React hook ─────────────────────────────────────────────────────────

export interface ChatSidebarsState {
  readonly threads: ReadonlyArray<ThreadState>;
  readonly memories: ReadonlyArray<MemoryItem>;
  readonly memoryEnabled: boolean;
  readonly error: string | null;
  reloadThreads(): Promise<void>;
  reloadMemories(): Promise<void>;
  renameThread(threadId: string, title: string): Promise<void>;
  deleteThread(threadId: string): Promise<void>;
  addMemory(content: string, type: MemoryType): Promise<void>;
  deleteMemory(key: string): Promise<void>;
  setMemoryEnabled(enabled: boolean): void;
  /**
   * Click-to-resume: fetch a thread's persisted history and translate it into
   * replayable chat turns. The shell hands these to `useAgentRun.resumeThread`.
   * Returns an empty array (never throws) if the fetch fails — the error is
   * surfaced via `error` so a broken resume degrades to "nothing happened".
   */
  loadThreadTurns(threadId: string): Promise<ReadonlyArray<ChatTurn>>;
}

/**
 * Drives the thread + memory side panels. `fetchImpl` is injectable for tests
 * (defaults to the global `fetch`); the panels never see it.
 *
 * The memory on/off toggle is local UI state for now — it gates whether the
 * panel surfaces management affordances, NOT a server flag flip (the
 * MEMORY_ENABLED runtime flag is a deploy-time concern, default OFF).
 */
export function useChatSidebars(
  fetchImpl: typeof fetch = globalThis.fetch,
): ChatSidebarsState {
  const [threads, setThreads] = React.useState<ReadonlyArray<ThreadState>>([]);
  const [memories, setMemories] = React.useState<ReadonlyArray<MemoryItem>>([]);
  const [memoryEnabled, setMemoryEnabled] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const f = React.useRef(fetchImpl);
  f.current = fetchImpl;

  const guard = React.useCallback(async (op: () => Promise<void>): Promise<void> => {
    try {
      await op();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const reloadThreads = React.useCallback(
    (): Promise<void> =>
      guard(async () => {
        setThreads(await fetchThreadList(f.current));
      }),
    [guard],
  );

  const reloadMemories = React.useCallback(
    (): Promise<void> =>
      guard(async () => {
        setMemories(await fetchMemoryList(f.current));
      }),
    [guard],
  );

  const renameThread = React.useCallback(
    (threadId: string, title: string): Promise<void> =>
      guard(async () => {
        const updated = await renameThreadRequest(f.current, threadId, title);
        setThreads((prev) =>
          prev.map((t) => (t.thread_id === threadId ? updated : t)),
        );
      }),
    [guard],
  );

  const deleteThread = React.useCallback(
    (threadId: string): Promise<void> =>
      guard(async () => {
        await archiveThreadRequest(f.current, threadId);
        setThreads((prev) => prev.filter((t) => t.thread_id !== threadId));
      }),
    [guard],
  );

  const addMemory = React.useCallback(
    (content: string, type: MemoryType): Promise<void> =>
      guard(async () => {
        const created = await addMemoryRequest(f.current, content, type);
        setMemories((prev) => [created, ...prev]);
      }),
    [guard],
  );

  const deleteMemory = React.useCallback(
    (key: string): Promise<void> =>
      guard(async () => {
        await deleteMemoryRequest(f.current, key);
        setMemories((prev) => prev.filter((m) => m.key !== key));
      }),
    [guard],
  );

  const loadThreadTurns = React.useCallback(
    async (threadId: string): Promise<ReadonlyArray<ChatTurn>> => {
      try {
        const t = await fetchThread(f.current, threadId);
        return threadMessagesToTurns(t.messages);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return [];
      }
    },
    [],
  );

  // Initial load. The empty deps array intentionally loads once on mount; the
  // callbacks read the live fetch impl through the ref, so they stay stable.
  React.useEffect(() => {
    void reloadThreads();
    void reloadMemories();
  }, [reloadThreads, reloadMemories]);

  return {
    threads,
    memories,
    memoryEnabled,
    error,
    reloadThreads,
    reloadMemories,
    renameThread,
    deleteThread,
    addMemory,
    deleteMemory,
    setMemoryEnabled,
    loadThreadTurns,
  };
}
