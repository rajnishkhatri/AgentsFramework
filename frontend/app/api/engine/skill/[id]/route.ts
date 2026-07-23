/**
 * GET /api/engine/skill/[id] — coarse read (5+N+1→1) for use_skill_detail (T A.9).
 */

import { NextRequest } from "next/server";
import { engineDb, enginePorts, serverPortBag } from "@/lib/bff/server_composition";
import {
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
} from "@/lib/bff/engine_guard";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  const { id: skillId } = await ctx.params;
  const subject =
    req.nextUrl.searchParams.get("subject")?.trim() || DEFAULT_SUBJECT;
  const sessions = Number(req.nextUrl.searchParams.get("sessions") ?? "5");
  const db = engineDb();
  const ports = enginePorts();

  const [skills, tutorial, skill_states, misses, accuracy_rows] =
    await Promise.all([
      ports.skillTaxonomy.list(subject),
      ports.tutorialRepo.getTutorial(subject, skillId),
      db.listSkillState(subject, learnerId),
      db.listMisses(subject, learnerId),
      db.accuracyRowsBySkill(subject, learnerId, skillId, sessions),
    ]);

  const skill = skills.find((s) => s.id === skillId) ?? null;
  const missIds = [...new Set(misses.map((m) => m.question_id))];
  const miss_questions = (
    await Promise.all(missIds.map((id) => ports.questionRepo.get(id)))
  ).filter((q): q is NonNullable<typeof q> => q != null);

  return jsonOk({
    skill,
    skills,
    tutorial,
    skill_states,
    misses,
    accuracy_rows,
    miss_questions,
  });
}
