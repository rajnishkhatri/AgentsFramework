/**
 * Shared authz helpers for `/api/engine/*` Route Handlers (coach-v3 FR-A1/A2/A2a).
 *
 * Handlers stay thin (F-R4/B6): claim → derive learnerId → optional ownership
 * check → one EngineDb call. Never trust a client-supplied learnerId.
 */

import { resolveLearnIdentity } from "../learn/resolve_learn_identity";
import type { IdentityClaim } from "../trust-view/identity";
import type { QuizSession } from "../wire/engine_entities";

/** Narrow session lookup — avoids importing the EngineDb adapter type into bff/. */
export type SessionLookup = {
  getSession(id: string): Promise<QuizSession | null>;
};

export function unauthorized(): Response {
  return new Response(JSON.stringify({ error: "unauthorized" }), {
    status: 401,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

export function notFound(): Response {
  return new Response(JSON.stringify({ error: "not_found" }), {
    status: 404,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

export function conflict(error = "session_closed"): Response {
  return new Response(JSON.stringify({ error }), {
    status: 409,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

export function badRequest(error = "invalid_body"): Response {
  return new Response(JSON.stringify({ error }), {
    status: 400,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

export function jsonOk(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

/**
 * Resolve the WorkOS session claim, treating retrieval failures as unauthenticated
 * (FR-A1 — never proceed to a DB call without a claim).
 */
export async function requireEngineClaim(
  getSession: () => Promise<IdentityClaim | null>,
): Promise<IdentityClaim | Response> {
  let claim: IdentityClaim | null = null;
  try {
    claim = await getSession();
  } catch {
    // Session retrieval failed — treat as unauthenticated.
  }
  if (!claim) return unauthorized();
  return claim;
}

/**
 * FR-A2: learnerId from the server-verified session only.
 * Uses `resolveLearnIdentity` so BFF and RSC share one mapping.
 */
export function learnerIdFromClaim(claim: IdentityClaim): string {
  return resolveLearnIdentity({
    bypass: false,
    user: { id: claim.sub },
  }).learnerId;
}

/**
 * FR-A2a — session-scoped ownership guard.
 * Loads the session, compares `learner_id` to the server-derived id, and
 * returns 404 on mismatch/absent *before* any dependent read/write runs.
 */
export async function requireOwnedSession(
  db: SessionLookup,
  sessionId: string,
  learnerId: string,
): Promise<
  | { ok: true; session: QuizSession }
  | { ok: false; response: Response }
> {
  const session = await db.getSession(sessionId);
  if (!session || session.learner_id !== learnerId) {
    return { ok: false, response: notFound() };
  }
  return { ok: true, session };
}

/**
 * T R.12 / FR-C2 — like `requireOwnedSession`, but additionally rejects with
 * 409 when the session is already closed (`ended_at != null`). Used by the
 * session-scoped write handlers (`attempt`, `session/current`, `session/close`)
 * so a late write after close can never re-open a completed session's counts.
 * The session row is already loaded by `requireOwnedSession` — no extra query.
 */
export async function requireOwnedOpenSession(
  db: SessionLookup,
  sessionId: string,
  learnerId: string,
): Promise<
  | { ok: true; session: QuizSession }
  | { ok: false; response: Response }
> {
  const owned = await requireOwnedSession(db, sessionId, learnerId);
  if (!owned.ok) return owned;
  if (owned.session.ended_at != null) {
    return { ok: false, response: conflict() };
  }
  return { ok: true, session: owned.session };
}
