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
  AttemptResolution,
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
import {
  browserEngineClient,
  durableEngineEnabled,
} from "@/lib/adapters/engine/engine_client";

export { uniqueMissQuestionIds } from "@/lib/miss_pool";
export interface QuizItemResult {
  readonly skillId: string;
  readonly question: Question;
  /**
   * The question's REVIEWED hint ladder, rung ascending (ADR-0014, FR-12/20).
   * `[]` when no reviewed rungs exist — the hint panel falls back to the
   * generic Socratic nudge, never an unreviewed row.
   * ADR-0035: item-level by default; pass `choiceLetter` via `loadHintLadder`
   * after a wrong pick for Gen2 choice-conditional rungs.
   */
  readonly hintLadder: readonly Hint[];
}

/**
 * ADR-0035 moment-router load: `choiceLetter` null/omit → Gen1 item-level;
 * A–D → that wrong letter's Gen2 ladder (empty when none reviewed).
 */
export async function loadHintLadder(
  ports: Pick<EnginePortBag, "hintRepo">,
  subject: string,
  questionId: string,
  choiceLetter?: string | null,
): Promise<readonly Hint[]> {
  const letter =
    choiceLetter === "A" ||
    choiceLetter === "B" ||
    choiceLetter === "C" ||
    choiceLetter === "D"
      ? choiceLetter
      : null;
  return ports.hintRepo.list(subject, questionId, letter);
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
  // T A.11: durable + session → ONE GET /next (scheduler + served-set server-side).
  if (durableEngineEnabled() && args.sessionId != null) {
    const payload = await browserEngineClient().nextItem(args.sessionId);
    if (payload.empty || payload.question == null) {
      throw new EngineNotFoundError(
        payload.reason === "no_content"
          ? "no content available"
          : "no next item",
      );
    }
    return {
      skillId: payload.skill_id ?? payload.question.skill_id,
      question: payload.question,
      hintLadder: payload.hints,
    };
  }

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
  // Item-level ladder at open (ADR-0014); wrong-letter Gen2 reload is
  // loadHintLadder + ladder_loaded on the quiz page (ADR-0035).
  const hintLadder = await loadHintLadder(ports, args.subject, question.id);
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
  const hintLadder = await loadHintLadder(ports, args.subject, question.id);
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
  const hintLadder = await loadHintLadder(ports, args.subject, question.id);
  return { skillId: question.skill_id, question, hintLadder };
}

/**
 * FR-A7 / FR-A9.1: sync grade + one idempotency key per answer action.
 * The quiz page shows `verdict` immediately, then persists via `runQuizSubmit`
 * with the same key (resent verbatim on FR-A8 retry — never mint a second key).
 */
export function planAnswerAction(
  ports: Pick<EnginePortBag, "grader">,
  args: {
    readonly question: Question;
    readonly letter: string | null;
    /** Reuse on write-fail retry; omit to mint a fresh UUID. */
    readonly idempotencyKey?: string;
  },
): { verdict: Verdict; letter: string; idempotencyKey: string } | null {
  if (args.letter == null) return null;
  const verdict = ports.grader.grade(args.question, { letter: args.letter });
  if (verdict == null) return null;
  return {
    verdict,
    letter: args.letter,
    idempotencyKey: args.idempotencyKey ?? crypto.randomUUID(),
  };
}

/** FR-G3: durable empty bank → honest "no content" UI (not a generic crash). */
export function isNoContentError(err: unknown): boolean {
  return (
    err instanceof EngineNotFoundError &&
    /no content available/i.test(err.message)
  );
}

