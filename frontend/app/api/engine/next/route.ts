/**
 * GET /api/engine/next?session=<id> — server-side scheduler pick (FR-B9 / T A.8).
 * Reconstructs served-set from attempts; does not return it on the wire.
 * Adaptive mode layers content-fresh eligibility (FR-E1..E5) over FSRS.
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
import type { Question } from "@/lib/wire/engine_entities";

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

  let question: Question | null = null;
  let skillId: string | null = null;

  try {
    if (session.mode === "adaptive") {
      const pick = await pickAdaptive(
        ports,
        db,
        session.subject,
        learnerId,
        servedIds,
        servedSkillIds,
      );
      if (pick) {
        skillId = pick.skill_id;
        question = await ports.questionRepo.get(pick.question_id);
      }
    } else if (session.mode === "drill" && session.skill_focus) {
      skillId = session.skill_focus;
      question = await ports.questionRepo.nextReviewed(
        session.subject,
        session.skill_focus,
        servedIds,
      );
    } else if (session.mode === "review") {
      // FR-E5: review serves exact past misses — eligibility does not apply.
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
    // FR-G3 vs FR-C5: an actually empty reviewed bank is a setup failure;
    // otherwise this session exhausted its finite servable pool and should
    // close gracefully to Summary.
    const reviewedItems = await db.listReviewedTestItems(session.subject);
    return jsonOk({
      empty: true,
      reason: reviewedItems.length === 0 ? "no_content" : "exhausted",
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

type SchedulerPorts = {
  scheduler: {
    next: (
      subject: string,
      learnerId: string,
      servedIds?: readonly string[],
      servedSkillIds?: readonly string[],
    ) => Promise<{ skill_id: string; question_id: string }>;
  };
};

type EligibilityDb = {
  listAlreadyCorrectQuestionIds: (
    subject: string,
    learnerId: string,
  ) => Promise<string[]>;
};

/**
 * FR-E1/E1a/E3: prefer not-yet-correct items by extending excludeIds with the
 * FR-E4 already-correct projection; if that preferred pool is empty, fall back
 * to full-bank FSRS (servedIds only — today's scheduler behavior).
 */
async function pickAdaptive(
  ports: SchedulerPorts,
  db: EligibilityDb,
  subject: string,
  learnerId: string,
  servedIds: readonly string[],
  servedSkillIds: readonly string[],
): Promise<{ skill_id: string; question_id: string } | null> {
  const alreadyCorrect = await db.listAlreadyCorrectQuestionIds(
    subject,
    learnerId,
  );
  const preferredExclude = [...servedIds, ...alreadyCorrect];
  try {
    return await ports.scheduler.next(
      subject,
      learnerId,
      preferredExclude,
      servedSkillIds,
    );
  } catch (err) {
    if (!(err instanceof EngineNotFoundError)) throw err;
  }
  // FR-E3: not-yet-correct pool exhausted → normal FSRS over the full bank.
  try {
    return await ports.scheduler.next(
      subject,
      learnerId,
      servedIds,
      servedSkillIds,
    );
  } catch (err) {
    if (!(err instanceof EngineNotFoundError)) throw err;
    return null;
  }
}
