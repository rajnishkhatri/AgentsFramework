import { NextRequest } from "next/server";
import {
  makeMemoryDeleteHandler,
  makeMemorySuppressHandler,
} from "@/lib/bff/handlers";
import { serverPortBag } from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

export async function DELETE(
  req: NextRequest,
  ctx: { params: Promise<{ key: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const { key } = await ctx.params;
  return makeMemoryDeleteHandler({
    auth: bag.authProvider,
    memoryStore: bag.memoryStore,
  })(req, { params: { key } });
}

// Phase B (D5): reject = soft-suppress / un-suppress one of the caller's
// memories. Auth + Zod + port call only (FE-AP-3); same-origin cookie auth.
export async function PATCH(
  req: NextRequest,
  ctx: { params: Promise<{ key: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const { key } = await ctx.params;
  return makeMemorySuppressHandler({
    auth: bag.authProvider,
    memoryStore: bag.memoryStore,
  })(req, { params: { key } });
}
