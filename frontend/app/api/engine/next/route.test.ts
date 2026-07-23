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
    scheduler: { next: vi.fn() },
    questionRepo: {
      get: vi.fn(),
      nextReviewed: mocks.nextReviewed,
    },
    attemptRepo: { misses: vi.fn() },
    hintRepo: { list: vi.fn() },
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
