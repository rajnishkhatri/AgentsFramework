/**
 * POST /api/engine/session/open — open a new quiz session (coach-v3 §5).
 *
 * Thin (F-R4/B6): WorkOS gate (FR-A1) → server-derived learnerId (FR-A2) →
 * `insertSession`. Client-supplied learnerId / learner_id is ignored.
 */

import { NextRequest } from "next/server";
import { z } from "zod";
import { engineDb, serverPortBag } from "@/lib/bff/server_composition";
import {
  badRequest,
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
} from "@/lib/bff/engine_guard";
import { SessionMode, type QuizSession } from "@/lib/wire/engine_entities";
import { newUuid } from "@/lib/new_uuid";

export const dynamic = "force-dynamic";

const OpenBody = z.object({
  subject: z.string().min(1),
  mode: SessionMode,
  skill_focus: z.string().nullable().optional(),
  target_count: z.number().int().positive().nullable().optional(),
});

const DEFAULT_TARGET_COUNT = 30;

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  let parsed: z.infer<typeof OpenBody>;
  try {
    parsed = OpenBody.parse(await req.json());
  } catch {
    return badRequest();
  }

  const row: QuizSession = {
    id: newUuid(),
    subject: parsed.subject,
    learner_id: learnerId,
    mode: parsed.mode,
    skill_focus: parsed.skill_focus ?? null,
    started_at: new Date().toISOString(),
    ended_at: null,
    score_correct: 0,
    score_total: 0,
    target_count:
      parsed.target_count === undefined
        ? DEFAULT_TARGET_COUNT
        : parsed.target_count,
    current_question_id: null,
  };

  await engineDb().insertSession(row);
  return jsonOk(row);
}
