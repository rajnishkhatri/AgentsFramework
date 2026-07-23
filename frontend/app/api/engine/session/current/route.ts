/**
 * POST /api/engine/session/current — write served pointer (FR-B3a / T A.8).
 * The only serve-pointer writer.
 */

import { NextRequest } from "next/server";
import { z } from "zod";
import { engineDb, serverPortBag } from "@/lib/bff/server_composition";
import {
  badRequest,
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
  requireOwnedSession,
} from "@/lib/bff/engine_guard";

export const dynamic = "force-dynamic";

const Body = z.object({
  session_id: z.string().min(1),
  question_id: z.string().nullable(),
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
  const owned = await requireOwnedSession(db, parsed.session_id, learnerId);
  if (!owned.ok) return owned.response;

  await db.setSessionCurrentQuestion(parsed.session_id, parsed.question_id);
  return jsonOk({ ok: true });
}
