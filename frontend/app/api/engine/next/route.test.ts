/**
 * GET /api/engine/next — distinguish an empty bank (FR-G3) from a finite
 * session pool that has been exhausted (FR-C5).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  getAuthSession: vi.fn(),
  getSession: vi.fn(),
  listSessionQuestionIds: vi.fn(),
  listSessionSkillIds: vi.fn(),
  listReviewedTestItems: vi.fn(),
  nextReviewed: vi.fn(),
  schedulerNext: vi.fn(),
  questionGet: vi.fn(),
  hintList: vi.fn(),
}));

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession: mocks.getAuthSession },
  }),
  engineDb: () => ({
    getSession: mocks.getSession,
    listSessionQuestionIds: mocks.listSessionQuestionIds,
    listSessionSkillIds: mocks.listSessionSkillIds,
    listReviewedTestItems: mocks.listReviewedTestItems,
  }),
  enginePorts: () => ({
    scheduler: { next: mocks.schedulerNext },
    questionRepo: {
      get: mocks.questionGet,
      nextReviewed: mocks.nextReviewed,
    },
    attemptRepo: { misses: vi.fn() },
    hintRepo: { list: mocks.hintList },
  }),
}));

import { GET } from "./route";

function request(): NextRequest {
  return new NextRequest("http://localhost/api/engine/next?session=s1");
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getAuthSession.mockResolvedValue({ sub: "learner-1" });
  mocks.getSession.mockResolvedValue({
    id: "s1",
    subject: "act-english",
    learner_id: "learner-1",
    mode: "drill",
    skill_focus: "skill-1",
    started_at: "2026-07-22T00:00:00.000Z",
    ended_at: null,
    score_correct: 0,
    score_total: 0,
    target_count: 30,
    current_question_id: null,
  });
  mocks.listSessionQuestionIds.mockResolvedValue(["q1"]);
  mocks.listSessionSkillIds.mockResolvedValue(["skill-1"]);
  mocks.nextReviewed.mockResolvedValue(null);
});

describe("GET /api/engine/next — empty reason", () => {
  it("returns exhausted when reviewed content exists but none remains servable", async () => {
    mocks.listReviewedTestItems.mockResolvedValue([{ id: "q1" }]);

    const res = await GET(request());

    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toMatchObject({
      empty: true,
      reason: "exhausted",
      question: null,
    });
  });

  it("returns no_content only when the reviewed bank is empty", async () => {
    mocks.listReviewedTestItems.mockResolvedValue([]);

    const res = await GET(request());

    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toMatchObject({
      empty: true,
      reason: "no_content",
      question: null,
    });
  });
});

describe("GET /api/engine/next — served-set ownership (FR-B9)", () => {
  it("reconstructs exclude ids server-side and never returns a served-set on the wire", async () => {
    mocks.getSession.mockResolvedValue({
      id: "s1",
      subject: "act-english",
      learner_id: "learner-1",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-07-22T00:00:00.000Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: 30,
      current_question_id: null,
    });
    const answered = Array.from({ length: 29 }, (_, i) => `q${i + 1}`);
    mocks.listSessionQuestionIds.mockResolvedValue(answered);
    mocks.listSessionSkillIds.mockResolvedValue(["skill-1"]);
    mocks.schedulerNext.mockResolvedValue({
      skill_id: "skill-1",
      question_id: "q30",
    });
    mocks.questionGet.mockResolvedValue({
      id: "q30",
      subject: "act-english",
      skill_id: "skill-1",
      stem: "Q30",
    });
    mocks.hintList.mockResolvedValue([]);

    const res = await GET(request());
    const body = await res.json();

    expect(mocks.schedulerNext).toHaveBeenCalledWith(
      "act-english",
      "learner-1",
      answered,
      ["skill-1"],
    );
    expect(body).toMatchObject({
      empty: false,
      question: { id: "q30" },
    });
    expect(body).not.toHaveProperty("served_question_ids");
    expect(body).not.toHaveProperty("servedIds");
  });
});
