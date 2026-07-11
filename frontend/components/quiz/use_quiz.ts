/**
 * useQuiz — the Quiz screen's seam onto the engine ports (FR-D1..D8).
 *
 * Per F-R1 the Quiz component owns NO domain logic. The whole learning
 * sequence — scheduler pick → reviewed question → grade → record attempt →
 * FSRS review — lives here. The orchestration is exported as React-free async
 * functions (`openQuizItem`, `runQuizSubmit`) so it is testable in node against
 * a seeded InMemoryEngineDb with no React and no mocks (the analogue of
 * `consumeRunStream` in use_agent_run).
 *
 * Grading order (FR-D2/D3/A2): grade with the pure Grader FIRST; only a
 * non-null verdict (a real selection, FR-D2a) yields an attempt, which is then
 * recorded (AttemptRepo) and fed to the Scheduler's `review()` — the sole
 * `skill_state` writer. No selection ⇒ no verdict ⇒ no attempt ⇒ no state write.
 *
 * Imports engine ports (via the injected bag) + wire shapes only. The default
 * bag comes from `useEngine()` context (C3); tests inject a seeded bag directly.
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import type {
  Attempt,
  Hint,
  Question,
  QuizSession,
  SessionMode,
  Skill,
  SkillState,
  Verdict,
} from "@/lib/wire/engine_entities";
import { EngineNotFoundError } from "@/lib/ports/engine/errors";
import { uniqueMissQuestionIds } from "@/lib/miss_pool";

export { uniqueMissQuestionIds } from "@/lib/miss_pool";
export interface QuizItemResult {
  readonly skillId: string;
  readonly question: Question;
  /**
   * The question's REVIEWED hint ladder, rung ascending (ADR-0014, FR-12/20).
   * `[]` when no reviewed rungs exist — the hint panel falls back to the
   * generic Socratic nudge, never an unreviewed row.
   */
  readonly hintLadder: readonly Hint[];
}

export interface OpenSessionArgs {
  readonly subject: string;
  readonly learnerId: string;
  readonly mode: SessionMode;
  /** Skill id for a drill session (FR-A5); omit/null for adaptive/review. */
  readonly focus?: string | null;
  /**
   * Bounded-session length (S3, FR-5/6). Omit → the repo resolves the per-mode
   * default (30) from the `content_string` policy; a positive int → that many
   * items; `null` → an endless session. The distinction between "omitted" and
   * explicit `null` is preserved end-to-end (undefined ≠ null).
   */
  readonly targetCount?: number | null;
}

export interface QuizSessionResult {
  readonly session: QuizSession;
  /**
   * The learner's per-skill mastery captured ONCE at session open, before the
   * first `review()` mutates skill_state — the "before" half of the FR-G1 delta
   * (ADR-0011 §4). Keyed by `skill_id`; empty for a brand-new learner (delta
   * later renders "—"). Immutable: it must not track the in-session mutations
   * the Scheduler makes, so Summary can diff it against a fresh read.
   */
  readonly skillStateAtStart: ReadonlyMap<string, SkillState>;
}

/**
 * Open a quiz session and snapshot the learner's mastery at that moment.
 *
 * FR-G1 needs the mastery delta across the session. `SkillState.mastery` is
 * mutated by `Scheduler.review()` during play, so "before" must be read once at
 * open — after `sessionRepo.open(...)` resolves, before any `runQuizSubmit`
 * (ADR-0011 §4). The read goes through the read-only `learnerRead` port, never
 * the write path (FR-A2: the Scheduler is the sole skill_state writer).
 */
export async function openQuizSession(
  ports: EnginePortBag,
  args: OpenSessionArgs,
): Promise<QuizSessionResult> {
  // Review sessions bound to the unique miss pool size (FR-A6 / FR-C5) unless
  // the caller passed an explicit targetCount (including null = endless).
  let targetCount = args.targetCount;
  if (args.mode === "review" && targetCount === undefined) {
    const misses = await ports.attemptRepo.misses(args.subject, args.learnerId);
    targetCount = uniqueMissQuestionIds(misses).length;
  }
  const session = await ports.sessionRepo.open(
    args.subject,
    args.learnerId,
    args.mode,
    args.focus ?? null,
    // Forward verbatim (no coalescing): `undefined` = omitted → repo resolves
    // the default; explicit `null` = endless; a value = that length (FR-5/6).
    targetCount,
  );
  const rows = await ports.learnerRead.listSkillState(args.subject, args.learnerId);
  const skillStateAtStart = new Map(rows.map((s) => [s.skill_id, s]));
  return { session, skillStateAtStart };
}

/**
 * List the subject's known skill ids (`Skill.id`) — the set FR-6 validates a
 * `?focus=` param against before opening a drill. Read-only taxonomy access; no
 * mastery, no write path (SkillTaxonomy contract #1).
 */
export async function listQuizSkillIds(
  ports: EnginePortBag,
  subject: string,
): Promise<string[]> {
  const skills = await ports.skillTaxonomy.list(subject);
  return skills.map((s) => s.id);
}

