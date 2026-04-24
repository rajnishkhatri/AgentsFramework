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

import { ThreadCreateRequestSchema } from "../wire/agent_protocol";
import type { AuthProvider } from "../ports/auth_provider";
import type { AgentRuntimeClient } from "../ports/agent_runtime_client";
import type { ThreadStore } from "../ports/thread_store";

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
