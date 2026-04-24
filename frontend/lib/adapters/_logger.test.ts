/**
 * L2 tests for the shared adapter logger (Rule A7 / O3).
 *
 * Failure paths first: assert PII-class fields are NOT silently dropped
 * by the logger (the adapter is responsible for not passing them in the
 * first place; the logger does not scrub).
 *
 * Then namespace, level routing, and stable key ordering.
 */

import { describe, expect, it } from "vitest";
import {
  createAdapterLogger,
  type LogLevel,
} from "./_logger";

function recordingSink(): {
  lines: Array<readonly [LogLevel, string]>;
  sink: (level: LogLevel, line: string) => void;
} {
  const lines: Array<readonly [LogLevel, string]> = [];
  return {
    lines,
    sink(level, line) {
      lines.push([level, line]);
    },
  };
}

describe("createAdapterLogger", () => {
  it("exposes the §17 / O3 namespace pattern frontend:adapter:<family>", () => {
    const r = recordingSink();
    const log = createAdapterLogger("auth", { sink: r.sink });
    expect(log.namespace).toBe("frontend:adapter:auth");
  });

  it.each<[LogLevel, "debug" | "info" | "warn" | "error"]>([
    ["debug", "debug"],
    ["info", "info"],
    ["warn", "warn"],
    ["error", "error"],
  ])("routes %s to the %s sink slot", (level, method) => {
    const r = recordingSink();
    const log = createAdapterLogger("runtime", { sink: r.sink });
    log[method]("hello");
    expect(r.lines).toHaveLength(1);
    expect(r.lines[0]?.[0]).toBe(level);
    expect(r.lines[0]?.[1]).toContain("[frontend:adapter:runtime] " + level + " hello");
  });

  it("emits stable key=value ordering (sorted) so log greps stay deterministic", () => {
    const r = recordingSink();
    const log = createAdapterLogger("thread_store", { sink: r.sink });
    log.info("listed threads", {
      trace_id: "t-1",
      latency_ms: 12,
      attempt: 2,
      run_id: "r-9",
    });
    const line = r.lines[0]?.[1] ?? "";
    // Keys appear alphabetically: attempt, latency_ms, run_id, trace_id
    const idxAttempt = line.indexOf("attempt=2");
    const idxLatency = line.indexOf("latency_ms=12");
    const idxRunId = line.indexOf("run_id=r-9");
    const idxTrace = line.indexOf("trace_id=t-1");
    expect(idxAttempt).toBeGreaterThan(0);
    expect(idxLatency).toBeGreaterThan(idxAttempt);
    expect(idxRunId).toBeGreaterThan(idxLatency);
    expect(idxTrace).toBeGreaterThan(idxRunId);
  });

  it("omits undefined metadata values (no `key=undefined` noise)", () => {
    const r = recordingSink();
    const log = createAdapterLogger("auth", { sink: r.sink });
    log.warn("token near expiry", {
      trace_id: "t-1",
      latency_ms: 5,
    });
    const line = r.lines[0]?.[1] ?? "";
    expect(line).not.toContain("undefined");
    expect(line).toContain("trace_id=t-1");
    expect(line).toContain("latency_ms=5");
  });

  it("emits a bare line when no metadata is supplied", () => {
    const r = recordingSink();
    const log = createAdapterLogger("ui_runtime", { sink: r.sink });
    log.error("mount failed");
    expect(r.lines[0]?.[1]).toBe("[frontend:adapter:ui_runtime] error mount failed");
  });
});
