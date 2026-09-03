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
  insertExamRun,
  listExamRunsByLearner,
  getExamRun,
  beginExamSection,
  upsertExamRunItems,
  finishExamSection,
  setExamRunComposite,
  setExamBookmark,
  listExamRunItemsByLearner,
  getExamFormForClient,
  getExamFormKeys,
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
  const insertExamRun = vi.fn();
  const listExamRunsByLearner = vi.fn();
  const getExamRun = vi.fn();
  const beginExamSection = vi.fn();
  const upsertExamRunItems = vi.fn();
  const finishExamSection = vi.fn();
  const setExamRunComposite = vi.fn();
  const setExamBookmark = vi.fn();
  const listExamRunItemsByLearner = vi.fn();
  const getExamFormForClient = vi.fn();
  const getExamFormKeys = vi.fn();
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
    insertExamRun,
    listExamRunsByLearner,
    getExamRun,
    beginExamSection,
    upsertExamRunItems,
    finishExamSection,
    setExamRunComposite,
    setExamBookmark,
    listExamRunItemsByLearner,
    getExamFormForClient,
    getExamFormKeys,
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
      insertExamRun,
      listExamRunsByLearner,
      getExamRun,
      beginExamSection,
      upsertExamRunItems,
      finishExamSection,
      setExamRunComposite,
      setExamBookmark,
      listExamRunItemsByLearner,
      getExamFormForClient,
      getExamFormKeys,
    })),
  };
});

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession: getAuthSession },
  }),
  engineDb,
  enginePorts: () => ({ grader: { grade: () => null } }),
}));

import { EXAM_ENGINE_DB_METHODS } from "@/lib/adapters/engine/db/dispatcher_learner_arg";
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

  it("404 for getExamFormKeys (server-only; never dispatched)", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    const res = await POST(req("getExamFormKeys", ["test01-english"]), {
      params: Promise.resolve({ method: "getExamFormKeys" }),
    });
    expect(res.status).toBe(404);
    expect(getExamFormKeys).not.toHaveBeenCalled();
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

  it("forces insertExamRun arg0 learnerId from the authenticated claim (W1-3)", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    insertExamRun.mockResolvedValue(undefined);
    const run = {
      id: "run-1",
      learner_id: "learner-B",
      form_id: "test01",
      created_at: "2026-09-02T00:00:00.000Z",
      composite: null,
    };

    const res = await POST(req("insertExamRun", ["learner-B", run]), {
      params: Promise.resolve({ method: "insertExamRun" }),
    });

    expect(res.status).toBe(204);
    expect(insertExamRun).toHaveBeenCalledWith("learner-A", run);
  });
});

const EXAM_STARTED = "2026-09-02T00:00:00.000Z";
const EXAM_DEADLINE = "2026-09-02T00:45:00.000Z";
const EXAM_GRADES = {
  raw_correct: 0,
  raw_scored_total: 1,
  scale_score: null,
};

/** Run-scoped exam methods (arg1 = runId). FR-3 / W1-6. */
const EXAM_RUN_SCOPED: Array<
  [string, unknown[], ReturnType<typeof vi.fn>]
> = [
  ["getExamRun", ["learner-B", "run-B"], getExamRun],
  [
    "beginExamSection",
    ["learner-B", "run-B", "english", EXAM_STARTED, EXAM_DEADLINE],
    beginExamSection,
  ],
  ["upsertExamRunItems", ["learner-B", "run-B", "english", []], upsertExamRunItems],
  [
    "finishExamSection",
    ["learner-B", "run-B", "english", "submitted", EXAM_GRADES, 0],
    finishExamSection,
  ],
  ["setExamRunComposite", ["learner-B", "run-B", null], setExamRunComposite],
  ["setExamBookmark", ["learner-B", "run-B", "english", "q1", true], setExamBookmark],
];

const EXAM_LEARNER_ONLY: Array<
  [string, unknown[], ReturnType<typeof vi.fn>]
> = [
  ["insertExamRun", ["learner-B", { id: "run-new" }], insertExamRun],
  ["listExamRunsByLearner", ["learner-B"], listExamRunsByLearner],
  ["listExamRunItemsByLearner", ["learner-B"], listExamRunItemsByLearner],
  ["getExamFormForClient", ["learner-B", "test01-english"], getExamFormForClient],
];

describe("POST /api/engine/db/[method] exam (W1-6 / FR-3)", () => {
  it("covers every exam EngineDb method (run-scoped 404 or learner-arg force)", () => {
    const covered = [
      ...EXAM_RUN_SCOPED.map(([method]) => method),
      ...EXAM_LEARNER_ONLY.map(([method]) => method),
    ].sort();
    expect(covered).toEqual([...EXAM_ENGINE_DB_METHODS].sort());
  });

  it.each(EXAM_RUN_SCOPED)(
    "returns 404 before dispatching foreign-learner exam %s",
    async (method, args, dependentMethod) => {
      getAuthSession.mockResolvedValue({ sub: "learner-A" });
      getExamRun.mockResolvedValue(null);

      const res = await POST(req(method, args), {
        params: Promise.resolve({ method }),
      });

      expect(res.status).toBe(404);
      expect(getExamRun).toHaveBeenCalledWith("learner-A", "run-B");
      if (method === "getExamRun") {
        expect(getExamRun).toHaveBeenCalledTimes(1);
      } else {
        expect(dependentMethod).not.toHaveBeenCalled();
      }
    },
  );

  it.each(EXAM_LEARNER_ONLY)(
    "forces %s arg0 learnerId from the authenticated claim",
    async (method, args, dependentMethod) => {
      getAuthSession.mockResolvedValue({ sub: "learner-A" });
      dependentMethod.mockResolvedValue(method === "insertExamRun" ? undefined : []);

      const res = await POST(req(method, args), {
        params: Promise.resolve({ method }),
      });

      expect(res.status).toBe(method === "insertExamRun" ? 204 : 200);
      expect(dependentMethod.mock.calls[0]![0]).toBe("learner-A");
    },
  );
});
