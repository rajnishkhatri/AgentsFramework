/**
 * GET /api/engine/session/active — newest open session + pointer + server tally.
 */

import { NextRequest } from "next/server";
import { engineDb, serverPortBag } from "@/lib/bff/server_composition";
import {
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
} from "@/lib/bff/engine_guard";
import { commitFirstTally } from "@/lib/bff/engine_tally";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  const subject =
    req.nextUrl.searchParams.get("subject")?.trim() || DEFAULT_SUBJECT;
  const db = engineDb();
  const session = await db.getNewestOpenSession(subject, learnerId);
  if (!session) {
    return jsonOk({ session: null, running_score: null });
  }
  const attempts = await db.listSessionAttempts(session.id);
  const running_score = commitFirstTally(attempts);
  return jsonOk({ session, running_score });
}
