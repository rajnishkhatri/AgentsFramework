/**
 * POST /api/engine/attempt — auth + ownership + idempotent return (T A.12).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const { getSession, engineGetSession, insertAttempt, engineDb } = vi.hoisted(
  () => {
    const engineGetSession = vi.fn();
    const insertAttempt = vi.fn();
    return {
      getSession: vi.fn(),
      engineGetSession,
      insertAttempt,
      engineDb: vi.fn(() => ({
        getSession: engineGetSession,
        insertAttempt,
      })),
    };
  },
);

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession },
  }),
  engineDb,
}));

import { POST } from "./route";

function req(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/engine/attempt", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "content-type": "application/json" },
  });
}

const baseBody = {
  subject: "act-english",
  session_id: "sess-1",
  question_id: "q1",
  chosen_letter: "A",
  correct: true,
  elapsed_ms: 10,
  used_hint: false,
  idempotency_key: "idem-1",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("POST /api/engine/attempt", () => {
  it("401 and no DB when unauthenticated", async () => {
    getSession.mockResolvedValue(null);
    const res = await POST(req(baseBody));
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
  });

  it("404 when learner A guesses B's session (no insert)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    engineGetSession.mockResolvedValue({
      id: "sess-1",
      learner_id: "learner-B",
      subject: "act-english",
      mode: "adaptive",
      skill_focus: null,
      started_at: "t",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: 30,
    });
    const res = await POST(req(baseBody));
    expect(res.status).toBe(404);
    expect(insertAttempt).not.toHaveBeenCalled();
  });

  it("returns stored attempt for already-existed (idempotent 200)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    engineGetSession.mockResolvedValue({
      id: "sess-1",
      learner_id: "learner-A",
      subject: "act-english",
      mode: "adaptive",
      skill_focus: null,
      started_at: "t",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: 30,
    });
    const stored = {
      id: "a-existing",
      ...baseBody,
      created_at: "2026-07-22T00:00:00.000Z",
    };
    insertAttempt.mockResolvedValue({
      status: "already-existed",
      attempt: stored,
    });
    const res = await POST(req(baseBody));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(stored);
  });
});
