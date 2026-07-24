/**
 * GET /api/engine/summary — coarse hydration (T R.9 / §7 / FR-D1).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  getSession,
  engineGetSession,
  listSkillState,
  listMisses,
  listSessionQuestionIds,
  listSessionAttempts,
  skillTaxonomyList,
  questionRepoGet,
  engineDb,
  enginePorts,
} = vi.hoisted(() => {
  const engineGetSession = vi.fn();
  const listSkillState = vi.fn();
  const listMisses = vi.fn();
  const listSessionQuestionIds = vi.fn();
  const listSessionAttempts = vi.fn();
  const skillTaxonomyList = vi.fn();
  const questionRepoGet = vi.fn();
  return {
    getSession: vi.fn(),
    engineGetSession,
    listSkillState,
    listMisses,
    listSessionQuestionIds,
    listSessionAttempts,
    skillTaxonomyList,
    questionRepoGet,
    engineDb: vi.fn(() => ({
      getSession: engineGetSession,
      listSkillState,
      listMisses,
      listSessionQuestionIds,
      listSessionAttempts,
    })),
    enginePorts: vi.fn(() => ({
      skillTaxonomy: { list: skillTaxonomyList },
      questionRepo: { get: questionRepoGet },
    })),
  };
});

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession },
  }),
  engineDb,
  enginePorts,
}));

import { GET } from "./route";

function req(session?: string): NextRequest {
  const q = session === undefined ? "" : `?session=${session}`;
  return new NextRequest(`http://localhost/api/engine/summary${q}`);
}

const ownedSession = {
  id: "sess-1",
  subject: "act-english",
  learner_id: "learner-A",
  mode: "adaptive" as const,
  skill_focus: null,
  started_at: "2026-07-22T00:00:00.000Z",
  ended_at: "2026-07-22T01:00:00.000Z",
  score_correct: 1,
  score_total: 2,
  target_count: 30,
  current_question_id: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GET /api/engine/summary — T R.9 coarse hydration", () => {
  it("401 and never touches the DB without a WorkOS session", async () => {
    getSession.mockResolvedValue(null);
    const res = await GET(req("sess-1"));
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
    expect(enginePorts).not.toHaveBeenCalled();
  });

  it("400 when session query param is missing", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    const res = await GET(req());
    expect(res.status).toBe(400);
    expect(engineDb).not.toHaveBeenCalled();
  });

  it("404 when learner A guesses B's session", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    engineGetSession.mockResolvedValue({
      ...ownedSession,
      learner_id: "learner-B",
    });
    const res = await GET(req("sess-1"));
    expect(res.status).toBe(404);
    expect(listSessionAttempts).not.toHaveBeenCalled();
  });

  it("hydrates the coarse bag in one handler (each read once)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    engineGetSession.mockResolvedValue(ownedSession);

    const skills = [{ id: "s1", subject: "act-english", name: "Grammar" }];
    const skill_states = [
      { skill_id: "s1", learner_id: "learner-A", subject: "act-english" },
    ];
    const misses = [
      {
        question_id: "q-miss",
        learner_id: "learner-A",
        subject: "act-english",
      },
    ];
    const served_question_ids = ["q1", "q-miss"];
    const attempts = [
      {
        id: "a1",
        session_id: "sess-1",
        question_id: "q1",
        subject: "act-english",
      },
    ];
    const qMiss = { id: "q-miss", stem: "miss?" };
    const q1 = { id: "q1", stem: "one?" };

    skillTaxonomyList.mockResolvedValue(skills);
    listSkillState.mockResolvedValue(skill_states);
    listMisses.mockResolvedValue(misses);
    listSessionQuestionIds.mockResolvedValue(served_question_ids);
    listSessionAttempts.mockResolvedValue(attempts);
    questionRepoGet.mockImplementation(async (id: string) =>
      id === "q-miss" ? qMiss : id === "q1" ? q1 : null,
    );

    const res = await GET(req("sess-1"));
    expect(res.status).toBe(200);
    const body = await res.json();

    expect(body.session).toEqual(ownedSession);
    expect(body.skills).toEqual(skills);
    expect(body.skill_states).toEqual(skill_states);
    expect(body.misses).toEqual(misses);
    expect(body.served_question_ids).toEqual(served_question_ids);
    expect(body.attempts).toEqual(attempts);
    expect(body.miss_questions).toEqual(
      expect.arrayContaining([qMiss, q1]),
    );
    expect(body.questions).toEqual(body.miss_questions);

    expect(skillTaxonomyList).toHaveBeenCalledTimes(1);
    expect(skillTaxonomyList).toHaveBeenCalledWith("act-english");
    expect(listSkillState).toHaveBeenCalledTimes(1);
    expect(listMisses).toHaveBeenCalledTimes(1);
    expect(listSessionQuestionIds).toHaveBeenCalledTimes(1);
    expect(listSessionAttempts).toHaveBeenCalledTimes(1);
    expect(listSessionAttempts).toHaveBeenCalledWith("sess-1");
    // Unique ids from misses + served → two question fetches, not a fan-out of 6 screens.
    expect(questionRepoGet).toHaveBeenCalledTimes(2);
  });
});
