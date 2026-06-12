/**
 * Understanding edit proxy (task_understanding plan Phase 4).
 *
 * Thin BFF Route Handler (B6, FE-AP-3): authenticates via the AuthProvider
 * port, validates the edit against the wire schema, and forwards to the
 * middleware edit endpoint. Per F-R9 the BFF holds no cloud credentials —
 * it forwards the WorkOS access token as `Authorization: Bearer` only.
 */

import { NextRequest } from "next/server";
import { makeUnderstandingEditHandler } from "@/lib/bff/handlers";
import {
  forwardToMiddleware,
  serverPortBag,
} from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ threadId: string }> },
): Promise<Response> {
  const { threadId } = await ctx.params;
  const bag = serverPortBag();
  return makeUnderstandingEditHandler({
    auth: bag.authProvider,
    forward: forwardToMiddleware,
  })(req, threadId);
}
