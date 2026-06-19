/**
 * use_chat_sidebars — pure fetch-function tests (node, no React).
 *
 * The hook itself is a thin React wrapper; the load/mutate logic lives in
 * exported pure async functions driven by an injected `fetch`, so they can be
 * tested without a DOM (mirrors `consumeRunStream` in use_agent_run).
 *
 * Failure paths first (FD6): non-OK status and malformed payloads must surface
 * as a typed error, never silent corruption. The browser→BFF leg is
 * same-origin cookie auth, so these functions send NO bearer token.
 */

import { describe, expect, it, vi } from "vitest";
import {
  fetchThreadList,
  fetchThread,
  createThreadRequest,
  appendTurnRequest,
  threadMessagesToTurns,
  fetchMemoryList,
  renameThreadRequest,
  archiveThreadRequest,
  addMemoryRequest,
  deleteMemoryRequest,
  suppressMemoryRequest,
  ChatSidebarsError,
} from "./use_chat_sidebars";
import type { MemoryItem, ThreadState } from "@/lib/wire/agent_protocol";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function thread(id: string, title: string): ThreadState {
  return {
    thread_id: id,
    user_id: "u",
    title,
    messages: [],
    created_at: "2026-06-17T00:00:00Z",
    updated_at: "2026-06-17T00:00:00Z",
    archived_at: null,
  };
}

function memory(key: string, content: string): MemoryItem {
  return { key, type: "semantic", content, salience: 0.5 };
}

// ── fetchThreadList ────────────────────────────────────────────────────

describe("fetchThreadList — failure paths first", () => {
  it("throws ChatSidebarsError on a non-OK status", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 500))) as typeof fetch;
    await expect(fetchThreadList(f)).rejects.toBeInstanceOf(ChatSidebarsError);
  });

  it("throws on a malformed payload (missing threads)", async () => {
    const f = (() =>
      Promise.resolve(jsonResponse({ wat: 1 }))) as typeof fetch;
    await expect(fetchThreadList(f)).rejects.toBeInstanceOf(ChatSidebarsError);
  });

  it("returns the parsed thread list on the happy path", async () => {
    const f = (() =>
      Promise.resolve(
        jsonResponse({ threads: [thread("t1", "Trip")], next_cursor: null }),
      )) as typeof fetch;
    const out = await fetchThreadList(f);
    expect(out.map((t) => t.title)).toEqual(["Trip"]);
  });

  it("requests the threads route without a bearer header (same-origin cookie auth)", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(jsonResponse({ threads: [], next_cursor: null })),
    );
    await fetchThreadList(spy as unknown as typeof fetch);
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit | undefined];
    expect(url).toContain("/api/threads");
    expect(
      JSON.stringify(init?.headers ?? {}).toLowerCase(),
    ).not.toContain("authorization");
  });
});

// ── fetchThread (click-to-resume) ──────────────────────────────────────

describe("fetchThread — failure paths first", () => {
  it("throws ChatSidebarsError on a non-OK status (404 not-owned / not-found)", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 404))) as typeof fetch;
    await expect(fetchThread(f, "t1")).rejects.toBeInstanceOf(ChatSidebarsError);
  });

  it("throws on a malformed payload (missing thread fields)", async () => {
    const f = (() =>
      Promise.resolve(jsonResponse({ wat: 1 }))) as typeof fetch;
    await expect(fetchThread(f, "t1")).rejects.toBeInstanceOf(ChatSidebarsError);
  });

  it("GETs the single-thread route by encoded id (no bearer header)", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(jsonResponse(thread("a/b", "Trip"))),
    );
    const out = await fetchThread(spy as unknown as typeof fetch, "a/b");
    expect(out.title).toBe("Trip");
    const [url, init] = spy.mock.calls[0] as unknown as [
      string,
      RequestInit | undefined,
    ];
    expect(url).toContain("/api/threads/a%2Fb");
    expect(init?.method).toBe("GET");
    expect(
      JSON.stringify(init?.headers ?? {}).toLowerCase(),
    ).not.toContain("authorization");
  });
});

// ── createThreadRequest (auto-create on first send) ────────────────────

