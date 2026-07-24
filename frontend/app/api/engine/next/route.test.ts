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
  listSessionAttempts: vi.fn(),
  listReviewedTestItems: vi.fn(),
  listAlreadyCorrectQuestionIds: vi.fn(),
  listMisses: vi.fn(),
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
    listSessionAttempts: mocks.listSessionAttempts,
    listReviewedTestItems: mocks.listReviewedTestItems,
    listAlreadyCorrectQuestionIds: mocks.listAlreadyCorrectQuestionIds,
    listMisses: mocks.listMisses,
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
  mocks.listSessionAttempts.mockResolvedValue([]);
  mocks.listAlreadyCorrectQuestionIds.mockResolvedValue([]);
  mocks.listMisses.mockResolvedValue([]);
  mocks.nextReviewed.mockResolvedValue(null);
});

describe("GET /api/engine/next — target_count hard stop (FR-C2 / T R.3)", () => {
  it("returns session_complete (no item) when server tally already meets target", async () => {
    const resolved = Array.from({ length: 30 }, (_, i) => ({
      id: `a${i + 1}`,
      session_id: "s1",
      question_id: `q${i + 1}`,
      learner_id: "learner-1",
      subject: "act-english",
      skill_id: "skill-1",
      chosen_letter: "B",
      correct: true,
      used_hint: false,
      elapsed_ms: 100,
      created_at: `2026-07-22T00:00:${String(i).padStart(2, "0")}.000Z`,
      resolution: "first_try",
      idempotency_key: `k${i + 1}`,
    }));
    mocks.listSessionAttempts.mockResolvedValue(resolved);
    mocks.listSessionQuestionIds.mockResolvedValue(
      resolved.map((a) => a.question_id),
    );
    // Bank still has content — without the gate, /next would serve Q31.
    mocks.nextReviewed.mockResolvedValue({
      id: "q31",
      subject: "act-english",
      skill_id: "skill-1",
      difficulty: 3,
      context_html: "",
      stem: "Q31?",
      choices: [],
      answer_letter: "A",
      per_choice_rationale: {},
      why_correct_md: "",
      why_tempted_md: "",
      rule_md: "",
      item_type: "underlined-span-mc",
      misconception: null,
      reviewed: true,
      generated_by: "test",
    });
    mocks.listReviewedTestItems.mockResolvedValue([{ id: "q31" }]);

    const res = await GET(request());

    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toMatchObject({
      empty: true,
      reason: "session_complete",
      question: null,
    });
    expect(mocks.nextReviewed).not.toHaveBeenCalled();
    expect(mocks.schedulerNext).not.toHaveBeenCalled();
  });

  it("does not gate endless sessions (target_count null)", async () => {
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
      target_count: null,
      current_question_id: null,
    });
    mocks.listSessionAttempts.mockResolvedValue(
      Array.from({ length: 40 }, (_, i) => ({
        id: `a${i + 1}`,
        session_id: "s1",
        question_id: `q${i + 1}`,
        learner_id: "learner-1",
        subject: "act-english",
        skill_id: "skill-1",
        chosen_letter: "B",
        correct: true,
        used_hint: false,
        elapsed_ms: 100,
        created_at: "2026-07-22T00:00:00.000Z",
        resolution: "first_try",
        idempotency_key: `k${i + 1}`,
      })),
    );
    mocks.nextReviewed.mockResolvedValue({
      id: "q41",
      subject: "act-english",
      skill_id: "skill-1",
      difficulty: 3,
      context_html: "",
      stem: "Still going?",
      choices: [],
      answer_letter: "A",
      per_choice_rationale: {},
      why_correct_md: "",
      why_tempted_md: "",
      rule_md: "",
      item_type: "underlined-span-mc",
      misconception: null,
      reviewed: true,
      generated_by: "test",
    });
    mocks.hintList.mockResolvedValue([]);

    const res = await GET(request());
    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toMatchObject({
      empty: false,
      question: { id: "q41" },
    });
  });
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

