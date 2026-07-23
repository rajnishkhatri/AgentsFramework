/**
 * POST /api/engine/skill-state — upsertSkillState (T A.8).
 * Forces learner_id from the session (FR-A2).
 */

import { NextRequest } from "next/server";
import { engineDb, serverPortBag } from "@/lib/bff/server_composition";
import {
  badRequest,
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
} from "@/lib/bff/engine_guard";
import { SkillState } from "@/lib/wire/engine_entities";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  let parsed: ReturnType<typeof SkillState.parse>;
  try {
    parsed = SkillState.parse(await req.json());
  } catch {
    return badRequest();
  }

  const state = { ...parsed, learner_id: learnerId };
  await engineDb().upsertSkillState(state);
  return jsonOk(state);
}