describe("createThreadRequest — failure paths first", () => {
  it("throws ChatSidebarsError on a non-OK status", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 500))) as typeof fetch;
    await expect(
      createThreadRequest(f, "tid-1", "u1", "hello there"),
    ).rejects.toBeInstanceOf(ChatSidebarsError);
  });

  it("throws on a malformed payload (missing thread fields)", async () => {
    const f = (() => Promise.resolve(jsonResponse({ wat: 1 }))) as typeof fetch;
    await expect(
      createThreadRequest(f, "tid-1", "u1", "hello"),
    ).rejects.toBeInstanceOf(ChatSidebarsError);
  });

  it("POSTs the minted thread_id + first_message metadata, no bearer", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(jsonResponse(thread("tid-1", "hello there"))),
    );
    const out = await createThreadRequest(
      spy as unknown as typeof fetch,
      "tid-1",
      "u1",
      "hello there",
    );
    expect(out.thread_id).toBe("tid-1");
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/threads");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as {
      thread_id: string;
      user_id: string;
      metadata: { first_message: string };
    };
    expect(body.thread_id).toBe("tid-1");
    expect(body.user_id).toBe("u1");
    expect(body.metadata.first_message).toBe("hello there");
    expect(
      JSON.stringify(init.headers ?? {}).toLowerCase(),
    ).not.toContain("authorization");
  });
});

// ── appendTurnRequest (per-turn persist) ───────────────────────────────

describe("appendTurnRequest — failure paths first", () => {
  const TURN = { user: "q", assistant: "a", turnId: "tn-1" };

  it("throws ChatSidebarsError on a non-OK, non-404 status", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 500))) as typeof fetch;
    await expect(appendTurnRequest(f, "tid-1", TURN)).rejects.toBeInstanceOf(
      ChatSidebarsError,
    );
  });

  it("resolves silently on 404 (idempotent / pruned-or-not-owned)", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 404))) as typeof fetch;
    await expect(appendTurnRequest(f, "tid-1", TURN)).resolves.toBeUndefined();
  });

  it("POSTs the turn (snake_case turn_id) to the messages route, no bearer", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(new Response(null, { status: 204 })),
    );
    await appendTurnRequest(spy as unknown as typeof fetch, "a/b", TURN);
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/threads/a%2Fb/messages");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body).toEqual({ user: "q", assistant: "a", turn_id: "tn-1" });
    expect(
      JSON.stringify(init.headers ?? {}).toLowerCase(),
    ).not.toContain("authorization");
  });
});

// ── suppressMemoryRequest (Phase B reject = soft-suppress) ─────────────

describe("suppressMemoryRequest — failure paths first", () => {
  it("throws ChatSidebarsError on a non-OK, non-404 status", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 500))) as typeof fetch;
    await expect(suppressMemoryRequest(f, "k1", true)).rejects.toBeInstanceOf(
      ChatSidebarsError,
    );
  });

  it("resolves silently on 404 (idempotent — nothing to suppress)", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 404))) as typeof fetch;
    await expect(
      suppressMemoryRequest(f, "k1", true),
    ).resolves.toBeUndefined();
  });

  it("PATCHes the keyed memory route with the flag", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(new Response(null, { status: 204 })),
    );
    await suppressMemoryRequest(spy as unknown as typeof fetch, "k 1", true);
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/memory/k%201");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ suppressed: true });
  });

  it("forwards suppressed=false (un-suppress / reversible)", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(new Response(null, { status: 204 })),
    );
    await suppressMemoryRequest(spy as unknown as typeof fetch, "k1", false);
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ suppressed: false });
  });
});

// ── threadMessagesToTurns (pure replay translator) ─────────────────────

describe("threadMessagesToTurns", () => {
  it("returns no turns for an empty history", () => {
    expect(threadMessagesToTurns([])).toEqual([]);
  });

  it("pairs a user message with the following assistant message into one turn", () => {
    const turns = threadMessagesToTurns([
      { role: "user", content: "what units do I prefer?" },
      { role: "assistant", content: "You prefer metric units." },
    ]);
    expect(turns).toHaveLength(1);
    expect(turns[0]?.user).toBe("what units do I prefer?");
    expect(turns[0]?.assistant.status).toBe("complete");
    const seg = turns[0]?.assistant.segments[0];
    expect(seg?.kind).toBe("text");
    expect(seg && seg.kind === "text" ? seg.text : "").toContain("metric");
  });

  it("gives each replayed turn a stable, unique React key", () => {
    const turns = threadMessagesToTurns([
      { role: "user", content: "a" },
      { role: "assistant", content: "A" },
      { role: "user", content: "b" },
      { role: "assistant", content: "B" },
    ]);
    expect(turns).toHaveLength(2);
    expect(turns[0]?.id).not.toBe(turns[1]?.id);
  });

  it("tolerates a trailing user message with no assistant reply yet", () => {
    const turns = threadMessagesToTurns([
      { role: "user", content: "hello" },
    ]);
    expect(turns).toHaveLength(1);
    expect(turns[0]?.user).toBe("hello");
    // No assistant content yet → empty segments, but still a complete (frozen)
    // view so it never animates a phantom run.
    expect(turns[0]?.assistant.status).toBe("complete");
    expect(turns[0]?.assistant.segments).toEqual([]);
  });

  it("ignores non-user/assistant roles (system, tool) in the replay", () => {
    const turns = threadMessagesToTurns([
      { role: "system", content: "you are helpful" },
      { role: "user", content: "hi" },
      { role: "tool", content: "{...}" },
      { role: "assistant", content: "hello!" },
    ]);
    expect(turns).toHaveLength(1);
    expect(turns[0]?.user).toBe("hi");
    expect(
      turns[0]?.assistant.segments[0] &&
        turns[0].assistant.segments[0].kind === "text"
        ? turns[0].assistant.segments[0].text
        : "",
    ).toBe("hello!");
  });

  it("tolerates non-string / missing content without throwing", () => {
    const turns = threadMessagesToTurns([
      { role: "user", content: 42 },
      { role: "assistant" },
    ]);
    expect(turns).toHaveLength(1);
    expect(turns[0]?.user).toBe("");
  });
});

