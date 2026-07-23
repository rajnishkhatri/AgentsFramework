/**
 * Fine-grained EngineDb dispatch — POST /api/engine/db/<method> (FR-A4 / T A.10).
 *
 * Body: `{ args: unknown[] }`. Server-only content writes → 404 (no authenticated
 * learner may mutate the bank). Learner-keyed methods ignore any learnerId in
 * args and substitute the session-derived id (FR-A2).
 */

import { NextRequest } from "next/server";
import { engineDb, serverPortBag } from "@/lib/bff/server_composition";
import {
  badRequest,
  jsonOk,
  learnerIdFromClaim,
  notFound,
  requireEngineClaim,
} from "@/lib/bff/engine_guard";
import {
  ENGINE_DB_DISPOSITION,
  type EngineDbMethodName,
} from "@/lib/adapters/engine/db/engine_db_disposition";
import type { EngineDb } from "@/lib/adapters/engine/db/engine_db";

export const dynamic = "force-dynamic";

/** Methods whose last-or-specific arg is a learnerId the client must not choose. */
const LEARNER_ARG: Partial<Record<EngineDbMethodName, number>> = {
  listSkillState: 1,
  listClosedSessionsByLearner: 1,
  getNewestOpenSession: 1,
  listMisses: 1,
  accuracyRowsBySkill: 1,
  getSkillState: 2,
  listProgressPoints: 1,
};

function isMethodName(value: string): value is EngineDbMethodName {
  return Object.prototype.hasOwnProperty.call(ENGINE_DB_DISPOSITION, value);
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ method: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() => bag.authProvider.getSession());
  if (claimOrRes instanceof Response) return claimOrRes;
  const learnerId = learnerIdFromClaim(claimOrRes);

  const { method: raw } = await ctx.params;
  if (!isMethodName(raw)) return notFound();
  if (ENGINE_DB_DISPOSITION[raw] === "server-only") return notFound();

  let args: unknown[];
  try {
    const body = (await req.json()) as { args?: unknown };
    if (!Array.isArray(body.args)) return badRequest();
    args = body.args;
  } catch {
    return badRequest();
  }

  const learnerIdx = LEARNER_ARG[raw];
  if (learnerIdx !== undefined) {
    args = [...args];
    args[learnerIdx] = learnerId;
  }

  const db = engineDb();
  const fn = db[raw] as (...a: unknown[]) => Promise<unknown>;
  const result = await fn.apply(db, args);
  if (result === undefined) {
    return new Response(null, {
      status: 204,
      headers: { "cache-control": "no-store" },
    });
  }
  return jsonOk(result);
}
