import { NextRequest } from "next/server";
import { makeRunCancelHandler } from "@/lib/bff/handlers";
import { serverPortBag } from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  return makeRunCancelHandler({
    auth: bag.authProvider,
    agentRuntimeClient: bag.agentRuntimeClient,
  })(req);
}
