/**
 * GET /api/engine/quiz/bootstrap?session=<id> — pure read (coach-v3 §5).
 *
 * Returns session + current item + hint ladder. Ownership via
 * `requireOwnedSession` (FR-A2a) before any dependent read.
 */

import { NextRequest } from "next/server";
import { engineDb, serverPortBag } from "@/lib/bff/server_composition";
import {
  badRequest,
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
  requireOwnedSession,
} from "@/lib/bff/engine_guard";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  const sessionId = req.nextUrl.searchParams.get("session");
  if (!sessionId) return badRequest("missing_session");

  const db = engineDb();
  const owned = await requireOwnedSession(db, sessionId, learnerId);
  if (!owned.ok) return owned.response;

  const session = owned.session;
  const questionId = session.current_question_id ?? null;
  const question = questionId ? await db.getQuestion(questionId) : null;
  const hints =
    questionId != null
      ? await db.listReviewedHints(session.subject, questionId)
      : [];

  return jsonOk({ session, question, hints });
}
