// @vitest-environment happy-dom
/**
 * sse_client tests (Sprint 4 review F4).
 *
 * Stubs `EventSource` so we can synthesise `event: log` frames without an
 * actual server.  Covers:
 *   * malformed JSON in the `data` payload triggers `onError`,
 *   * Zod-invalid JSON triggers `onError`,
 *   * a well-formed frame triggers `onLog`,
 *   * `handle.close()` invokes `EventSource.close()` even after a frame.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

type Listener = (event: MessageEvent) => void;

class StubEventSource {
  static instances: StubEventSource[] = [];
  url: string;
  listeners: Map<string, Listener[]> = new Map();
  closed = false;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    StubEventSource.instances.push(this);
  }

  addEventListener(name: string, listener: Listener): void {
    const list = this.listeners.get(name) ?? [];
    list.push(listener);
    this.listeners.set(name, list);
  }

  removeEventListener(name: string, listener: Listener): void {
    const list = this.listeners.get(name) ?? [];
    this.listeners.set(
      name,
      list.filter((l) => l !== listener),
    );
  }

  close(): void {
    this.closed = true;
  }

  emit(name: string, data: string): void {
    const list = this.listeners.get(name) ?? [];
    for (const listener of list) {
      listener({ data } as MessageEvent);
    }
  }
}

beforeEach(() => {
  StubEventSource.instances = [];
  vi.stubGlobal("EventSource", StubEventSource as unknown as typeof EventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const VALID_FRAME = JSON.stringify({
  concern: "guards",
  timestamp: "2026-04-26T08:00:00.000Z",
  logger: "services.guardrails",
  level: "INFO",
  message: "ok",
  raw: "raw line",
});

describe("openLogStream — failure first", () => {
  it("invokes onError when the SSE data payload is not valid JSON", async () => {
    const onLog = vi.fn();
    const onError = vi.fn();
    const { openLogStream } = await import("./sse_client");
    openLogStream({
      baseUrl: "http://localhost:8001",
      onLog,
      onError,
    });
    const es = StubEventSource.instances[0]!;
    es.emit("log", "not-json{");
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0]?.[0]).toMatch(/Bad SSE log frame/);
    expect(onLog).not.toHaveBeenCalled();
  });

  it("invokes onError when the payload fails Zod parsing", async () => {
    const onLog = vi.fn();
    const onError = vi.fn();
    const { openLogStream } = await import("./sse_client");
    openLogStream({
      baseUrl: "http://localhost:8001",
      onLog,
      onError,
    });
    const es = StubEventSource.instances[0]!;
    es.emit("log", JSON.stringify({ concern: 123 }));
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0]?.[0]).toMatch(/SSE log frame failed Zod parse/);
    expect(onLog).not.toHaveBeenCalled();
  });

  it("invokes onError on transport-level error events", async () => {
    const onError = vi.fn();
    const { openLogStream } = await import("./sse_client");
    openLogStream({
      baseUrl: "http://localhost:8001",
      onLog: vi.fn(),
      onError,
    });
    const es = StubEventSource.instances[0]!;
    es.listeners.get("error")?.[0]?.({} as MessageEvent);
    expect(onError).toHaveBeenCalled();
  });
});

describe("openLogStream — acceptance", () => {
  it("forwards a well-formed frame to onLog", async () => {
    const onLog = vi.fn();
    const onError = vi.fn();
    const { openLogStream } = await import("./sse_client");
    openLogStream({
      baseUrl: "http://localhost:8001",
      onLog,
      onError,
    });
    const es = StubEventSource.instances[0]!;
    es.emit("log", VALID_FRAME);
    expect(onLog).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
    const row = onLog.mock.calls[0]?.[0];
    expect(row.message).toBe("ok");
    expect(row.concern).toBe("guards");
  });

  it("encodes concern, level, and search into the connection URL", async () => {
    const { openLogStream } = await import("./sse_client");
    openLogStream({
      baseUrl: "http://localhost:8001",
      concerns: ["guards", "tools"],
      level: "ERROR",
      search: "boom",
      onLog: vi.fn(),
    });
    const es = StubEventSource.instances[0]!;
    expect(es.url).toContain("/api/v1/logs/stream");
    expect(es.url).toContain("concerns=guards");
    expect(es.url).toContain("concerns=tools");
    expect(es.url).toContain("level=ERROR");
    expect(es.url).toContain("search=boom");
  });

  it("calls EventSource.close() when handle.close() is invoked", async () => {
    const { openLogStream } = await import("./sse_client");
    const handle = openLogStream({
      baseUrl: "http://localhost:8001",
      onLog: vi.fn(),
    });
    const es = StubEventSource.instances[0]!;
    handle.close();
    expect(es.closed).toBe(true);
    // Calling close twice is safe.
    handle.close();
    expect(es.closed).toBe(true);
  });
});
