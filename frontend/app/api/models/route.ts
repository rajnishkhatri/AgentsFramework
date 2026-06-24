/**
 * Models catalog proxy (model picker).
 *
 * Thin BFF Route Handler (B6, FE-AP-3): authenticates via the AuthProvider
 * port, then forwards the WorkOS access token to the backend `GET /models` as
 * `Authorization: Bearer` only (F-R9: the BFF holds no cloud credentials). The
 * backend returns the active registry's catalog (name+tier, no pricing).
 */

import { NextRequest } from "next/server";
import { makeModelsListHandler } from "@/lib/bff/handlers";
import {
  forwardToMiddleware,
  serverPortBag,
} from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  return makeModelsListHandler({
    auth: bag.authProvider,
    forward: forwardToMiddleware,
  })(req);
}
