import { NextRequest } from "next/server";
import { makeThreadAppendHandler } from "@/lib/bff/handlers";
import { serverPortBag } from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

/**
 * Persist one completed conversation turn into the durable thread store
 * (the "save all chats" seam). Auth + Zod + port-call only (FE-AP-3): the
 * handler collapses missing/not-owned to 404 (no existence oracle).
 */
export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const { id } = await ctx.params;
  return makeThreadAppendHandler({
    auth: bag.authProvider,
    threadStore: bag.threadStore,
  })(req, { params: { id } });
}
