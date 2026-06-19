/**
 * HttpMemoryStore tests. Failure paths first (FD6).
 *
 * The adapter forwards to the middleware over HTTP with the caller's bearer
 * token (F-R9). It validates every upstream payload with the wire schema, so
 * a malformed response is a typed MemoryStoreError, not silent corruption.
 */

import { describe, expect, it, vi } from "vitest";
import { HttpMemoryStore } from "./http_memory_store";
import { MemoryStoreError } from "../../ports/memory_store";

function store(fetchImpl: typeof fetch) {
  return new HttpMemoryStore({
    baseUrl: "http://mw",
    fetchImpl,
    getToken: async () => "tok-123",
  });
}

function jsonRes(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("HttpMemoryStore — failure paths first", () => {
  it("list throws MemoryStoreError on a non-ok status", async () => {
    const s = store(() => Promise.resolve(jsonRes(503, { detail: "down" })));
    await expect(s.list()).rejects.toBeInstanceOf(MemoryStoreError);
  });

  it("list throws on a malformed payload (schema guard)", async () => {
    const s = store(() => Promise.resolve(jsonRes(200, { nope: true })));
    await expect(s.list()).rejects.toBeInstanceOf(MemoryStoreError);
  });

  it("list throws on a network failure", async () => {
    const s = store(() => Promise.reject(new Error("ECONNREFUSED")));
    await expect(s.list()).rejects.toBeInstanceOf(MemoryStoreError);
  });

  it("add throws on a non-ok status", async () => {
    const s = store(() => Promise.resolve(jsonRes(422, { detail: "bad" })));
    await expect(s.add("x", "semantic")).rejects.toBeInstanceOf(
      MemoryStoreError,
    );
  });

  it("remove swallows a 404 (idempotent delete)", async () => {
    const s = store(() => Promise.resolve(new Response(null, { status: 404 })));
    await expect(s.remove("k")).resolves.toBeUndefined();
  });

  it("remove throws on a 500", async () => {
    const s = store(() => Promise.resolve(new Response(null, { status: 500 })));
    await expect(s.remove("k")).rejects.toBeInstanceOf(MemoryStoreError);
  });

  it("suppress swallows a 404 (idempotent — nothing to suppress)", async () => {
    const s = store(() => Promise.resolve(new Response(null, { status: 404 })));
    await expect(s.suppress("k", true)).resolves.toBeUndefined();
  });

  it("suppress throws on a 500", async () => {
    const s = store(() => Promise.resolve(new Response(null, { status: 500 })));
    await expect(s.suppress("k", true)).rejects.toBeInstanceOf(MemoryStoreError);
  });
});

describe("HttpMemoryStore — acceptance", () => {
  it("list returns the caller's items and forwards the bearer token", async () => {
    const fetchImpl = vi.fn(() =>
      Promise.resolve(
        jsonRes(200, {
          items: [
            { key: "k1", type: "semantic", content: "metric units", salience: 0.8 },
          ],
        }),
      ),
    ) as unknown as typeof fetch;
    const s = store(fetchImpl);
    const items = await s.list();
    expect(items).toHaveLength(1);
    expect(items[0]?.content).toBe("metric units");
    const firstCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0] as [string, RequestInit];
    expect(firstCall[1].headers).toMatchObject({
      authorization: "Bearer tok-123",
    });
  });

  it("add posts the create body and returns the created item", async () => {
    const seen: RequestInit[] = [];
    const fetchImpl = ((_url: string, init: RequestInit) => {
      seen.push(init);
      return Promise.resolve(
        jsonRes(200, {
          key: "k-new",
          type: "semantic",
          content: "likes dark mode",
          salience: null,
        }),
      );
    }) as unknown as typeof fetch;
    const s = store(fetchImpl);
    const item = await s.add("likes dark mode", "semantic");
    expect(item.key).toBe("k-new");
    expect(JSON.parse(String(seen[0]?.body))).toMatchObject({
      content: "likes dark mode",
      type: "semantic",
    });
  });

  it("remove hits the keyed DELETE path", async () => {
    const urls: string[] = [];
    const fetchImpl = ((url: string) => {
      urls.push(url);
      return Promise.resolve(new Response(null, { status: 200 }));
    }) as unknown as typeof fetch;
    const s = store(fetchImpl);
    await s.remove("k 1");
    expect(urls[0]).toBe("http://mw/agent/memory/k%201");
  });

  it("suppress PATCHes the keyed path with the flag and bearer token", async () => {
    let seen: { url: string; init: RequestInit } | null = null;
    const fetchImpl = ((url: string, init: RequestInit) => {
      seen = { url, init };
      return Promise.resolve(new Response(null, { status: 204 }));
    }) as unknown as typeof fetch;
    const s = store(fetchImpl);
    await s.suppress("k 1", true);
    expect(seen!.url).toBe("http://mw/agent/memory/k%201");
    expect(seen!.init.method).toBe("PATCH");
    expect(JSON.parse(seen!.init.body as string)).toEqual({ suppressed: true });
    expect((seen!.init.headers as Record<string, string>).authorization).toBe(
      "Bearer tok-123",
    );
  });
});
