/**
 * SSE streaming proxy (S3.9.1 / S3.5.2).
 *
 * Thin BFF Route Handler (B6, FE-AP-3): authenticates via the AuthProvider
 * port, then forwards the request to the middleware via the composition
 * helper `forwardToMiddleware`. Response bytes are piped through
 * `proxySSE` to set the X6 streaming-headers contract.
 *
 * Per F-R9 the BFF holds no cloud credentials -- it forwards the WorkOS
 * access token as `Authorization: Bearer` and nothing else. Per C4/C5
 * the route handler reads no env directly; `forwardToMiddleware` owns
 * the upstream URL.
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
  const claim = await bag.authProvider.getSession();
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
