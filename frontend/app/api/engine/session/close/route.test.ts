/**
 * POST /api/engine/session/close — server tally + NULL pointer (T R.9 / FR-B10 / FR-B3c).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  getSession,
  engineGetSession,
  listSessionAttempts,
  setSessionCurrentQuestion,
  patchSessionClose,
  engineDb,
} = vi.hoisted(() => {
  const engineGetSession = vi.fn();
  const listSessionAttempts = vi.fn();
  const setSessionCurrentQuestion = vi.fn();
  const patchSessionClose = vi.fn();
  return {
    getSession: vi.fn(),
    engineGetSession,
    listSessionAttempts,
    setSessionCurrentQuestion,
    patchSessionClose,
    engineDb: vi.fn(() => ({
      getSession: engineGetSession,
      listSessionAttempts,
      setSessionCurrentQuestion,
      patchSessionClose,
    })),
  };
});

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession },
  }),
  engineDb,
}));

import { POST } from "./route";
import { commitFirstTally } from "@/lib/bff/engine_tally";

function req(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/engine/session/close", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "content-type": "application/json" },
  });
}

const ownedSession = {
  id: "sess-1",
  subject: "act-english",
  learner_id: "learner-A",
  mode: "adaptive" as const,
  skill_focus: null,
  started_at: "2026-07-22T00:00:00.000Z",
  ended_at: null,
  score_correct: 0,
  score_total: 0,
  target_count: 30,
  current_question_id: "q4",
};

const attempts = [
  {
    id: "a1",
    session_id: "sess-1",
    question_id: "q1",
    learner_id: "learner-A",
    subject: "act-english",
    skill_id: "s1",
    chosen_letter: "B",
    correct: true,
    used_hint: false,
    elapsed_ms: 100,
    created_at: "t1",
    resolution: "first_try" as const,
    idempotency_key: "k1",
  },
  {
    id: "a2",
    session_id: "sess-1",
    question_id: "q2",
    learner_id: "learner-A",
    subject: "act-english",
    skill_id: "s1",
    chosen_letter: "A",
    correct: false,
    used_hint: true,
    elapsed_ms: 200,
    created_at: "t2",
    resolution: "coached" as const,
    idempotency_key: "k2",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("POST /api/engine/session/close — T R.9 tally + NULL-on-close", () => {
  it("401 and never touches the DB without a WorkOS session", async () => {
    getSession.mockResolvedValue(null);
    const res = await POST(req({ session_id: "sess-1" }));
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
  });

  it("404 when learner A guesses B's session (no tally / close)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    engineGetSession.mockResolvedValue({
      ...ownedSession,
      learner_id: "learner-B",
    });
    const res = await POST(req({ session_id: "sess-1" }));
    expect(res.status).toBe(404);
    expect(listSessionAttempts).not.toHaveBeenCalled();
    expect(setSessionCurrentQuestion).not.toHaveBeenCalled();
    expect(patchSessionClose).not.toHaveBeenCalled();
  });

  it("clears current_question_id and closes with server commitFirstTally (ignores client scores)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    engineGetSession.mockResolvedValue(ownedSession);
    listSessionAttempts.mockResolvedValue(attempts);
    const expected = commitFirstTally(attempts);
    const closed = {
      ...ownedSession,
      ended_at: "2026-07-22T01:00:00.000Z",
      score_correct: expected.score_correct,
      score_total: expected.score_total,
      current_question_id: null,
    };
    patchSessionClose.mockResolvedValue(closed);

    const res = await POST(
      req({
        session_id: "sess-1",
        // Client lies — handler must ignore these (FR-B10).
        score_correct: 99,
        score_total: 99,
      }),
    );

    expect(res.status).toBe(200);
    expect(listSessionAttempts).toHaveBeenCalledWith("sess-1");
    // T R.12: the pointer clear is folded INTO patchSessionClose (one atomic
    // UPDATE), so the route no longer calls setSessionCurrentQuestion separately.
    expect(setSessionCurrentQuestion).not.toHaveBeenCalled();
    expect(patchSessionClose).toHaveBeenCalledTimes(1);
    const [, patch] = patchSessionClose.mock.calls[0]!;
    expect(patch).toMatchObject({
      score_correct: expected.score_correct,
      score_total: expected.score_total,
    });
    expect(patch.score_correct).toBe(1);
    expect(patch.score_total).toBe(2);
    expect(patch.ended_at).toEqual(expect.any(String));
    const body = await res.json();
    expect(body).toEqual(closed);
    // FR-B3c: the closed session's served pointer is NULL.
    expect(body.current_question_id).toBeNull();
  });

  it("409 and never closes when the session is already closed (T R.12 / FR-C2)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    engineGetSession.mockResolvedValue({
      ...ownedSession,
      ended_at: "2026-07-22T01:00:00.000Z", // already closed
    });
    const res = await POST(req({ session_id: "sess-1" }));
    expect(res.status).toBe(409);
    expect(listSessionAttempts).not.toHaveBeenCalled();
    expect(setSessionCurrentQuestion).not.toHaveBeenCalled();
    expect(patchSessionClose).not.toHaveBeenCalled();
  });
});
