/**
 * Coach session-marker write route (ADR-0012 Amendment; agent spec FR-19).
 *
 * Fire-and-forget target of the quiz submit path: records
 * `{user_id, question_id, submitted_at}` in the coach-session marker store,
 * flipping the coach's derived mode to post_feedback for that item —
 * monotonically (the repo has no unmark method).
 *
 * B6/F-R4 thin: auth-gate via the AuthProvider port, Zod-parse the body,
 * one port call. `user_id` is the SERVER-derived session subject (S3) — a
 * client-supplied user_id is ignored. No secrets, no business logic.
 *
 * Failure path first: no session → 401 and the store is never touched;
 * malformed body → 400 and the store is never touched.
 */

import { NextRequest } from "next/server";
import { z } from "zod";
import {
  coachMarkerRepo,
  serverPortBag,
} from "@/lib/bff/server_composition";

export const dynamic = "force-dynamic";

const MarkerWrite = z.object({ question_id: z.string().min(1) });

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
      headers: {
        "content-type": "application/json",
        "cache-control": "no-store",
      },
    });
  }

  let parsed: z.infer<typeof MarkerWrite>;
  try {
    parsed = MarkerWrite.parse(await req.json());
  } catch {
    return new Response(JSON.stringify({ error: "invalid_body" }), {
      status: 400,
      headers: {
        "content-type": "application/json",
        "cache-control": "no-store",
      },
    });
  }

  // Fire-and-forget (route header + marker_repo docstring): a marker WRITE is
  // best-effort. A store outage must NOT surface as a 500 — the write fails
  // CLOSED downstream (isSubmitted returns false on any read error, so the
  // coach derives pre_submit and never leaks answer fields). Swallow the throw
  // and still 204; the caller does not retry a marker.
  try {
    await coachMarkerRepo().markSubmitted(claim.sub, parsed.question_id);
  } catch {
    // best-effort: a missed marker degrades to pre_submit, never a 500.
  }
  return new Response(null, { status: 204 });
}