export interface QuizSubmitArgs {
  readonly session: QuizSession;
  readonly question: Question;
  readonly learnerId: string;
  readonly letter: string | null;
  readonly elapsedMs: number;
  readonly usedHint: boolean;
  /**
   * Commit-first FR-10: set only on the resolving attempt. Omit/null for
   * non-resolving wrongs and legacy single-attempt submits. When
   * `commitFirstCoach` is true and this is omitted, derived from the verdict
   * + `hadPriorWrongAttempts`.
   */
  readonly resolution?: AttemptResolution | null;
  /**
   * Commit-first FR-12: when false, skip `scheduler.review` (retry/escape after
   * the first graded attempt). Default true preserves legacy always-review.
   */
  readonly isFirstGradedAttempt?: boolean;
  /**
   * Commit-first: when false, skip coach-marker notify (still in coached loop).
   * Default true preserves legacy notify-on-every-real-submit. When
   * `commitFirstCoach` is true and this is omitted, derived from the verdict
   * (wrong ⇒ false, correct ⇒ true).
   */
  readonly resolvesItem?: boolean;
  /**
   * When true, derive resolvesItem/resolution from the graded verdict
   * (wrong stays in loop; correct resolves as first_try/coached).
   */
  readonly commitFirstCoach?: boolean;
  /** True when this item already has a recorded wrong (for coached vs first_try). */
  readonly hadPriorWrongAttempts?: boolean;
  /**
   * FR-A9.1: one key per answer action. Caller stamps at grade time and resends
   * verbatim on HTTP retry; omit to mint a new UUID (fresh action).
   */
  readonly idempotencyKey?: string;
}

export interface QuizSubmitResult {
  /** null when nothing was selected (FR-D2a). */
  readonly verdict: Verdict | null;
  /** null when nothing was selected (no attempt recorded). */
  readonly attempt: Attempt | null;
  /** null when nothing was selected or review was skipped (FR-12 retry). */
  readonly skillState: SkillState | null;
}

export interface QuizEscapeArgs {
  readonly session: QuizSession;
  readonly question: Question;
  readonly learnerId: string;
  /** Last wrong letter (honest: learner never produced the key — FR-6). */
  readonly lastWrongLetter: string;
  readonly elapsedMs: number;
  readonly usedHint: boolean;
  /** Almost always false — exhaustion requires a prior wrong (FR-12). */
  readonly isFirstGradedAttempt?: boolean;
  /** FR-A9.1: stable key for escape-action retries. */
  readonly idempotencyKey?: string;
}

export interface QuizEscapeResult {
  readonly attempt: Attempt;
  readonly skillState: SkillState | null;
}

/**
 * Grade → (record + review) for one submitted answer. No selection ⇒ all-null
 * result and zero side effects (FR-D2a/D4).
 *
 * Commit-first extensions (optional args; defaults preserve legacy):
 *   - `resolution` written on the resolving attempt only (FR-10)
 *   - `scheduler.review` only when `isFirstGradedAttempt !== false` (FR-12)
 *   - coach notify only when `resolvesItem !== false` (stay pre_submit in loop)
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

  const commitFirst = args.commitFirstCoach === true;
  const resolvesItem =
    args.resolvesItem != null
      ? args.resolvesItem
      : commitFirst
        ? verdict.correct
        : true;
  let resolution: AttemptResolution | null | undefined = args.resolution;
  if (resolution === undefined && commitFirst && verdict.correct) {
    resolution = args.hadPriorWrongAttempts ? "coached" : "first_try";
  }

  // FR-A9.1: one idempotency_key per answer action (stamped at grade time).
  const idempotency_key = args.idempotencyKey ?? crypto.randomUUID();
  const attempt = await ports.attemptRepo.record({
    subject: args.question.subject,
    session_id: args.session.id,
    question_id: args.question.id,
    chosen_letter: args.letter,
    correct: verdict.correct,
    elapsed_ms: args.elapsedMs,
    used_hint: args.usedHint,
    idempotency_key,
    ...(resolution != null ? { resolution } : {}),
  });

  // ADR-0012 Amendment (FR-19): fire-and-forget marker write — flips the
  // coach's derived mode to post_feedback for this item. Fires as soon as
  // the attempt is durably recorded, BEFORE the FSRS review: a failing
  // review must not strand the coach in pre_submit for a question whose
  // feedback the learner is already looking at. Only a REAL submit notifies
  // (the no-selection path returned above); a throwing notifier never
  // breaks grading (fail-closed: the coach just stays pre_submit).
  // Commit-first: skip while still in the coached loop (`resolvesItem: false`).
  if (resolvesItem) {
    try {
      ports.quizSubmitNotifier?.notifySubmitted(args.question.id);
    } catch {
      // Swallow by contract (QuizSubmitNotifier rule 1).
    }
  }

  // FR-12: mastery reviews the first graded attempt only.
  const isFirst = args.isFirstGradedAttempt !== false;
  const skillState = isFirst ? await ports.scheduler.review(attempt) : null;

  return { verdict, attempt, skillState };
}

/**
 * Priced escape (FR-6): record a resolving attempt with `correct=false`,
 * `resolution="walked_through"`, `chosen_letter` = last wrong letter. Notifies
 * the coach marker (item resolved); reviews only if somehow first attempt.
 */
