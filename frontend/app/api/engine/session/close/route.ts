/**
 * POST /api/engine/session/close — server-computed commit-first tally (FR-B10).
 * Ignores any client-provided score.
 */

import { NextRequest } from "next/server";
import { z } from "zod";
import { engineDb, serverPortBag } from "@/lib/bff/server_composition";
import {
  badRequest,
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
  requireOwnedSession,
} from "@/lib/bff/engine_guard";
import { commitFirstTally } from "@/lib/bff/engine_tally";

export const dynamic = "force-dynamic";

const Body = z.object({
  session_id: z.string().min(1),
});

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  let parsed: z.infer<typeof Body>;
  try {
    parsed = Body.parse(await req.json());
  } catch {
    return badRequest();
  }

  const db = engineDb();
  const owned = await requireOwnedSession(db, parsed.session_id, learnerId);
  if (!owned.ok) return owned.response;

  const attempts = await db.listSessionAttempts(parsed.session_id);
  const tally = commitFirstTally(attempts);
  await db.setSessionCurrentQuestion(parsed.session_id, null);
  const closed = await db.patchSessionClose(parsed.session_id, {
    ended_at: new Date().toISOString(),
    score_correct: tally.score_correct,
    score_total: tally.score_total,
  });
  return jsonOk(closed);
}
