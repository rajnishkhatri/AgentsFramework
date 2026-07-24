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
  requireOwnedSession,
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

/** Methods whose object arg embeds a learner id the client must not choose. */
const LEARNER_FIELD_ARG: Partial<Record<EngineDbMethodName, number>> = {
  insertSession: 0,
  upsertSkillState: 0,
};

/** Session-scoped methods whose session id is a positional argument. */
const SESSION_ARG: Partial<Record<EngineDbMethodName, number>> = {
  getSession: 0,
  patchSessionClose: 0,
  setSessionCurrentQuestion: 0,
  listSessionQuestionIds: 0,
  listSessionAttempts: 0,
  listSessionSkillIds: 0,
};

/** Session-scoped methods whose object arg embeds the session id. */
const SESSION_FIELD_ARG: Partial<Record<EngineDbMethodName, number>> = {
  insertAttempt: 0,
};

function isMethodName(value: string): value is EngineDbMethodName {
  return Object.prototype.hasOwnProperty.call(ENGINE_DB_DISPOSITION, value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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

  const learnerFieldIdx = LEARNER_FIELD_ARG[raw];
  if (learnerFieldIdx !== undefined) {
    const value = args[learnerFieldIdx];
    if (!isRecord(value)) return badRequest();
    args = [...args];
    args[learnerFieldIdx] = { ...value, learner_id: learnerId };
  }

  const db = engineDb();

  const sessionIdx = SESSION_ARG[raw];
  const sessionFieldIdx = SESSION_FIELD_ARG[raw];
  let sessionId: unknown;
  if (sessionIdx !== undefined) {
    sessionId = args[sessionIdx];
  } else if (sessionFieldIdx !== undefined) {
    const value = args[sessionFieldIdx];
    if (!isRecord(value)) return badRequest();
    sessionId = value.session_id;
  }
  if (sessionIdx !== undefined || sessionFieldIdx !== undefined) {
    if (typeof sessionId !== "string" || sessionId.length === 0) {
      return badRequest();
    }
    const owned = await requireOwnedSession(db, sessionId, learnerId);
    if (!owned.ok) return owned.response;
  }

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
