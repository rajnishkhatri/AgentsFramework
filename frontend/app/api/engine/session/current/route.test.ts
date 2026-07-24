/**
 * POST /api/engine/session/current — served-pointer write (FR-B3a / FR-A2a).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  getSession,
  getSessionRow,
  setSessionCurrentQuestion,
  engineDb,
} = vi.hoisted(() => {
  const getSessionRow = vi.fn();
  const setSessionCurrentQuestion = vi.fn();
  return {
    getSession: vi.fn(),
    getSessionRow,
    setSessionCurrentQuestion,
    engineDb: vi.fn(() => ({
      getSession: getSessionRow,
      setSessionCurrentQuestion,
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

function req(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/engine/session/current", {
    method: "POST",
    body: typeof body === "string" ? body : JSON.stringify(body),
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  getSessionRow.mockResolvedValue({
    id: "sess-1",
    learner_id: "learner-A",
  });
  setSessionCurrentQuestion.mockResolvedValue(undefined);
});

describe("POST /api/engine/session/current — FR-A1 / FR-A2a / FR-B3a", () => {
  it("401 and never writes when there is no WorkOS session", async () => {
    getSession.mockResolvedValue(null);
    const res = await POST(
      req({ session_id: "sess-1", question_id: "q4" }),
    );
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
    expect(setSessionCurrentQuestion).not.toHaveBeenCalled();
  });

  it("404 and skips the pointer write when the session is not owned", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    getSessionRow.mockResolvedValue({
      id: "sess-1",
      learner_id: "learner-B",
    });
    const res = await POST(
      req({ session_id: "sess-1", question_id: "q4" }),
    );
    expect(res.status).toBe(404);
    expect(setSessionCurrentQuestion).not.toHaveBeenCalled();
  });

  it("writes current_question_id for the owned session (FR-B3a)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    const res = await POST(
      req({ session_id: "sess-1", question_id: "q4" }),
    );
    expect(res.status).toBe(200);
    expect(setSessionCurrentQuestion).toHaveBeenCalledWith("sess-1", "q4");
  });

  it("409 and never writes when the session is already closed (T R.12 / FR-C2)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    getSessionRow.mockResolvedValue({
      id: "sess-1",
      learner_id: "learner-A",
      ended_at: "2026-07-22T01:00:00.000Z", // already closed
    });
    const res = await POST(
      req({ session_id: "sess-1", question_id: "q4" }),
    );
    expect(res.status).toBe(409);
    expect(setSessionCurrentQuestion).not.toHaveBeenCalled();
  });
});
