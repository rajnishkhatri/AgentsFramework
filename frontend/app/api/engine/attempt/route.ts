/**
 * POST /api/engine/attempt — thin idempotent insert (FR-A9.1 / T A.8, A.12).
 * Returns the stored Attempt whether inserted or already-existed.
 */

import { NextRequest } from "next/server";
import { z } from "zod";
import { engineDb, serverPortBag } from "@/lib/bff/server_composition";
import {
  badRequest,
  jsonOk,
  learnerIdFromClaim,
  requireEngineClaim,
  requireOwnedOpenSession,
} from "@/lib/bff/engine_guard";
import { Attempt, AttemptInput } from "@/lib/wire/engine_entities";
import { newUuid } from "@/lib/new_uuid";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  let input: z.infer<typeof AttemptInput>;
  try {
    input = AttemptInput.parse(await req.json());
  } catch {
    return badRequest();
  }

  const db = engineDb();
  const owned = await requireOwnedOpenSession(db, input.session_id, learnerId);
  if (!owned.ok) return owned.response;

  const row = Attempt.parse({
    ...input,
    id: newUuid(),
    created_at: new Date().toISOString(),
  });
  const result = await db.insertAttempt(row);
  return jsonOk(result.attempt);
}
