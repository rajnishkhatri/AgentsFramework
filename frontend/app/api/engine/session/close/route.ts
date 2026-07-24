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
  requireOwnedOpenSession,
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
  // T R.12 / FR-C2: reject a re-close (already-closed session) so a double
  // close can never re-tally with late attempts.
  const owned = await requireOwnedOpenSession(db, parsed.session_id, learnerId);
  if (!owned.ok) return owned.response;

  const attempts = await db.listSessionAttempts(parsed.session_id);
  const tally = commitFirstTally(attempts);
  // T R.12: the served-pointer clear (`current_question_id = NULL`) is folded
  // INTO patchSessionClose as one atomic UPDATE (FR-B3c), so a partial apply
  // (pointer cleared, close not written) can never leave a session half-closed.
  const closed = await db.patchSessionClose(parsed.session_id, {
    ended_at: new Date().toISOString(),
    score_correct: tally.score_correct,
    score_total: tally.score_total,
  });
  return jsonOk(closed);
}