// ── fetchMemoryList ────────────────────────────────────────────────────

describe("fetchMemoryList", () => {
  it("throws on a non-OK status", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 503))) as typeof fetch;
    await expect(fetchMemoryList(f)).rejects.toBeInstanceOf(ChatSidebarsError);
  });

  it("returns the parsed items on the happy path", async () => {
    const f = (() =>
      Promise.resolve(
        jsonResponse({ items: [memory("k1", "likes metric units")] }),
      )) as typeof fetch;
    const out = await fetchMemoryList(f);
    expect(out.map((m) => m.content)).toEqual(["likes metric units"]);
  });
});

// ── mutations ──────────────────────────────────────────────────────────

describe("renameThreadRequest", () => {
  it("PATCHes the thread and returns the updated state", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(jsonResponse(thread("t1", "Renamed"))),
    );
    const out = await renameThreadRequest(
      spy as unknown as typeof fetch,
      "t1",
      "Renamed",
    );
    expect(out.title).toBe("Renamed");
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/threads/t1");
    expect(init.method).toBe("PATCH");
  });

  it("throws on a non-OK status (404 not-owned / not-found)", async () => {
    const f = (() => Promise.resolve(jsonResponse({}, 404))) as typeof fetch;
    await expect(
      renameThreadRequest(f, "t1", "x"),
    ).rejects.toBeInstanceOf(ChatSidebarsError);
  });
});

describe("archiveThreadRequest", () => {
  it("DELETEs the thread and resolves on 204", async () => {
    const spy = vi.fn(() => Promise.resolve(new Response(null, { status: 204 })));
    await expect(
      archiveThreadRequest(spy as unknown as typeof fetch, "t1"),
    ).resolves.toBeUndefined();
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/threads/t1");
    expect(init.method).toBe("DELETE");
  });

  it("treats 404 as idempotent-OK", async () => {
    const f = (() =>
      Promise.resolve(new Response(null, { status: 404 }))) as typeof fetch;
    await expect(archiveThreadRequest(f, "gone")).resolves.toBeUndefined();
  });
});

describe("addMemoryRequest", () => {
  it("POSTs content+type and returns the created item", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(jsonResponse(memory("k9", "remembers X"))),
    );
    const out = await addMemoryRequest(
      spy as unknown as typeof fetch,
      "remembers X",
      "semantic",
    );
    expect(out.key).toBe("k9");
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/memory");
    expect(init.method).toBe("POST");
  });

  it("throws on a malformed response", async () => {
    const f = (() => Promise.resolve(jsonResponse({ nope: 1 }))) as typeof fetch;
    await expect(
      addMemoryRequest(f, "x", "semantic"),
    ).rejects.toBeInstanceOf(ChatSidebarsError);
  });
});

describe("deleteMemoryRequest", () => {
  it("DELETEs by encoded key and resolves on 204", async () => {
    const spy = vi.fn(() => Promise.resolve(new Response(null, { status: 204 })));
    await expect(
      deleteMemoryRequest(spy as unknown as typeof fetch, "a/b"),
    ).resolves.toBeUndefined();
    const [url] = spy.mock.calls[0] as unknown as [string];
    expect(url).toContain("/api/memory/a%2Fb");
  });

  it("treats 404 as idempotent-OK", async () => {
    const f = (() =>
      Promise.resolve(new Response(null, { status: 404 }))) as typeof fetch;
    await expect(deleteMemoryRequest(f, "gone")).resolves.toBeUndefined();
  });
});
