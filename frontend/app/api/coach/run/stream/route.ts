/**
 * Coach SSE streaming proxy (Phase 2.1, FR-F / §5).
 *
 * The coach rides the CHAT runtime (plan OD-3 / design §7 divergence #1) — there
 * is no separate coach engine port — so this Route Handler is the same thin BFF
 * seam as /api/run/stream (B6, FE-AP-3): authenticate via the AuthProvider port,
 * forward to the middleware, pipe the bytes through `proxySSE` (X6 headers).
 *
 * It is a separate route only so the coach client streams from its own base
 * (`/api/coach/run/stream`), keeping the coach thread + persona selection
 * distinct from chat while reusing every transport invariant. The coach
 * `agent_id` (subject-coach-english) rides in the client request body; this
 * route adds no business logic and holds no cloud credentials (F-R9) — it
 * forwards the WorkOS access token as `Authorization: Bearer` and nothing else.
 */

import { NextRequest } from "next/server";
import { proxySSE } from "@/lib/transport/edge_proxy";
import {
  coachMarkerRepo,
  forwardToMiddleware,
  serverPortBag,
} from "@/lib/bff/server_composition";
import {
  deriveCoachMode,
  sanitizeCoachRunBody,
} from "@/lib/translators/coach_context_sanitizer";

export const dynamic = "force-dynamic";

/**
 * Pull `input.coach_context.question_id` out of the raw body, or null when
 * this is a plain chat run (no coach_context) or the body is unparseable —
 * both of which forward byte-identical.
 */
function extractCoachQuestionId(rawBody: string): string | null {
  try {
    const parsed = JSON.parse(rawBody) as {
      input?: { coach_context?: { question_id?: unknown } };
    };
    const qid = parsed?.input?.coach_context?.question_id;
    return typeof qid === "string" && qid.length > 0 ? qid : null;
  } catch {
    return null;
  }
}

export async function POST(req: NextRequest): Promise<Response> {
  const bag = serverPortBag();
  let claim = null;
  try {
    claim = await bag.authProvider.getSession();
  } catch {
    // Session retrieval failed — treat as unauthenticated.
  }

  if (!claim) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  }
  const token = await bag.authProvider.getAccessToken();
  let body = await req.text();

  // ADR-0012 Amendment (FR-19/FR-21): derive the AUTHORITATIVE mode from the
  // coach-session marker store (server-side session subject — client mode is
  // advisory) and strip the four answer-bearing Question fields pre-submit.
  // Pure decision logic lives in the sanitizer translator; this block is the
  // port-call wiring (B6). Chat bodies without a coach_context pass through
  // byte-identical. Any failure fails CLOSED to pre_submit.
  const questionId = extractCoachQuestionId(body);
  if (questionId !== null) {
    let hasSubmittedMarker = false;
    try {
      hasSubmittedMarker = await coachMarkerRepo().isSubmitted(
        claim.sub,
        questionId,
      );
    } catch {
      // Unreadable store ⇒ pre_submit (fields stripped) — never leak.
    }
    const mode = deriveCoachMode({ hasSubmittedMarker });
    body = JSON.stringify(sanitizeCoachRunBody(JSON.parse(body), mode));
  }

  const upstream = await forwardToMiddleware("/run/stream", {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
      accept: "text/event-stream",
    },
    body,
  });
  return proxySSE(upstream);
}
