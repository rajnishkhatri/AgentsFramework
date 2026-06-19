/**
 * BFF Route Handler factories (S3.9.1).
 *
 * Per FRONTEND_STYLE_GUIDE B4-B6 and FE-AP-3: Route Handlers are
 * composition adapters -- port calls and SSE byte-forward only. No
 * business logic. The handlers in this file are pure functions that take
 * a `Request` and return a `Response`; the `route.ts` files in
 * `app/api/...` thin-wrap them by pulling ports from server-side
 * composition.
 *
 * Imports: ports/, transport/edge_proxy, wire/. No SDK, no React.
 */

import {
  MemoryCreateRequestSchema,
  MemorySuppressRequestSchema,
  TaskUnderstandingEditRequestSchema,
  ThreadAppendRequestSchema,
  ThreadCreateRequestSchema,
  ThreadRenameRequestSchema,
} from "../wire/agent_protocol";
import type { AuthProvider } from "../ports/auth_provider";
import type { AgentRuntimeClient } from "../ports/agent_runtime_client";
import type { ThreadStore } from "../ports/thread_store";
import type { MemoryStore } from "../ports/memory_store";

const NO_STORE = { "cache-control": "no-store" };

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...NO_STORE },
  });
}

function unauthorized(): Response {
  return json(401, { error: "unauthorized" });
}

function badRequest(reason: string): Response {
  return json(400, { error: "bad_request", reason });
}

function notFound(): Response {
  return json(404, { error: "not_found" });
}

interface ThreadDeps {
  readonly auth: AuthProvider;
  readonly threadStore: ThreadStore;
}

interface RuntimeDeps {
  readonly auth: AuthProvider;
  readonly agentRuntimeClient: AgentRuntimeClient;
}

export function makeThreadCreateHandler(
  deps: ThreadDeps,
): (req: Request) => Promise<Response> {
  return async (req) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return badRequest("invalid_json");
    }
    const parsed = ThreadCreateRequestSchema.safeParse(body);
    if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "");
    const created = await deps.threadStore.create(claim, parsed.data);
    return json(200, created);
  };
}

export function makeThreadListHandler(
  deps: ThreadDeps,
): (req: Request) => Promise<Response> {
  return async (req) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    const url = new URL(req.url);
    const cursor = url.searchParams.get("cursor");
    const limitStr = url.searchParams.get("limit");
    const limit = limitStr ? Math.max(1, Math.min(100, Number(limitStr))) : 20;
    const page = await deps.threadStore.list(claim, { cursor, limit });
    return json(200, page);
  };
}

export function makeThreadGetHandler(
  deps: ThreadDeps,
): (req: Request, ctx: { params: { id: string } }) => Promise<Response> {
  return async (_req, ctx) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    const t = await deps.threadStore.get(claim, ctx.params.id);
    if (!t) return notFound();
    return json(200, t);
  };
}

export function makeThreadRenameHandler(
  deps: ThreadDeps,
): (req: Request, ctx: { params: { id: string } }) => Promise<Response> {
  return async (req, ctx) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return badRequest("invalid_json");
    }
    const parsed = ThreadRenameRequestSchema.safeParse(body);
    if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "");
    try {
      const updated = await deps.threadStore.rename(
        claim,
        ctx.params.id,
        parsed.data.title,
      );
      return json(200, updated);
    } catch {
      // The ThreadStore contract throws on missing OR not-owned; collapse both
      // to 404 so the response is no existence oracle (FD3.SEC).
      return notFound();
    }
  };
}

export function makeThreadAppendHandler(
  deps: ThreadDeps,
): (req: Request, ctx: { params: { id: string } }) => Promise<Response> {
  return async (req, ctx) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return badRequest("invalid_json");
    }
    const parsed = ThreadAppendRequestSchema.safeParse(body);
    if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "");
    try {
      await deps.threadStore.appendTurn(claim, ctx.params.id, {
        user: parsed.data.user,
        assistant: parsed.data.assistant,
        turnId: parsed.data.turn_id,
      });
      return new Response(null, { status: 204, headers: NO_STORE });
    } catch {
      // appendTurn throws on missing OR not-owned; collapse both to 404 so the
      // response is no existence oracle (FD3.SEC), mirroring rename.
      return notFound();
    }
  };
}

