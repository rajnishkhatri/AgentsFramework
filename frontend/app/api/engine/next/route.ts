/**
 * GET /api/engine/next?session=<id> — server-side scheduler pick (FR-B9 / T A.8).
 * Reconstructs served-set from attempts; does not return it on the wire.
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
import { EngineNotFoundError } from "@/lib/ports/engine/errors";

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

  const servedIds = await db.listSessionQuestionIds(sessionId);
  const servedSkillIds = await db.listSessionSkillIds(sessionId);
  const ports = enginePorts();

  let question = null;
  let skillId: string | null = null;

  try {
    if (session.mode === "adaptive") {
      const pick = await ports.scheduler.next(
        session.subject,
        learnerId,
        servedIds,
        servedSkillIds,
      );
      skillId = pick.skill_id;
      question = await ports.questionRepo.get(pick.question_id);
    } else if (session.mode === "drill" && session.skill_focus) {
      skillId = session.skill_focus;
      question = await ports.questionRepo.nextReviewed(
        session.subject,
        session.skill_focus,
        servedIds,
      );
    } else if (session.mode === "review") {
      const misses = await db.listMisses(session.subject, learnerId);
      const served = new Set(servedIds);
      const nextMiss = misses.find((m) => !served.has(m.question_id));
      if (nextMiss) {
        question = await ports.questionRepo.get(nextMiss.question_id);
        skillId = question?.skill_id ?? null;
      }
    }
  } catch (err) {
    if (!(err instanceof EngineNotFoundError)) throw err;
    // Exhausted / empty bank → honest no-content (FR-G3), not a 500.
  }

  if (!question) {
    return jsonOk({
      empty: true,
      reason: "no_content",
      question: null,
      hints: [],
      skill_id: null,
    });
  }

  const hints = await ports.hintRepo.list(session.subject, question.id, null);
  return jsonOk({
    empty: false,
    question,
    hints,
    skill_id: skillId ?? question.skill_id,
  });
}
