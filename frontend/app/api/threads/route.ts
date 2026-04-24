import { NextRequest } from "next/server";
import {
  makeThreadCreateHandler,
  makeThreadListHandler,
} from "@/lib/bff/handlers";
import { serverPortBag } from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  return makeThreadListHandler({
    auth: bag.authProvider,
    threadStore: bag.threadStore,
  })(req);
}

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  return makeThreadCreateHandler({
    auth: bag.authProvider,
    threadStore: bag.threadStore,
  })(req);
}