/**
 * List the subject's full `Skill` rows (D1 Q-7). The page joins
 * `Question.skill_id` against these to fill `QuizItemVM.skillName` /
 * `accentVar`. Read-only taxonomy; keeps `listQuizSkillIds` for focus-param
 * resolution (no regression).
 */
export async function listQuizSkills(
  ports: EnginePortBag,
  subject: string,
): Promise<Skill[]> {
  return ports.skillTaxonomy.list(subject);
}

/**
 * Pick the next (skill, question) for the learner and load the reviewed item.
 *
 * `sessionId` (S3, FR-9/FR-13): when present, the play loop derives this
 * session's already-served question ids from its `attempt` rows and passes them
 * to `scheduler.next` so a session never repeats a question. It also derives the
 * served *skills* newest-first (S3.1, FR-3/ADR-0024) so the scheduler rotates to
 * a different bucket instead of parking on the same weakest skill. Both sets are
 * ephemeral + caller-owned (derived here, never persisted on `skill_state`);
 * omitting `sessionId` keeps today's single-pick behaviour (backward-compatible).
 *
 * Review sessions (FR-A6): draw from `AttemptRepo.misses` (unique ids,
 * newest-incorrect first), skipping ids already served this session — not the
 * adaptive FSRS scheduler.
 *
 * Drill sessions (FR-A5): draw only from `session.skill_focus` via
 * `QuestionRepo.nextReviewed` — never cross-skill adaptive priority.
 */
export async function openQuizItem(
  ports: EnginePortBag,
  args: { subject: string; learnerId: string; sessionId?: string },
): Promise<QuizItemResult> {
  const servedIds =
    args.sessionId != null
      ? await ports.attemptRepo.servedQuestionIds(args.sessionId)
      : undefined;
  const servedSkillIds =
    args.sessionId != null
      ? await ports.attemptRepo.servedSkillIds(args.sessionId)
      : undefined;

  if (args.sessionId != null) {
    const session = await ports.sessionRepo.get(args.sessionId);
    if (session?.mode === "review") {
      return openReviewQuizItem(ports, {
        subject: args.subject,
        learnerId: args.learnerId,
        servedIds: servedIds ?? [],
      });
    }
    if (session?.mode === "drill" && session.skill_focus != null) {
      return openDrillQuizItem(ports, {
        subject: args.subject,
        skillId: session.skill_focus,
        servedIds: servedIds ?? [],
      });
    }
  }

  const next = await ports.scheduler.next(
    args.subject,
    args.learnerId,
    servedIds,
    servedSkillIds,
  );
  const question = await ports.questionRepo.get(next.question_id);
  if (question == null) {
    // The scheduler picked an id the repo can't resolve — a seam defect, surfaced
    // rather than handing the learner an empty item.
    throw new Error(`scheduled question ${next.question_id} not found`);
  }
  // The ladder loads WITH the item (no per-hint fetch): reviewed rungs only
  // (ADR-0014); [] keeps the panel on the generic nudge fallback.
  const hintLadder = await ports.hintRepo.list(args.subject, question.id);
  return { skillId: next.skill_id, question, hintLadder };
}

/** FR-A5: next unserved reviewed item for the drill's focused skill only. */
async function openDrillQuizItem(
  ports: EnginePortBag,
  args: {
    subject: string;
    skillId: string;
    servedIds: readonly string[];
  },
): Promise<QuizItemResult> {
  const question = await ports.questionRepo.nextReviewed(
    args.subject,
    args.skillId,
    args.servedIds,
  );
  if (question == null) {
    throw new EngineNotFoundError(
      `no unserved reviewed question for drill skill '${args.skillId}' (subject '${args.subject}')`,
    );
  }
  const hintLadder = await ports.hintRepo.list(args.subject, question.id);
  return { skillId: args.skillId, question, hintLadder };
}

/** FR-A6: next unserved unique miss, newest-incorrect first. */
async function openReviewQuizItem(
  ports: EnginePortBag,
  args: {
    subject: string;
    learnerId: string;
    servedIds: readonly string[];
  },
): Promise<QuizItemResult> {
  const misses = await ports.attemptRepo.misses(args.subject, args.learnerId);
  const pool = uniqueMissQuestionIds(misses);
  const nextId = pool.find((id) => !args.servedIds.includes(id));
  if (nextId == null) {
    throw new EngineNotFoundError(
      `no unserved missed questions for learner '${args.learnerId}' (subject '${args.subject}')`,
    );
  }
  const question = await ports.questionRepo.get(nextId);
  if (question == null) {
    throw new Error(`missed question ${nextId} not found`);
  }
  const hintLadder = await ports.hintRepo.list(args.subject, question.id);
  return { skillId: question.skill_id, question, hintLadder };
}

export interface QuizSubmitArgs {
  readonly session: QuizSession;
  readonly question: Question;
  readonly learnerId: string;
  readonly letter: string | null;
  readonly elapsedMs: number;
  readonly usedHint: boolean;
}

