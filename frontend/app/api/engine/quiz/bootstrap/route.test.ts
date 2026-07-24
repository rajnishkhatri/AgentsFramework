/**
 * GET /api/engine/quiz/bootstrap — ownership guard (FR-A2a / T A.3).
 *
 * Learner A guessing B's session id → 404, and no dependent read runs after
 * the ownership check (spy: getQuestion / listReviewedHints never called).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const { getSession, engineGetSession, getQuestion, listReviewedHints, engineDb } =
  vi.hoisted(() => {
    const engineGetSession = vi.fn();
    const getQuestion = vi.fn();
    const listReviewedHints = vi.fn();
    return {
      getSession: vi.fn(),
      engineGetSession,
      getQuestion,
      listReviewedHints,
      engineDb: vi.fn(() => ({
        getSession: engineGetSession,
        getQuestion,
        listReviewedHints,
      })),
    };
  });

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession },
  }),
  engineDb,
}));

import { GET } from "./route";

function req(sessionId: string): NextRequest {
  return new NextRequest(
    `http://localhost/api/engine/quiz/bootstrap?session=${encodeURIComponent(sessionId)}`,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GET /api/engine/quiz/bootstrap — FR-A1 / FR-A2a", () => {
  it("401 and no DB when unauthenticated", async () => {
    getSession.mockResolvedValue(null);
    const res = await GET(req("sess-b"));
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
  });

  it("404 and no dependent read when learner A guesses B's session", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    engineGetSession.mockResolvedValue({
      id: "sess-b",
      subject: "act-english",
      learner_id: "learner-B",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-07-22T00:00:00.000Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: 30,
      current_question_id: "q-1",
    });
    const res = await GET(req("sess-b"));
    expect(res.status).toBe(404);
    expect(engineGetSession).toHaveBeenCalledWith("sess-b");
    expect(getQuestion).not.toHaveBeenCalled();
    expect(listReviewedHints).not.toHaveBeenCalled();
  });
});
