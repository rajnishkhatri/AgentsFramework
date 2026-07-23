/**
 * GET /api/engine/session/active — newest open + pointer + commit-first tally.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  getSession,
  getNewestOpenSession,
  listSessionAttempts,
  engineDb,
} = vi.hoisted(() => {
  const getNewestOpenSession = vi.fn();
  const listSessionAttempts = vi.fn();
  return {
    getSession: vi.fn(),
    getNewestOpenSession,
    listSessionAttempts,
    engineDb: vi.fn(() => ({ getNewestOpenSession, listSessionAttempts })),
  };
});

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession },
  }),
  engineDb,
}));

import { GET } from "./route";

function req(subject = "act-english"): NextRequest {
  return new NextRequest(
    `http://localhost/api/engine/session/active?subject=${subject}`,
  );
}

const openSession = {
  id: "sess-open",
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

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GET /api/engine/session/active — FR-A1 / FR-B2 / FR-B10", () => {
  it("401 and never touches the DB without a WorkOS session", async () => {
    getSession.mockResolvedValue(null);
    const res = await GET(req());
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
  });

  it("returns null session when there is no open row (FR-B7 completed skipped)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    getNewestOpenSession.mockResolvedValue(null);
    const res = await GET(req());
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      session: null,
      running_score: null,
      pointer_attempted: false,
    });
    expect(getNewestOpenSession).toHaveBeenCalledWith(
      "act-english",
      "learner-A",
    );
    expect(listSessionAttempts).not.toHaveBeenCalled();
  });

  it("returns pointer + commit-first tally and whether the pointer has any attempt (FR-B3/B5/B10)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    getNewestOpenSession.mockResolvedValue(openSession);
    listSessionAttempts.mockResolvedValue([
      {
        id: "a1",
        session_id: "sess-open",
        question_id: "q1",
        learner_id: "learner-A",
        subject: "act-english",
        skill_id: "s1",
        chosen_letter: "B",
        correct: true,
        used_hint: false,
        elapsed_ms: 100,
        created_at: "t1",
        resolution: "first_try",
        idempotency_key: "k1",
      },
      {
        id: "a2",
        session_id: "sess-open",
        question_id: "q4",
        learner_id: "learner-A",
        subject: "act-english",
        skill_id: "s1",
        chosen_letter: "A",
        correct: false,
        used_hint: false,
        elapsed_ms: 100,
        created_at: "t2",
        resolution: null,
        idempotency_key: "k2",
      },
    ]);

    const res = await GET(req());
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.session.id).toBe("sess-open");
    expect(body.session.current_question_id).toBe("q4");
    // unique first_try / unique resolved → q1 only contributes to numerator;
    // q4 is non-resolving so denominator stays 1.
    expect(body.running_score).toEqual({ score_correct: 1, score_total: 1 });
    expect(body.pointer_attempted).toBe(true);
  });

  it("pointer_attempted is false when the served question has zero attempts", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    getNewestOpenSession.mockResolvedValue(openSession);
    listSessionAttempts.mockResolvedValue([
      {
        id: "a1",
        session_id: "sess-open",
        question_id: "q1",
        learner_id: "learner-A",
        subject: "act-english",
        skill_id: "s1",
        chosen_letter: "B",
        correct: true,
        used_hint: false,
        elapsed_ms: 100,
        created_at: "t1",
        resolution: "first_try",
        idempotency_key: "k1",
      },
    ]);

    const res = await GET(req());
    const body = await res.json();
    expect(body.pointer_attempted).toBe(false);
    expect(body.running_score).toEqual({ score_correct: 1, score_total: 1 });
  });
});
