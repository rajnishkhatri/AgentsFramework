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
import { commitFirstTally, isAtTargetCount } from "@/lib/bff/engine_tally";
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
    return jsonOk({
      session: null,
      running_score: null,
      pointer_attempted: false,
      complete: false,
    });
  }
  const attempts = await db.listSessionAttempts(session.id);
  const running_score = commitFirstTally(attempts);
  // FR-B3-feedback: any attempt row on the pointer (incl. non-resolving wrong
  // first grade) means resume must advance, not re-show.
  const pointerId = session.current_question_id ?? null;
  const pointer_attempted =
    pointerId != null &&
    attempts.some((attempt) => attempt.question_id === pointerId);
  // FR-C2 / T R.3: at-target open sessions are complete — client closes to
  // summary instead of resuming into a (target+1)th serve.
  const complete = isAtTargetCount(session.target_count, running_score.score_total);
  return jsonOk({ session, running_score, pointer_attempted, complete });
}
