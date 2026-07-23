/**
 * GET /api/engine/dashboard — coarse read (5→1) for use_dashboard (T A.9).
 */

import { NextRequest } from "next/server";
import { engineDb, enginePorts, serverPortBag } from "@/lib/bff/server_composition";
import {
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
} from "@/lib/bff/engine_guard";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";
import { pickFocusSkillId } from "@/lib/translators/focus_pick";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  const subject =
    req.nextUrl.searchParams.get("subject")?.trim() || DEFAULT_SUBJECT;
  const sinceISO = req.nextUrl.searchParams.get("since") ?? undefined;
  const nowISO =
    req.nextUrl.searchParams.get("now")?.trim() || new Date().toISOString();
  const db = engineDb();
  const ports = enginePorts();

  const [skills, skill_states, misses, sessions] = await Promise.all([
    ports.skillTaxonomy.list(subject),
    db.listSkillState(subject, learnerId),
    db.listMisses(subject, learnerId),
    db.listClosedSessionsByLearner(
      subject,
      learnerId,
      sinceISO ? { sinceISO } : undefined,
    ),
  ]);

  const focusSkillId = pickFocusSkillId(skill_states, nowISO);
  const focus_question =
    focusSkillId == null
      ? null
      : await ports.questionRepo.nextReviewed(subject, focusSkillId);

  return jsonOk({
    skills,
    skill_states,
    misses,
    sessions,
    focus_skill_id: focusSkillId,
    focus_question,
    review_misses_count: new Set(misses.map((m) => m.question_id)).size,
  });
}