export function makeThreadArchiveHandler(
  deps: ThreadDeps,
): (req: Request, ctx: { params: { id: string } }) => Promise<Response> {
  return async (_req, ctx) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    // archive() is a SOFT delete and idempotent (A6): missing/non-owned is a
    // silent no-op, so the caller always sees 204.
    await deps.threadStore.archive(claim, ctx.params.id);
    return new Response(null, { status: 204, headers: NO_STORE });
  };
}

export function makeRunCancelHandler(
  deps: RuntimeDeps,
): (req: Request) => Promise<Response> {
  return async (req) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    let body: { run_id?: unknown };
    try {
      body = (await req.json()) as { run_id?: unknown };
    } catch {
      return badRequest("invalid_json");
    }
    if (typeof body.run_id !== "string") return badRequest("run_id_required");
    await deps.agentRuntimeClient.cancel(body.run_id);
    return new Response(null, { status: 204, headers: NO_STORE });
  };
}

// ── Memory panel (Phase 3) ────────────────────────────────────────────
//
// Auth-gated like the thread handlers (B6: caller's own only). The
// MemoryStore port forwards to the middleware over the caller's bearer token;
// the cross-user-leak guard is enforced server-side on identity.owner, so the
// handler never sees or passes a user_id.

interface MemoryDeps {
  readonly auth: AuthProvider;
  readonly memoryStore: MemoryStore;
}

export function makeMemoryListHandler(
  deps: MemoryDeps,
): (req: Request) => Promise<Response> {
  return async () => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    const items = await deps.memoryStore.list();
    return json(200, { items });
  };
}

export function makeMemoryCreateHandler(
  deps: MemoryDeps,
): (req: Request) => Promise<Response> {
  return async (req) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return badRequest("invalid_json");
    }
    const parsed = MemoryCreateRequestSchema.safeParse(body);
    if (!parsed.success) {
      return badRequest(parsed.error.issues[0]?.message ?? "");
    }
    const created = await deps.memoryStore.add(
      parsed.data.content,
      parsed.data.type,
      parsed.data.salience,
    );
    return json(200, created);
  };
}

export function makeMemoryDeleteHandler(
  deps: MemoryDeps,
): (req: Request, ctx: { params: { key: string } }) => Promise<Response> {
  return async (_req, ctx) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    await deps.memoryStore.remove(ctx.params.key);
    return new Response(null, { status: 204, headers: NO_STORE });
  };
}

// Phase B (D5): reject = soft-suppress. PATCH /api/memory/{key} flips the
// suppressed flag (recall excludes it server-side; the row is retained). The
// port's suppress() is idempotent on a missing key, so a 404 from upstream
// collapses to 204 there — this handler simply mirrors the create/delete shape
// (auth + Zod + port call, FE-AP-3).
export function makeMemorySuppressHandler(
  deps: MemoryDeps,
): (req: Request, ctx: { params: { key: string } }) => Promise<Response> {
  return async (req, ctx) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return badRequest("invalid_json");
    }
    const parsed = MemorySuppressRequestSchema.safeParse(body);
    if (!parsed.success) {
      return badRequest(parsed.error.issues[0]?.message ?? "");
    }
    await deps.memoryStore.suppress(ctx.params.key, parsed.data.suppressed);
    return new Response(null, { status: 204, headers: NO_STORE });
  };
}

// ── Understanding edit (task_understanding plan Phase 4) ──────────────

interface UnderstandingEditDeps {
  readonly auth: AuthProvider;
  /** `forwardToMiddleware`-shaped dependency (F-R9: bearer in, no creds). */
  readonly forward: (
    path: string,
    init: { method: string; headers: Record<string, string>; body: string },
  ) => Promise<Response>;
}

export function makeUnderstandingEditHandler(
  deps: UnderstandingEditDeps,
): (req: Request, threadId: string) => Promise<Response> {
  return async (req, threadId) => {
    const claim = await deps.auth.getSession();
    if (!claim) return unauthorized();
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return badRequest("invalid_json");
    }
    const parsed = TaskUnderstandingEditRequestSchema.safeParse(body);
    if (!parsed.success) {
      return json(422, { error: "invalid_edit", issues: parsed.error.issues });
    }
    const token = await deps.auth.getAccessToken();
    const upstream = await deps.forward(
      `/run/understanding/${encodeURIComponent(threadId)}`,
      {
        method: "POST",
        headers: {
          authorization: `Bearer ${token}`,
          "content-type": "application/json",
        },
        body: JSON.stringify(parsed.data),
      },
    );
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": "application/json", ...NO_STORE },
    });
  };
}
