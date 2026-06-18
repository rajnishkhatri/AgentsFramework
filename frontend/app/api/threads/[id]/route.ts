import { NextRequest } from "next/server";
import {
  makeThreadArchiveHandler,
  makeThreadGetHandler,
  makeThreadRenameHandler,
} from "@/lib/bff/handlers";
import { serverPortBag } from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const { id } = await ctx.params;
  return makeThreadGetHandler({
    auth: bag.authProvider,
    threadStore: bag.threadStore,
  })(req, { params: { id } });
}

export async function PATCH(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const { id } = await ctx.params;
  return makeThreadRenameHandler({
    auth: bag.authProvider,
    threadStore: bag.threadStore,
  })(req, { params: { id } });
}

export async function DELETE(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const { id } = await ctx.params;
  return makeThreadArchiveHandler({
    auth: bag.authProvider,
    threadStore: bag.threadStore,
  })(req, { params: { id } });
}
