/**
 * Coach SSE streaming proxy (Phase 2.1, FR-F / §5).
 *
 * The coach rides the CHAT runtime (plan OD-3 / design §7 divergence #1) — there
 * is no separate coach engine port — so this Route Handler is the same thin BFF
 * seam as /api/run/stream (B6, FE-AP-3): authenticate via the AuthProvider port,
 * forward to the middleware, pipe the bytes through `proxySSE` (X6 headers).
 *
 * It is a separate route only so the coach client streams from its own base
 * (`/api/coach/run/stream`), keeping the coach thread + persona selection
 * distinct from chat while reusing every transport invariant. The coach
 * `agent_id` (subject-coach-english) rides in the client request body; this
 * route adds no business logic and holds no cloud credentials (F-R9) — it
 * forwards the WorkOS access token as `Authorization: Bearer` and nothing else.
 */

import { NextRequest } from "next/server";
import { proxySSE } from "@/lib/transport/edge_proxy";
import {
  forwardToMiddleware,
  serverPortBag,
} from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  let claim = null;
  try {
    claim = await bag.authProvider.getSession();
  } catch {
    // Session retrieval failed — treat as unauthenticated.
  }

  if (!claim) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  }
  const token = await bag.authProvider.getAccessToken();
  const body = await req.text();
  const upstream = await forwardToMiddleware("/run/stream", {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
      accept: "text/event-stream",
    },
    body,
  });
  return proxySSE(upstream);
}