export interface QuizSubmitResult {
  /** null when nothing was selected (FR-D2a). */
  readonly verdict: Verdict | null;
  /** null when nothing was selected (no attempt recorded). */
  readonly attempt: Attempt | null;
  /** null when nothing was selected (no FSRS review ran). */
  readonly skillState: SkillState | null;
}

/**
 * Grade → (record + review) for one submitted answer. No selection ⇒ all-null
 * result and zero side effects (FR-D2a/D4).
 */
export async function runQuizSubmit(
  ports: EnginePortBag,
  args: QuizSubmitArgs,
): Promise<QuizSubmitResult> {
  const verdict = ports.grader.grade(args.question, { letter: args.letter });
  if (verdict == null || args.letter == null) {
    // FR-D2a: nothing selected — record nothing, schedule nothing.
    return { verdict: null, attempt: null, skillState: null };
  }

  const attempt = await ports.attemptRepo.record({
    subject: args.question.subject,
    session_id: args.session.id,
    question_id: args.question.id,
    chosen_letter: args.letter,
    correct: verdict.correct,
    elapsed_ms: args.elapsedMs,
    used_hint: args.usedHint,
  });

  // ADR-0012 Amendment (FR-19): fire-and-forget marker write — flips the
  // coach's derived mode to post_feedback for this item. Fires as soon as
  // the attempt is durably recorded, BEFORE the FSRS review: a failing
  // review must not strand the coach in pre_submit for a question whose
  // feedback the learner is already looking at. Only a REAL submit notifies
  // (the no-selection path returned above); a throwing notifier never
  // breaks grading (fail-closed: the coach just stays pre_submit).
  try {
    ports.quizSubmitNotifier?.notifySubmitted(args.question.id);
  } catch {
    // Swallow by contract (QuizSubmitNotifier rule 1).
  }

  const skillState = await ports.scheduler.review(attempt);

  return { verdict, attempt, skillState };
}

export interface CloseSessionArgs {
  readonly sessionId: string;
  readonly scoreCorrect: number;
  readonly scoreTotal: number;
}

/**
 * Close the session with the running tally so the STORED score is what the
 * Summary reads (FR-D3/G1 — Summary never re-tallies). Called once on Finish,
 * before the route change. `sessionRepo.close` is idempotent, so a late/duplicate
 * close (e.g. a double-tap) re-applies the same tally harmlessly.
 */
export async function closeQuizSession(
  ports: EnginePortBag,
  args: CloseSessionArgs,
): Promise<QuizSession> {
  return ports.sessionRepo.close(args.sessionId, {
    score_correct: args.scoreCorrect,
    score_total: args.scoreTotal,
  });
}

/**
 * Resume a live Quiz session at a stashed question (FLAG-4 / FR-3 / FR-4).
 *
 * Loads the existing session + the specific question (not a fresh scheduler
 * pick). Returns `null` when the session or question is gone — caller MUST
 * clear the active pointer and open a fresh session (honest recovery, FR-4).
 */
export async function resumeQuizSession(
  ports: EnginePortBag,
  args: { sessionId: string; questionId: string },
): Promise<{ session: QuizSession; item: QuizItemResult } | null> {
  const session = await ports.sessionRepo.get(args.sessionId);
  if (session == null) return null;
  const question = await ports.questionRepo.get(args.questionId);
  if (question == null) return null;
  const hintLadder = await ports.hintRepo.list(session.subject, question.id);
  return {
    session,
    item: { skillId: question.skill_id, question, hintLadder },
  };
}

/**
 * Thin React wrapper: reads the engine bag from context (C3) and exposes the
 * orchestration bound to it. The component calls these; it holds no port logic.
 * Tests exercise `openQuizItem` / `runQuizSubmit` / `closeQuizSession` directly
 * with an injected bag, so the hook itself stays a trivial context binding (no
 * test-only param that would force a conditional `useEngine()` call).
 */
export function useQuiz(): {
  openSession: (args: OpenSessionArgs) => Promise<QuizSessionResult>;
  openItem: (args: {
    subject: string;
    learnerId: string;
    sessionId?: string;
  }) => Promise<QuizItemResult>;
  resumeSession: (args: {
    sessionId: string;
    questionId: string;
  }) => Promise<{ session: QuizSession; item: QuizItemResult } | null>;
  submit: (args: QuizSubmitArgs) => Promise<QuizSubmitResult>;
  closeSession: (args: CloseSessionArgs) => Promise<QuizSession>;
  listSkillIds: (subject: string) => Promise<string[]>;
  listSkills: (subject: string) => Promise<Skill[]>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({
      openSession: (args: OpenSessionArgs) => openQuizSession(ports, args),
      openItem: (args: { subject: string; learnerId: string; sessionId?: string }) =>
        openQuizItem(ports, args),
      resumeSession: (args: { sessionId: string; questionId: string }) =>
        resumeQuizSession(ports, args),
      submit: (args: QuizSubmitArgs) => runQuizSubmit(ports, args),
      closeSession: (args: CloseSessionArgs) => closeQuizSession(ports, args),
      listSkillIds: (subject: string) => listQuizSkillIds(ports, subject),
      listSkills: (subject: string) => listQuizSkills(ports, subject),
    }),
    [ports],
  );
}
