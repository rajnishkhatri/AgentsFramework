/**
 * L2 (reproducible) tests for the SSE client.
 *
 * Per the TDD-Agentic-Systems prompt §Protocol B: contract-driven TDD with
 * mocked I/O. EventSource is the dependency; we inject a fake factory so
 * the tests are deterministic.
 *
 * Failure paths first (X1-X5 + Check 4):
 *   - Zod parse failure -> yields SSEParseError sentinel (adapter maps to run_error)
 *   - Heartbeat timeout (no event for >30s) -> yields SSEHeartbeatTimeout sentinel
 *   - Backpressure overflow (>N unread events) -> drop-oldest behavior
 *   - Last-Event-ID resumption -> reconnect attaches the header
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  connectSSE,
  isSSEHeartbeatTimeout,
  isSSEParseError,
  type EventSourceFactory,
  type SSEMessage,
  type SSEYield,
} from "./sse_client";
import type { AGUIEvent } from "../wire/ag_ui_events";

type Listener = (msg: SSEMessage) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  public readyState: 0 | 1 | 2 = 0;
  public lastEventIdHeader: string | null = null;
  private msgListeners: Listener[] = [];
  private errListeners: ((e: unknown) => void)[] = [];
  private openListeners: (() => void)[] = [];

  constructor(
    public url: string,
    public init: { withCredentials?: boolean; headers?: Record<string, string> } = {},
  ) {
    FakeEventSource.instances.push(this);
    this.lastEventIdHeader = init.headers?.["Last-Event-ID"] ?? null;
  }

  addEventListener(name: string, listener: any): void {
    if (name === "message") this.msgListeners.push(listener as Listener);
    else if (name === "error") this.errListeners.push(listener as never);
    else if (name === "open") this.openListeners.push(listener as never);
  }
  emitOpen(): void {
    this.readyState = 1;
    for (const l of this.openListeners) l();
  }
  emitMessage(data: string, id?: string): void {
    for (const l of this.msgListeners) l({ data, lastEventId: id ?? "" });
  }
  emitError(e: unknown = new Error("boom")): void {
    this.readyState = 2;
    for (const l of this.errListeners) l(e);
  }
  close(): void {
    this.readyState = 2;
  }
}

const factory: EventSourceFactory = (url, init) =>
  new FakeEventSource(url, init) as unknown as EventSource;

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

async function pump<T>(it: AsyncIterable<T>, n: number): Promise<T[]> {
  const out: T[] = [];
  for await (const v of it) {
    out.push(v);
    if (out.length >= n) break;
  }
  return out;
}

const VALID_RUN_STARTED_DATA = (trace_id = "trace-001") =>
  JSON.stringify({
    type: "RUN_STARTED",
    run_id: "r1",
    thread_id: "t1",
    raw_event: { trace_id },
  });

describe("connectSSE Zod parse failure -> SSEParseError sentinel [X2]", () => {
  it("yields a parse-error sentinel on bad JSON", async () => {
    const stream = connectSSE({
      url: "/api/run/stream",
      runId: "r1",
      eventSourceFactory: factory,
    });
    const collector = pump(stream, 1);
    queueMicrotask(() => {
      const es = FakeEventSource.instances[0]!;
      es.emitOpen();
      es.emitMessage("{not-json");
    });
    const events = await collector;
    expect(events).toHaveLength(1);
    expect(isSSEParseError(events[0]!)).toBe(true);
  });
});

describe("connectSSE heartbeat timeout [X4]", () => {
  it("yields a heartbeat-timeout sentinel after the threshold", async () => {
    const stream = connectSSE({
      url: "/api/run/stream",
      runId: "r1",
      eventSourceFactory: factory,
      heartbeatTimeoutMs: 30_000,
    });
    const collector = pump(stream, 1);
    queueMicrotask(() => FakeEventSource.instances[0]!.emitOpen());
    await vi.advanceTimersByTimeAsync(31_000);
    const events = await collector;
    expect(isSSEHeartbeatTimeout(events[0]!)).toBe(true);
  });
});

describe("connectSSE backpressure (drop-oldest) [X5]", () => {
  it("never grows the internal buffer beyond bufferSize when consumer is slow", async () => {
    const stream = connectSSE({
      url: "/api/run/stream",
      runId: "r1",
      eventSourceFactory: factory,
      bufferSize: 4,
    });
    queueMicrotask(() => {
      const es = FakeEventSource.instances[0]!;
      es.emitOpen();
      for (let i = 0; i < 10; i++) {
        es.emitMessage(VALID_RUN_STARTED_DATA(`trace-${i}`));
      }
    });
    const drained = await pump(stream, 4);
    expect(drained).toHaveLength(4);
    const traceIds = drained
      .filter((e): e is AGUIEvent => !isSSEParseError(e) && !isSSEHeartbeatTimeout(e))
      .map((e) => e.raw_event?.trace_id);
    expect(traceIds).toEqual(["trace-6", "trace-7", "trace-8", "trace-9"]);
  });
});

describe("connectSSE Last-Event-ID resumption [X3]", () => {
  it("reconnect attaches the most recent event id as Last-Event-ID", async () => {
    const stream = connectSSE({
      url: "/api/run/stream",
      runId: "r1",
      eventSourceFactory: factory,
      reconnectDelayMs: 0,
    });
    const collector = pump(stream, 2);
    queueMicrotask(() => {
      const es = FakeEventSource.instances[0]!;
      es.emitOpen();
      es.emitMessage(VALID_RUN_STARTED_DATA("trace-001"), "evt-7");
      es.emitError(new Error("dropped"));
    });
    await vi.advanceTimersByTimeAsync(10);
    queueMicrotask(() => {
      const es = FakeEventSource.instances[1]!;
      es.emitOpen();
      es.emitMessage(VALID_RUN_STARTED_DATA("trace-002"), "evt-8");
    });
    const events = await collector;
    expect(events).toHaveLength(2);
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[1]!.lastEventIdHeader).toBe("evt-7");
  });
});

describe("connectSSE happy path", () => {
  it("yields parsed AGUIEvents with raw_event.trace_id forwarded", async () => {
    const stream = connectSSE({
      url: "/api/run/stream",
      runId: "r1",
      eventSourceFactory: factory,
    });
    const collector = pump(stream, 1);
    queueMicrotask(() => {
      const es = FakeEventSource.instances[0]!;
      es.emitOpen();
      es.emitMessage(VALID_RUN_STARTED_DATA("trace-001"));
    });
    const events = await collector;
    const evt = events[0]!;
    expect(isSSEParseError(evt)).toBe(false);
    if (!isSSEParseError(evt) && !isSSEHeartbeatTimeout(evt)) {
      expect(evt.type).toBe("RUN_STARTED");
      expect(evt.raw_event?.trace_id).toBe("trace-001");
    }
  });
});
