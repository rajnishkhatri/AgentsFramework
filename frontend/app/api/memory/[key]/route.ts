import { NextRequest } from "next/server";
import { makeMemoryDeleteHandler } from "@/lib/bff/handlers";
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