export async function runQuizEscape(
  ports: EnginePortBag,
  args: QuizEscapeArgs,
): Promise<QuizEscapeResult> {
  const attempt = await ports.attemptRepo.record({
    subject: args.question.subject,
    session_id: args.session.id,
    question_id: args.question.id,
    chosen_letter: args.lastWrongLetter,
    correct: false,
    elapsed_ms: args.elapsedMs,
    used_hint: args.usedHint,
    resolution: "walked_through",
    idempotency_key: args.idempotencyKey ?? crypto.randomUUID(),
  });

  try {
    ports.quizSubmitNotifier?.notifySubmitted(args.question.id);
  } catch {
    // Swallow by contract (QuizSubmitNotifier rule 1).
  }

  const isFirst = args.isFirstGradedAttempt === true;
  const skillState = isFirst ? await ports.scheduler.review(attempt) : null;
  return { attempt, skillState };
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
  const hintLadder = await loadHintLadder(ports, session.subject, question.id);
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
  /** FR-A7: sync grade + mint/reuse idempotency key (before persist). */
  planAnswer: (args: {
    question: Question;
    letter: string | null;
    idempotencyKey?: string;
  }) => { verdict: Verdict; letter: string; idempotencyKey: string } | null;
  submit: (args: QuizSubmitArgs) => Promise<QuizSubmitResult>;
  escape: (args: QuizEscapeArgs) => Promise<QuizEscapeResult>;
  closeSession: (args: CloseSessionArgs) => Promise<QuizSession>;
  listSkillIds: (subject: string) => Promise<string[]>;
  listSkills: (subject: string) => Promise<Skill[]>;
  /** ADR-0035: reload ladder for a wrong-letter pick (moment router). */
  loadLadder: (
    subject: string,
    questionId: string,
    choiceLetter?: string | null,
  ) => Promise<readonly Hint[]>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({
      openSession: (args: OpenSessionArgs) => openQuizSession(ports, args),
      openItem: (args: { subject: string; learnerId: string; sessionId?: string }) =>
        openQuizItem(ports, args),
      resumeSession: (args: { sessionId: string; questionId: string }) =>
        resumeQuizSession(ports, args),
      planAnswer: (args: {
        question: Question;
        letter: string | null;
        idempotencyKey?: string;
      }) => planAnswerAction(ports, args),
      submit: (args: QuizSubmitArgs) => runQuizSubmit(ports, args),
      escape: (args: QuizEscapeArgs) => runQuizEscape(ports, args),
      closeSession: (args: CloseSessionArgs) => closeQuizSession(ports, args),
      listSkillIds: (subject: string) => listQuizSkillIds(ports, subject),
      listSkills: (subject: string) => listQuizSkills(ports, subject),
      loadLadder: (
        subject: string,
        questionId: string,
        choiceLetter?: string | null,
      ) => loadHintLadder(ports, subject, questionId, choiceLetter),
    }),
    [ports],
  );
}
