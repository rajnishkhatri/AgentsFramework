/**
 * Phase B — durable resumeQuizSession (FR-B1/B3/B3b/B5/B8/B10).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";
import type { EnginePortBag } from "@/lib/composition_engine";
import {
  isResumeExhaustedError,
  QuizResumeExhaustedError,
  recordServedPointer,
  resumeQuizSession,
} from "./use_quiz";
import type { Question, QuizSession, Skill } from "@/lib/wire/engine_entities";

const SUBJECT = "act-english";
const LEARNER = "maya";

const durable = vi.hoisted(() => ({
  enabled: false,
  getActiveSession: vi.fn(),
  nextItem: vi.fn(),
  setSessionCurrent: vi.fn(),
}));

vi.mock("@/lib/adapters/engine/engine_client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/adapters/engine/engine_client")>();
  return {
    ...actual,
    durableEngineEnabled: () => durable.enabled,
    browserEngineClient: () =>
      ({
        getActiveSession: durable.getActiveSession,
        nextItem: durable.nextItem,
        setSessionCurrent: durable.setSessionCurrent,
      }) as unknown as ReturnType<typeof actual.browserEngineClient>,
  };
});

function skill(): Skill {
  return {
    id: "s-punc",
    subject: SUBJECT,
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-punctuation",
    description: "…",
    order: 1,
  };
}

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q4",
    subject: SUBJECT,
    skill_id: "s-punc",
    difficulty: 3,
    context_html: "ctx",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "A", B: "B" },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "…",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

function openSession(over: Partial<QuizSession> = {}): QuizSession {
  return {
    id: "sess-open",
    subject: SUBJECT,
    learner_id: LEARNER,
    mode: "adaptive",
    skill_focus: null,
    started_at: "2026-07-22T00:00:00.000Z",
    ended_at: null,
    score_correct: 0,
    score_total: 0,
    target_count: 30,
    current_question_id: "q4",
    ...over,
  };
}

let db: InMemoryEngineDb;
let ports: EnginePortBag;

beforeEach(() => {
  durable.enabled = true;
  durable.getActiveSession.mockReset();
  durable.nextItem.mockReset();
  durable.setSessionCurrent.mockReset();
  durable.setSessionCurrent.mockResolvedValue({ ok: true });

  db = new InMemoryEngineDb();
  db.seedSkills([skill()]);
  db.seedQuestions([question(), question({ id: "q5", stem: "Next?" })]);
  ports = buildBrowserEngineAdapters({ engineDb: db });
});

afterEach(() => {
  durable.enabled = false;
  vi.unstubAllEnvs();
});

describe("resumeQuizSession — durable (Phase B)", () => {
  it("re-shows a zero-attempt pointer and uses the server running score (FR-B3b/B10)", async () => {
    durable.getActiveSession.mockResolvedValue({
      session: openSession(),
      running_score: { score_correct: 2, score_total: 5 },
      pointer_attempted: false,
      complete: false,
    });

    const got = await resumeQuizSession(ports, { subject: SUBJECT });

    expect(got).not.toBeNull();
    expect(got!.item.question.id).toBe("q4");
    expect(got!.score).toEqual({ correct: 2, total: 5 });
    expect(durable.nextItem).not.toHaveBeenCalled();
  });

  it("advances when the pointer already has any attempt row (FR-B3-feedback)", async () => {
    durable.getActiveSession.mockResolvedValue({
      session: openSession(),
      running_score: { score_correct: 1, score_total: 2 },
      pointer_attempted: true,
      complete: false,
    });
    durable.nextItem.mockResolvedValue({
      empty: false,
      question: question({ id: "q5" }),
      hints: [],
      skill_id: "s-punc",
    });

    const got = await resumeQuizSession(ports, { subject: SUBJECT });

    expect(got!.item.question.id).toBe("q5");
    expect(durable.nextItem).toHaveBeenCalledWith("sess-open");
  });

  it("NULL pointer falls back to a scoped /next pick (FR-B8)", async () => {
    durable.getActiveSession.mockResolvedValue({
      session: openSession({ current_question_id: null }),
      running_score: { score_correct: 0, score_total: 0 },
      pointer_attempted: false,
      complete: false,
    });
    durable.nextItem.mockResolvedValue({
      empty: false,
      question: question({ id: "q5" }),
      hints: [],
      skill_id: "s-punc",
    });

    const got = await resumeQuizSession(ports, { subject: SUBJECT });

    expect(got!.item.question.id).toBe("q5");
    expect(durable.nextItem).toHaveBeenCalledWith("sess-open");
  });

  it("returns null when the stored question id no longer resolves (FR-B5)", async () => {
    durable.getActiveSession.mockResolvedValue({
      session: openSession({ current_question_id: "gone-q" }),
      running_score: { score_correct: 0, score_total: 1 },
      pointer_attempted: false,
      complete: false,
    });

    const got = await resumeQuizSession(ports, { subject: SUBJECT });
    expect(got).toBeNull();
  });

  it("returns null when there is no open session (FR-B7 completed skipped)", async () => {
    durable.getActiveSession.mockResolvedValue({
      session: null,
      running_score: null,
      pointer_attempted: false,
      complete: false,
    });

    expect(await resumeQuizSession(ports, { subject: SUBJECT })).toBeNull();
  });

  it("throws QuizResumeExhaustedError carrying the session when advance empties (FR-C5)", async () => {
    durable.getActiveSession.mockResolvedValue({
      session: openSession({ current_question_id: null }),
      running_score: { score_correct: 3, score_total: 3 },
      pointer_attempted: false,
      complete: false,
    });
    durable.nextItem.mockResolvedValue({
      empty: true,
      reason: "exhausted",
      question: null,
      hints: [],
      skill_id: null,
    });

    await expect(resumeQuizSession(ports, { subject: SUBJECT })).rejects.toThrow(
      QuizResumeExhaustedError,
    );
    try {
      await resumeQuizSession(ports, { subject: SUBJECT });
    } catch (err) {
      expect(isResumeExhaustedError(err)).toBe(true);
      if (isResumeExhaustedError(err)) {
        expect(err.session.id).toBe("sess-open");
        expect(err.score).toEqual({ correct: 3, total: 3 });
      }
    }
  });

  it("treats an at-target open session as complete — no Q31 via /next (FR-C2 / T R.3)", async () => {
    durable.getActiveSession.mockResolvedValue({
      session: openSession({ current_question_id: null, target_count: 30 }),
      running_score: { score_correct: 20, score_total: 30 },
      pointer_attempted: false,
      complete: true,
    });

    await expect(resumeQuizSession(ports, { subject: SUBJECT })).rejects.toThrow(
      QuizResumeExhaustedError,
    );
    expect(durable.nextItem).not.toHaveBeenCalled();
    try {
      await resumeQuizSession(ports, { subject: SUBJECT });
    } catch (err) {
      expect(isResumeExhaustedError(err)).toBe(true);
      if (isResumeExhaustedError(err)) {
        expect(err.score).toEqual({ correct: 20, total: 30 });
      }
    }
  });
});

describe("recordServedPointer — FR-B3a / B3a-nonblock", () => {
  it("posts the served pointer under the durable flag", async () => {
    recordServedPointer("sess-open", "q4");
    await Promise.resolve();
    expect(durable.setSessionCurrent).toHaveBeenCalledWith("sess-open", "q4");
  });

  it("swallows pointer-write failures so the serve is never blocked", async () => {
    durable.setSessionCurrent.mockRejectedValue(new Error("network down"));
    expect(() => recordServedPointer("sess-open", "q4")).not.toThrow();
    await Promise.resolve();
    expect(durable.setSessionCurrent).toHaveBeenCalled();
  });

  it("is a no-op when durable_engine is off", async () => {
    durable.enabled = false;
    recordServedPointer("sess-open", "q4");
    await Promise.resolve();
    expect(durable.setSessionCurrent).not.toHaveBeenCalled();
  });
});
