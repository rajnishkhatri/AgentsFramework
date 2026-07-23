/**
 * GET /api/engine/summary?session=<id> — coarse read (6→1) for use_summary (T A.9).
 */

import { NextRequest } from "next/server";
import { engineDb, enginePorts, serverPortBag } from "@/lib/bff/server_composition";
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
  const ports = enginePorts();

  const [skills, skill_states, misses, served_question_ids, attempts] =
    await Promise.all([
      ports.skillTaxonomy.list(session.subject),
      db.listSkillState(session.subject, learnerId),
      db.listMisses(session.subject, learnerId),
      db.listSessionQuestionIds(sessionId),
      db.listSessionAttempts(sessionId),
    ]);

  const questionIds = [
    ...new Set([...misses.map((m) => m.question_id), ...served_question_ids]),
  ];
  const questions = (
    await Promise.all(questionIds.map((id) => ports.questionRepo.get(id)))
  ).filter((q): q is NonNullable<typeof q> => q != null);

  return jsonOk({
    session,
    skills,
    skill_states,
    misses,
    served_question_ids,
    attempts,
    miss_questions: questions,
    questions,
  });
}
