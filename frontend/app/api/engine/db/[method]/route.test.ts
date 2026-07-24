/**
 * Fine-grained /api/engine/db/<method> — auth + server-only 404 (T A.10).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  getAuthSession,
  getDbSession,
  listSkills,
  insertQuestion,
  insertSession,
  insertAttempt,
  patchSessionClose,
  setSessionCurrentQuestion,
  listSessionQuestionIds,
  listSessionAttempts,
  listSessionSkillIds,
  upsertSkillState,
  engineDb,
} = vi.hoisted(() => {
  const listSkills = vi.fn();
  const insertQuestion = vi.fn();
  const getDbSession = vi.fn();
  const insertSession = vi.fn();
  const insertAttempt = vi.fn();
  const patchSessionClose = vi.fn();
  const setSessionCurrentQuestion = vi.fn();
  const listSessionQuestionIds = vi.fn();
  const listSessionAttempts = vi.fn();
  const listSessionSkillIds = vi.fn();
  const upsertSkillState = vi.fn();
  return {
    getAuthSession: vi.fn(),
    getDbSession,
    listSkills,
    insertQuestion,
    insertSession,
    insertAttempt,
    patchSessionClose,
    setSessionCurrentQuestion,
    listSessionQuestionIds,
    listSessionAttempts,
    listSessionSkillIds,
    upsertSkillState,
    engineDb: vi.fn(() => ({
      listSkills,
      insertQuestion,
      insertSession,
      getSession: getDbSession,
      insertAttempt,
      patchSessionClose,
      setSessionCurrentQuestion,
      listSessionQuestionIds,
      listSessionAttempts,
      listSessionSkillIds,
      upsertSkillState,
    })),
  };
});

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession: getAuthSession },
  }),
  engineDb,
}));

import { POST } from "./route";

function req(method: string, args: unknown[]): NextRequest {
  return new NextRequest(`http://localhost/api/engine/db/${method}`, {
    method: "POST",
    body: JSON.stringify({ args }),
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("POST /api/engine/db/[method]", () => {
  it("401 and no DB when unauthenticated", async () => {
    getAuthSession.mockResolvedValue(null);
    const res = await POST(req("listSkills", ["act-english"]), {
      params: Promise.resolve({ method: "listSkills" }),
    });
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
  });

  it("404 for server-only content writes (no handler surface)", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    const res = await POST(req("insertQuestion", [{}]), {
      params: Promise.resolve({ method: "insertQuestion" }),
    });
    expect(res.status).toBe(404);
    expect(insertQuestion).not.toHaveBeenCalled();
  });

  it("dispatches a fine-grained read", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    listSkills.mockResolvedValue([]);
    const res = await POST(req("listSkills", ["act-english"]), {
      params: Promise.resolve({ method: "listSkills" }),
    });
    expect(res.status).toBe(200);
    expect(listSkills).toHaveBeenCalledWith("act-english");
  });

  it.each([
    ["getSession", ["session-B"], getDbSession],
    [
      "patchSessionClose",
      [
        "session-B",
        {
          ended_at: "2026-07-23T00:00:00.000Z",
          score_correct: 1,
          score_total: 1,
        },
      ],
      patchSessionClose,
    ],
    [
      "setSessionCurrentQuestion",
      ["session-B", "question-1"],
      setSessionCurrentQuestion,
    ],
    ["listSessionQuestionIds", ["session-B"], listSessionQuestionIds],
    ["listSessionAttempts", ["session-B"], listSessionAttempts],
    ["listSessionSkillIds", ["session-B"], listSessionSkillIds],
    [
      "insertAttempt",
      [{ session_id: "session-B", question_id: "question-1" }],
      insertAttempt,
    ],
  ])(
    "returns 404 before dispatching cross-learner %s",
    async (method, args, dependentMethod) => {
      getAuthSession.mockResolvedValue({ sub: "learner-A" });
      getDbSession.mockResolvedValue({
        id: "session-B",
        learner_id: "learner-B",
      });

      const res = await POST(req(method, args), {
        params: Promise.resolve({ method }),
      });

      expect(res.status).toBe(404);
      expect(getDbSession).toHaveBeenCalledWith("session-B");
      if (method === "getSession") {
        expect(getDbSession).toHaveBeenCalledTimes(1);
      } else {
        expect(dependentMethod).not.toHaveBeenCalled();
      }
    },
  );

  it("forces insertSession learner_id from the authenticated claim", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    insertSession.mockResolvedValue(undefined);
    const supplied = {
      id: "session-1",
      subject: "act-english",
      learner_id: "learner-B",
    };

    const res = await POST(req("insertSession", [supplied]), {
      params: Promise.resolve({ method: "insertSession" }),
    });

    expect(res.status).toBe(204);
    expect(insertSession).toHaveBeenCalledWith({
      ...supplied,
      learner_id: "learner-A",
    });
  });

  it("forces upsertSkillState learner_id from the authenticated claim", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    upsertSkillState.mockResolvedValue(undefined);
    const supplied = {
      subject: "act-english",
      skill_id: "skill-1",
      learner_id: "learner-B",
    };

    const res = await POST(req("upsertSkillState", [supplied]), {
      params: Promise.resolve({ method: "upsertSkillState" }),
    });

    expect(res.status).toBe(204);
    expect(upsertSkillState).toHaveBeenCalledWith({
      ...supplied,
      learner_id: "learner-A",
    });
  });
});
