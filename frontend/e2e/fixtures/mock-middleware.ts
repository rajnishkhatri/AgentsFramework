/**
 * Mock Python middleware HTTP server for Tier 2 BFF integration tests.
 *
 * Stands in for the FastAPI app at `middleware/server.py` so the real
 * Next.js BFF routes (which `fetch(MIDDLEWARE_URL + path)` via
 * `forwardToMiddleware`) can be exercised end-to-end without a Python
 * runtime.
 *
 * Endpoints (mirroring `agent_ui_adapter` mounted on the production
 * middleware):
 *   GET  /healthz                 -> 200 "ok"
 *   POST /run/stream              -> 200 text/event-stream (canned scenarios)
 *   POST /run/cancel              -> 204
 *   POST /threads                 -> 200 ThreadState
 *   GET  /threads                 -> 200 ThreadListPage
 *   GET  /threads/{id}            -> 200 ThreadState | 404
 *
 * Auth: every endpoint except /healthz requires `Authorization: Bearer ...`.
 * Returns 401 otherwise. Tokens are NOT cryptographically validated -- the
 * mock only checks the header is present, mirroring the BFF-to-middleware
 * contract expectation.
 *
 * Configurable via env:
 *   MOCK_MIDDLEWARE_PORT   -- listen port (default 8765)
 *   MOCK_MIDDLEWARE_DELAY  -- per-event SSE delay ms (default 50)
 *   MOCK_MIDDLEWARE_FAIL   -- comma-separated paths that should return 500
 *
 * Run standalone (used by Playwright webServer):
 *   tsx e2e/fixtures/mock-middleware.ts
 */

import http from "node:http";
import {
  plainMarkdown,
  toolCallSuccess,
  longStream,
  runError,
  generativeCanvas,
  generativePanel,
  DEFAULT_TRACE_ID,
} from "./scenarios";
import type { AGUIEvent } from "../../lib/wire/ag_ui_events";

const PORT = Number(process.env.MOCK_MIDDLEWARE_PORT ?? "8765");
const DELAY_MS = Number(process.env.MOCK_MIDDLEWARE_DELAY ?? "50");
const FAIL_PATHS = new Set(
  (process.env.MOCK_MIDDLEWARE_FAIL ?? "").split(",").filter(Boolean),
);

const SCENARIOS = {
  plainMarkdown,
  toolCallSuccess,
  longStream,
  runError,
  generativeCanvas,
  generativePanel,
} as const;

type ScenarioName = keyof typeof SCENARIOS;

const NOW = () => new Date().toISOString();

const SAMPLE_THREADS = [
  { thread_id: "t-1", user_id: "u-1", messages: [], created_at: NOW(), updated_at: NOW() },
  { thread_id: "t-2", user_id: "u-1", messages: [], created_at: NOW(), updated_at: NOW() },
];

function selectScenario(body: string): ScenarioName {
  const lower = body.toLowerCase();
  if (lower.includes("list") && lower.includes("file")) return "toolCallSuccess";
  if (lower.includes("quantum")) return "longStream";
  if (lower.includes("pyramid")) return "generativePanel";
  if (lower.includes("sine") || lower.includes("sandbox")) return "generativeCanvas";
  if (lower.includes("etc/shadow")) return "runError";
  return "plainMarkdown";
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(c as Buffer));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    req.on("error", reject);
  });
}

function requireAuth(req: http.IncomingMessage, res: http.ServerResponse): boolean {
  const auth = req.headers["authorization"];
  if (!auth || !auth.toString().toLowerCase().startsWith("bearer ")) {
    res.writeHead(401, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "unauthorized" }));
    return false;
  }
  return true;
}

async function writeSSE(
  res: http.ServerResponse,
  events: ReadonlyArray<AGUIEvent>,
  delayMs: number,
): Promise<void> {
  res.writeHead(200, {
    "content-type": "text/event-stream",
    "cache-control": "no-cache, no-transform",
    "x-accel-buffering": "no",
    "x-trace-id": DEFAULT_TRACE_ID,
    connection: "keep-alive",
  });

  const heartbeat = setInterval(() => {
    try {
      res.write(": ping\n\n");
    } catch {
      // already closed
    }
  }, 5_000);

  try {
    for (const evt of events) {
      res.write(`data: ${JSON.stringify(evt)}\n\n`);
      if (delayMs > 0) {
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
  } finally {
    clearInterval(heartbeat);
    res.end();
  }
}

function jsonResponse(
  res: http.ServerResponse,
  status: number,
  payload: unknown,
): void {
  res.writeHead(status, { "content-type": "application/json", "x-trace-id": DEFAULT_TRACE_ID });
  res.end(JSON.stringify(payload));
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://localhost:${PORT}`);
  const path = url.pathname;
  const method = req.method ?? "GET";

  if (path === "/healthz") {
    res.writeHead(200, { "content-type": "text/plain" });
    res.end("ok");
    return;
  }

  if (FAIL_PATHS.has(path)) {
    jsonResponse(res, 500, { error: "injected_failure", trace_id: DEFAULT_TRACE_ID });
    return;
  }

  if (!requireAuth(req, res)) return;

  if (path === "/run/stream" && method === "POST") {
    const body = await readBody(req);
    const scenarioOverride = url.searchParams.get("scenario") as ScenarioName | null;
    const scenarioName: ScenarioName = scenarioOverride && SCENARIOS[scenarioOverride]
      ? scenarioOverride
      : selectScenario(body);
    const events = SCENARIOS[scenarioName]({ traceId: DEFAULT_TRACE_ID });
    await writeSSE(res, events, DELAY_MS);
    return;
  }

  if (path === "/run/cancel" && method === "POST") {
    res.writeHead(204);
    res.end();
    return;
  }

  if (path === "/threads" && method === "GET") {
    jsonResponse(res, 200, { threads: SAMPLE_THREADS, nextCursor: null });
    return;
  }

  if (path === "/threads" && method === "POST") {
    jsonResponse(res, 200, {
      thread_id: `t-${Date.now()}`,
      user_id: "u-1",
      messages: [],
      created_at: NOW(),
      updated_at: NOW(),
    });
    return;
  }

  const threadIdMatch = path.match(/^\/threads\/([^/]+)$/);
  if (threadIdMatch && method === "GET") {
    const id = threadIdMatch[1]!;
    const thread = SAMPLE_THREADS.find((t) => t.thread_id === id);
    if (!thread) {
      jsonResponse(res, 404, { error: "not_found" });
      return;
    }
    jsonResponse(res, 200, thread);
    return;
  }

  jsonResponse(res, 404, { error: "not_found", path });
});

server.listen(PORT, () => {
  console.log(
    `[mock-middleware] listening on :${PORT} (delay=${DELAY_MS}ms, fail=${[...FAIL_PATHS].join(",") || "none"})`,
  );
});

process.on("SIGTERM", () => server.close(() => process.exit(0)));
process.on("SIGINT", () => server.close(() => process.exit(0)));
