import { NextRequest } from "next/server";
import {
  makeMemoryCreateHandler,
  makeMemoryListHandler,
} from "@/lib/bff/handlers";
import { serverPortBag } from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  return makeMemoryListHandler({
    auth: bag.authProvider,
    memoryStore: bag.memoryStore,
  })(req);
}

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  return makeMemoryCreateHandler({
    auth: bag.authProvider,
    memoryStore: bag.memoryStore,
  })(req);
}