describe("GET /api/engine/next — content-fresh eligibility (Phase E)", () => {
  function adaptiveSession() {
    return {
      id: "s1",
      subject: "act-english",
      learner_id: "learner-1",
      mode: "adaptive" as const,
      skill_focus: null,
      started_at: "2026-07-22T00:00:00.000Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: 30,
      current_question_id: null,
    };
  }

  it("layers already-correct ids onto the served exclude set (FR-E1 / E1a)", async () => {
    mocks.getSession.mockResolvedValue(adaptiveSession());
    mocks.listSessionQuestionIds.mockResolvedValue(["q-served"]);
    mocks.listSessionSkillIds.mockResolvedValue(["skill-1"]);
    mocks.listAlreadyCorrectQuestionIds.mockResolvedValue(["q-prior-correct"]);
    mocks.schedulerNext.mockResolvedValue({
      skill_id: "skill-1",
      question_id: "q-fresh",
    });
    mocks.questionGet.mockResolvedValue({
      id: "q-fresh",
      subject: "act-english",
      skill_id: "skill-1",
      stem: "fresh",
    });
    mocks.hintList.mockResolvedValue([]);

    const res = await GET(request());
    expect(res.status).toBe(200);
    expect(mocks.listAlreadyCorrectQuestionIds).toHaveBeenCalledWith(
      "act-english",
      "learner-1",
    );
    expect(mocks.schedulerNext).toHaveBeenCalledTimes(1);
    expect(mocks.schedulerNext).toHaveBeenCalledWith(
      "act-english",
      "learner-1",
      ["q-served", "q-prior-correct"],
      ["skill-1"],
    );
    await expect(res.json()).resolves.toMatchObject({
      empty: false,
      question: { id: "q-fresh" },
    });
  });

  it("falls back to servedIds-only FSRS when the preferred pool is empty (FR-E3)", async () => {
    const { EngineNotFoundError } = await import(
      "@/lib/ports/engine/errors"
    );
    mocks.getSession.mockResolvedValue(adaptiveSession());
    mocks.listSessionQuestionIds.mockResolvedValue(["q-served"]);
    mocks.listSessionSkillIds.mockResolvedValue(["skill-1"]);
    mocks.listAlreadyCorrectQuestionIds.mockResolvedValue([
      "q-a",
      "q-b",
      "q-c",
    ]);
    mocks.schedulerNext
      .mockRejectedValueOnce(
        new EngineNotFoundError("no unserved reviewed question"),
      )
      .mockResolvedValueOnce({
        skill_id: "skill-1",
        question_id: "q-a",
      });
    mocks.questionGet.mockResolvedValue({
      id: "q-a",
      subject: "act-english",
      skill_id: "skill-1",
      stem: "repeat",
    });
    mocks.hintList.mockResolvedValue([]);

    const res = await GET(request());
    expect(res.status).toBe(200);
    expect(mocks.schedulerNext).toHaveBeenCalledTimes(2);
    expect(mocks.schedulerNext).toHaveBeenNthCalledWith(
      1,
      "act-english",
      "learner-1",
      ["q-served", "q-a", "q-b", "q-c"],
      ["skill-1"],
    );
    expect(mocks.schedulerNext).toHaveBeenNthCalledWith(
      2,
      "act-english",
      "learner-1",
      ["q-served"],
      ["skill-1"],
    );
    await expect(res.json()).resolves.toMatchObject({
      empty: false,
      question: { id: "q-a" },
    });
  });

  it("does not apply eligibility to mode=drill (FR-E5 adaptive-only)", async () => {
    mocks.getSession.mockResolvedValue({
      ...adaptiveSession(),
      mode: "drill",
      skill_focus: "skill-1",
    });
    mocks.listSessionQuestionIds.mockResolvedValue(["q1"]);
    mocks.nextReviewed.mockResolvedValue({
      id: "q2",
      subject: "act-english",
      skill_id: "skill-1",
      stem: "drill",
    });
    mocks.hintList.mockResolvedValue([]);

    const res = await GET(request());
    expect(res.status).toBe(200);
    expect(mocks.listAlreadyCorrectQuestionIds).not.toHaveBeenCalled();
    expect(mocks.schedulerNext).not.toHaveBeenCalled();
    expect(mocks.nextReviewed).toHaveBeenCalledWith(
      "act-english",
      "skill-1",
      ["q1"],
    );
    await expect(res.json()).resolves.toMatchObject({
      empty: false,
      question: { id: "q2" },
    });
  });

  it("does not apply eligibility to mode=review (FR-E5)", async () => {
    mocks.getSession.mockResolvedValue({
      ...adaptiveSession(),
      mode: "review",
    });
    mocks.listSessionQuestionIds.mockResolvedValue([]);
    mocks.listMisses.mockResolvedValue([
      {
        id: "a1",
        subject: "act-english",
        session_id: "old",
        question_id: "q-miss",
        chosen_letter: "B",
        correct: false,
        elapsed_ms: 1,
        used_hint: false,
        created_at: "2026-07-21T00:00:00.000Z",
      },
    ]);
    mocks.questionGet.mockResolvedValue({
      id: "q-miss",
      subject: "act-english",
      skill_id: "skill-1",
      stem: "miss",
    });
    mocks.hintList.mockResolvedValue([]);

    const res = await GET(request());
    expect(res.status).toBe(200);
    expect(mocks.listAlreadyCorrectQuestionIds).not.toHaveBeenCalled();
    expect(mocks.schedulerNext).not.toHaveBeenCalled();
    expect(mocks.listMisses).toHaveBeenCalledWith("act-english", "learner-1");
    await expect(res.json()).resolves.toMatchObject({
      empty: false,
      question: { id: "q-miss" },
    });
  });
});
