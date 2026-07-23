// B1: 'use client' required — the Quiz screen drives a live learning loop over
// the engine bag from useEngine() (the browser-safe InMemoryEngineDb substrate,
// ADR-0005 local-first): it opens a session, pulls scheduled items, grades
// submissions, and reviews — all async, client-only. The domain logic lives in
// the React-free orchestration (openQuizSession/openQuizItem/runQuizSubmit in
// use_quiz) and the pure quiz_screen_reducer phase machine (F-R1); this page is
// the thin glue that runs those effects and renders the phase.
//
// FR-G1 handoff: the `skillStateAtStart` snapshot captured at session open is
// stashed in quiz_session_store keyed by session id, so the Summary route can
// read it back and show a real mastery delta within the unbroken session
// (ADR-0011 §4). On a fresh Summary load the map is gone → delta "—".
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { buildBrowserRuntimeClient } from "@/lib/composition_browser";
import { QuizView, QuizFrameChrome } from "@/components/quiz/QuizView";
import { QuizProgress } from "@/components/quiz/QuizProgress";
import { FeedbackView } from "@/components/feedback/FeedbackView";
import { CoachDrawer } from "@/components/coach/CoachDrawer";
import { CoachPanel } from "@/components/coach/CoachPanel";
import { CoachTriggerPill } from "@/components/coach/CoachTriggerPill";
import {
  setCoachChoiceLetter,
  setCoachPin,
} from "@/components/coach/coach_thread_store";
import {
  getShellLayoutSnapshot,
  setPanelDismissed,
  subscribeShellLayout,
} from "@/components/shell/shell_layout_store";
import {
  coachMode,
  RAIL_COLLAPSED,
  useSurface,
} from "@/components/shell/use_surface";
import {
  isNoContentError,
  isPoolExhaustedError,
  isResumeExhaustedError,
  useQuiz,
  type QuizItemResult,
} from "@/components/quiz/use_quiz";
import { durableEngineEnabled } from "@/lib/adapters/engine/engine_client";
import { resolveQuizOpenMode } from "@/components/quiz/resolve_focus_mode";
import { toQuizCoachPin } from "@/components/quiz/quiz_coach_pin";
import {
  QuizNoContentState,
  QuizPersistErrorBanner,
} from "@/components/quiz/QuizDurableStates";
import { buildFeedback } from "@/components/feedback/use_feedback";
import {
  initialQuizScreen,
  quizScreenReducer,
  elapsedMsFrom,
} from "@/components/quiz/quiz_screen_reducer";
import {
  clearActiveQuiz,
  readActiveQuiz,
  setActiveQuiz,
  stashQuizSession,
} from "@/components/quiz/quiz_session_store";
import { toQuizItemVM } from "@/lib/translators/quiz_item_vm";
import { toQuizProgressVM } from "@/lib/translators/quiz_progress_vm";
import { resolveHintChoiceLetter } from "@/lib/translators/resolve_hint_choice_letter";
import { resolveCommitFirstLadder } from "@/lib/translators/resolve_commit_first_ladder";
import { EnvVarFlagsAdapter } from "@/lib/adapters/feature_flags/env_var_flags_adapter";
import { screen } from "@/components/shell/nav_model";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";
import type { QuizSession, Skill } from "@/lib/wire/engine_entities";

/** Sync flag snapshot for the quiz page (FR-14). Composition-ring adapter. */
function readCommitFirstCoachFlag(): boolean {
  return new EnvVarFlagsAdapter({
    env: {
      NEXT_PUBLIC_FF_COMMIT_FIRST_COACH:
        process.env.NEXT_PUBLIC_FF_COMMIT_FIRST_COACH,
      E2E_BYPASS_AUTH: process.env.E2E_BYPASS_AUTH,
      NODE_ENV: process.env.NODE_ENV,
    },
  }).isEnabled("commit_first_coach");
}

/**
 * A Socratic nudge derived from the stem — deliberately generic so it never
 * names the answer (FR-D5 non-reveal). The real per-item hint is a later content
 * seam (ContentRepo); this keeps the hint control honest and answer-free now.
 */
function socraticHint(stem: string): string {
  return `Before you pick: what is the sentence actually asking? Re-read it — "${stem}"`;
}

export default function QuizPage(): React.JSX.Element {
  const { learnerId } = useLearnIdentity();
  const {
    openSession,
    openItem,
    resumeSession,
    planAnswer,
    submit,
    escape,
    closeSession,
    listSkillIds,
    listSkills,
    loadLadder,
    recordPointer,
  } = useQuiz();
  const commitFirstCoach = React.useMemo(() => readCommitFirstCoachFlag(), []);
  const router = useRouter();
  const searchParams = useSearchParams();
  // FR-A5 / S2 (FR-6): `?focus=<skillId>` → drill. FR-A6 / FR-C5: `?mode=review`
  // → miss-pool session (Dashboard "Review my misses").
  const focusParam = searchParams.get("focus");
  const modeParam = searchParams.get("mode");
  // Deep-link intent: open the requested mode, do not resume a prior adaptive walk.
  const wantsFreshSession =
    modeParam === "review" || (focusParam != null && focusParam.length > 0);
  // ADR-0035 Direction 2b: quiz host switches on coachMode (not pin ladder).
  // Content screens always mount with 64px rail — pass RAIL_COLLAPSED.
  const surface = useSurface();
  const [viewportWidth, setViewportWidth] = React.useState(1200);
  React.useEffect(() => {
    const measure = () => setViewportWidth(window.innerWidth);
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  const mode = coachMode(surface, viewportWidth, RAIL_COLLAPSED);
  const coachRuntime = React.useMemo(
    () =>
      mode === "fullscreen"
        ? null
        : buildBrowserRuntimeClient({ baseUrl: "/api/coach" }),
    [mode],
  );
  const shellLayout = React.useSyncExternalStore(
    subscribeShellLayout,
    getShellLayoutSnapshot,
    getShellLayoutSnapshot,
  );
  const composerFocusRef = React.useRef<HTMLTextAreaElement | null>(null);
  const pillRef = React.useRef<HTMLButtonElement | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [state, dispatch] = React.useReducer(
    quizScreenReducer,
    initialQuizScreen,
  );

  // v3: open the coach as soon as a wrong commit starts the ladder (MOM-3).
  const coachedLoopActive =
    commitFirstCoach &&
    state.phase === "answering" &&
    state.coachedLoop != null;
  React.useEffect(() => {
    if (!coachedLoopActive) return;
    setDrawerOpen(true);
    if (shellLayout.panelDismissed) setPanelDismissed(false);
  }, [coachedLoopActive, shellLayout.panelDismissed]);

  // The open session (+ its id, the Summary handoff key) for the page's life.
  const [session, setSession] = React.useState<QuizSession | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  /** FR-G3: empty content tables → dedicated empty state (not a crash alert). */
  const [noContent, setNoContent] = React.useState(false);
  /**
   * FR-A8: write failed after optimistic verdict — hold UI, block advance.
   * Cleared on successful retry or next item.
   */
  const [persistError, setPersistError] = React.useState<string | null>(null);
  const [persistPending, setPersistPending] = React.useState(false);
  const closingSessionRef = React.useRef<string | null>(null);
  /**
   * FR-A9.1 / FR-A8: one answer-action payload above the retry boundary.
   * Retry resends the same idempotency key + the original first/coached flags
   * (re-deriving from post-optimistic state would flip isFirstGradedAttempt).
   */
  const pendingAnswerRef = React.useRef<{
    idempotencyKey: string;
    letter: string;
    question: QuizItemResult["question"];
    usedHint: boolean;
    elapsedMs: number;
    isFirstGradedAttempt: boolean;
    hadPriorWrongAttempts: boolean;
  } | null>(null);
  // D1 Q-7: full Skill rows for the chip join (name + accent_var).
  const [skillsById, setSkillsById] = React.useState<
    ReadonlyMap<string, Skill>
  >(new Map());

  const progressVm = toQuizProgressVM(
    state.score.total,
    state.phase,
    session?.target_count ?? null,
  );

  const closeAndRouteToSummary = React.useCallback(() => {
    if (session == null || closingSessionRef.current === session.id) return;
    closingSessionRef.current = session.id;
    dispatch({ type: "finish" });
    closeSession({
      sessionId: session.id,
      scoreCorrect: state.score.correct,
      scoreTotal: state.score.total,
    })
      .then(() => {
        clearActiveQuiz();
        router.push(`${screen("summary").route}?session=${session.id}`);
      })
      .catch((err: unknown) => {
        closingSessionRef.current = null;
        setError(
          err instanceof Error ? err.message : "Failed to close the session",
        );
      });
  }, [session, state.score, closeSession, router]);

  // FR-C1/C1a/C2: completion is keyed to the resolution tally, then waits for
  // the optimistic attempt write to land before server-tally close + summary.
  // A wrong first grade on Q30 does not increment total, so coaching stays open.
  React.useEffect(() => {
    if (!progressVm.complete || persistPending || persistError != null) return;
    closeAndRouteToSummary();
  }, [
    progressVm.complete,
    persistPending,
    persistError,
    closeAndRouteToSummary,
  ]);

  // Effect 1: resume OR open a fresh session.
  // Durable (FR-B1/B3/B6): GET /session/active — ignore RAM for position; deep
  // links (?mode=review / ?focus=) always open fresh. Flag-off keeps FLAG-4 RAM
  // resume. Stale/missing → clear + fresh (FR-B5 / FR-4).
  // D1: listSkills warms the Q-7 chip join (resume + fresh paths).
  React.useEffect(() => {
    let cancelled = false;

    async function start(): Promise<void> {
      void listSkills(DEFAULT_SUBJECT).then((skills) => {
        if (!cancelled) {
          setSkillsById(new Map(skills.map((s) => [s.id, s])));
        }
      });

      if (!wantsFreshSession) {
        if (durableEngineEnabled()) {
          try {
            const resumed = await resumeSession({ subject: DEFAULT_SUBJECT });
            if (cancelled) return;
            if (resumed != null) {
              setSession(resumed.session);
              dispatch({
                type: "resume_item",
                item: resumed.item,
                // FR-B10: server commit-first tally — never re-count client-side.
                score: resumed.score ?? { correct: 0, total: 0 },
                presentedAt: performance.now(),
              });
              return;
            }
          } catch (err: unknown) {
            if (cancelled) return;
            if (isNoContentError(err)) {
              setNoContent(true);
              return;
            }
            if (isResumeExhaustedError(err)) {
              // FR-C5 at mount: open session, pool gone → close to summary.
              setSession(err.session);
              closingSessionRef.current = err.session.id;
              dispatch({ type: "finish" });
              closeSession({
                sessionId: err.session.id,
                scoreCorrect: err.score.correct,
                scoreTotal: err.score.total,
              })
                .then(() => {
                  clearActiveQuiz();
                  router.push(
                    `${screen("summary").route}?session=${err.session.id}`,
                  );
                })
                .catch((closeErr: unknown) => {
                  closingSessionRef.current = null;
                  setError(
                    closeErr instanceof Error
                      ? closeErr.message
                      : "Failed to close the session",
                  );
                });
              return;
            }
            throw err;
          }
        } else {
          const pointer = readActiveQuiz();
          if (pointer != null) {
            const resumed = await resumeSession({
              sessionId: pointer.sessionId,
              questionId: pointer.questionId,
            });
            if (cancelled) return;
            if (resumed != null) {
              setSession(resumed.session);
              const feedback =
                pointer.phase === "feedback" &&
                pointer.verdict != null &&
                pointer.answeredLetter != null
                  ? {
                      verdict: pointer.verdict,
                      answeredLetter: pointer.answeredLetter,
                      usedHint: pointer.usedHint ?? false,
                    }
                  : undefined;
              dispatch({
                type: "resume_item",
                item: resumed.item,
                score: { correct: pointer.correct, total: pointer.total },
                presentedAt: performance.now(),
                ...(feedback != null ? { feedback } : {}),
              });
              return;
            }
            // FR-4: session/question gone — honest recovery, never fabricate.
            clearActiveQuiz();
          }
        }
      }
      if (wantsFreshSession) {
        clearActiveQuiz();
      }

      const skillIds = await listSkillIds(DEFAULT_SUBJECT);
      if (cancelled) return;
      const openMode = resolveQuizOpenMode(
        { mode: modeParam, focus: focusParam },
        skillIds,
      );
      const opened = await openSession({
        subject: DEFAULT_SUBJECT,
        learnerId,
        ...openMode,
      });
      if (cancelled || opened == null) return;
      stashQuizSession(opened.session.id, opened.skillStateAtStart);
      setSession(opened.session);
    }

    start().catch((err: unknown) => {
      if (!cancelled) {
        setError(
          err instanceof Error ? err.message : "Failed to start the session",
        );
      }
    });
    return () => {
      cancelled = true;
    };
  }, [
    openSession,
    resumeSession,
    closeSession,
    listSkillIds,
    listSkills,
    focusParam,
    modeParam,
    wantsFreshSession,
    learnerId,
    router,
  ]);

  // Effect 2: whenever we enter `loading` (initial + after Next) and a session
  // exists, fetch the next scheduled item and fold it into the phase machine.
  // Skipped on FLAG-4 resume (resume_item lands in answering, not loading).
  React.useEffect(() => {
    if (session == null || state.phase !== "loading") return;
    let cancelled = false;
    // S3: pass the session id so openItem derives this session's served-ids and
    // never re-serves a question already answered this session (FR-9/FR-13).
    openItem({ subject: DEFAULT_SUBJECT, learnerId, sessionId: session.id })
      .then((item) => {
        // D0 elapsed timing: stamp the monotonic clock the moment the item is
        // presented (clock start); onSubmit stops it to record a real elapsed_ms.
        if (!cancelled) {
          pendingAnswerRef.current = null;
          setPersistError(null);
          setPersistPending(false);
          setNoContent(false);
          dispatch({
            type: "item_loaded",
            item,
            presentedAt: performance.now(),
          });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          // FR-G3: empty bank → dedicated empty state, not a broken quiz.
          if (isNoContentError(err)) {
            setNoContent(true);
            return;
          }
          // G9: this catches the specific finite-pool exhaustion signal. Closing
          // is correct because no further item can resolve in this session.
          if (isPoolExhaustedError(err)) {
            closeAndRouteToSummary();
            return;
          }
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load the next question",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [
    session,
    state.phase,
    openItem,
    learnerId,
    closeAndRouteToSummary,
  ]);

  // Effect 3: keep the in-tab active pointer current while Quiz is live (FR-1).
  // Retained across unmount so Coach ← Back can resume; cleared only on Finish.
  // Feedback stash includes verdict + letter so remount restores reviewing (same N).
  // FR-B3a: on entering answering, also fire-and-forget POST /session/current
  // (failure must not block the serve — FR-B3a-nonblock).
  React.useEffect(() => {
    if (session == null) return;
    if (state.phase !== "answering" && state.phase !== "reviewing") return;
    const progressVm = toQuizProgressVM(
      state.score.total,
      state.phase,
      session.target_count ?? null,
    );
    if (state.phase === "reviewing") {
      setActiveQuiz({
        sessionId: session.id,
        questionId: state.item.question.id,
        position: progressVm.position,
        correct: state.score.correct,
        total: state.score.total,
        phase: "feedback",
        verdict: state.verdict,
        answeredLetter: state.answeredLetter,
        usedHint: state.usedHint,
      });
      return;
    }
    setActiveQuiz({
      sessionId: session.id,
      questionId: state.item.question.id,
      position: progressVm.position,
      correct: state.score.correct,
      total: state.score.total,
      phase: "answering",
    });
    recordPointer(session.id, state.item.question.id);
  }, [session, state, recordPointer]);

  // Effect 4: iPhone has no CoachPanel — keep coach_thread_store pin aligned
  // with the live item so sidebar "Coach" matches Ask-the-coach (not cold/stale Q1).
  // Wide CoachPanel already writes the same store; skip to avoid a duplicate path.
  React.useEffect(() => {
    if (coachRuntime != null) return;
    if (session == null) return;
    if (state.phase !== "answering" && state.phase !== "reviewing") return;
    const progressVm = toQuizProgressVM(
      state.score.total,
      state.phase,
      session.target_count ?? null,
    );
    const { pin, mode } = toQuizCoachPin({
      questionId: state.item.question.id,
      skillId: state.item.question.skill_id,
      skillName: skillsById.get(state.item.question.skill_id)?.name ?? null,
      position: progressVm.position,
      phase: state.phase,
    });
    setCoachPin(pin, mode);
  }, [coachRuntime, session, state]);

  // Effect 5: ADR-0035 moment router — wrong letter → choice-conditional ladder
  // + coach_context.choice_letter; no/correct pick → item-level (null letter).
  // Commit-first (FR-2/3): key off the *submitted* wrong letter (coachedLoop),
  // not the pre-submit selection — so no ladder loads before a commit.
  const momentLetter =
    state.phase === "answering"
      ? commitFirstCoach
        ? (state.coachedLoop?.activeLetter ?? null)
        : state.selectedLetter
      : state.phase === "reviewing"
        ? state.answeredLetter
        : null;
  const momentQuestionId =
    state.phase === "answering" || state.phase === "reviewing"
      ? state.item.question.id
      : null;
  const momentAnswerLetter =
    state.phase === "answering" || state.phase === "reviewing"
      ? state.item.question.answer_letter
      : null;
  const momentStem =
    state.phase === "answering" || state.phase === "reviewing"
      ? state.item.question.stem
      : null;
  React.useEffect(() => {
    if (
      session == null ||
      momentQuestionId == null ||
      momentAnswerLetter == null
    ) {
      return;
    }
    // Commit-first pre-submit: no letter committed → no ladder load (FR-2).
    if (
      commitFirstCoach &&
      state.phase === "answering" &&
      momentLetter == null
    ) {
      setCoachChoiceLetter(null);
      return;
    }
    const choice = resolveHintChoiceLetter(momentLetter, momentAnswerLetter);
    setCoachChoiceLetter(choice);
    let cancelled = false;
    const load = (letter: string | null) =>
      loadLadder(DEFAULT_SUBJECT, momentQuestionId, letter);
    const ladderPromise =
      commitFirstCoach && choice != null && momentStem != null
        ? resolveCommitFirstLadder(
            load,
            choice,
            socraticHint(momentStem),
            momentQuestionId,
            DEFAULT_SUBJECT,
          )
        : load(choice);
    ladderPromise
      .then((hintLadder) => {
        if (!cancelled)
          dispatch({
            type: "ladder_loaded",
            hintLadder,
            // G8 race guard: tag this load with the letter it was loaded for,
            // so a slow L1 load arriving after a switch to L2 is ignored.
            forLetter: choice,
          });
      })
      .catch(() => {
        // Ladder reload is best-effort: keep the open-time item-level ladder.
      });
    return () => {
      cancelled = true;
    };
  }, [
    session,
    momentLetter,
    momentQuestionId,
    momentAnswerLetter,
    momentStem,
    loadLadder,
    commitFirstCoach,
    state.phase,
  ]);

  const persistAnswer = React.useCallback(
    (args: {
      letter: string;
      idempotencyKey: string;
      question: QuizItemResult["question"];
      usedHint: boolean;
      elapsedMs: number;
      isFirstGradedAttempt: boolean;
      hadPriorWrongAttempts: boolean;
    }) => {
      if (session == null) return;
      setPersistPending(true);
      setPersistError(null);
      submit({
        session,
        question: args.question,
        learnerId,
        letter: args.letter,
        elapsedMs: args.elapsedMs,
        usedHint: args.usedHint,
        idempotencyKey: args.idempotencyKey,
        ...(commitFirstCoach
          ? {
              commitFirstCoach: true,
              isFirstGradedAttempt: args.isFirstGradedAttempt,
              hadPriorWrongAttempts: args.hadPriorWrongAttempts,
            }
          : {}),
      })
        .then(() => {
          // FR-A5 complete: durable write landed. Clear retry payload.
          pendingAnswerRef.current = null;
          setPersistPending(false);
          setPersistError(null);
        })
        .catch((err: unknown) => {
          // FR-A8: keep optimistic verdict; block advance; offer retry.
          setPersistPending(false);
          setPersistError(
            err instanceof Error
              ? err.message
              : "Failed to save your answer",
          );
        });
    },
    [session, submit, commitFirstCoach, learnerId],
  );

  const onSubmit = React.useCallback(() => {
    if (state.phase !== "answering" || session == null) return;
    if (persistPending) return;
    const letter = state.selectedLetter;
    // FR-7: same-letter resubmit is inert — skip record before it reaches the repo.
    if (
      commitFirstCoach &&
      letter != null &&
      state.coachedLoop?.activeLetter === letter
    ) {
      return;
    }
    const { question } = state.item;
    // FR-A7: grade sync first so the verdict can paint before the write.
    // FR-A9.1: mint the key once above the retry boundary (reuse on FR-A8 retry).
    const plan = planAnswer({
      question,
      letter,
      ...(pendingAnswerRef.current != null
        ? { idempotencyKey: pendingAnswerRef.current.idempotencyKey }
        : {}),
    });
    if (plan == null) return;

    const usedHint = state.usedHint || state.coachedLoop != null;
    const elapsedMs = elapsedMsFrom(state.presentedAt, performance.now());
    const isFirstGradedAttempt = state.coachedLoop == null;
    const hadPriorWrongAttempts =
      state.coachedLoop != null && state.coachedLoop.wrongLetters.length > 0;

    pendingAnswerRef.current = {
      idempotencyKey: plan.idempotencyKey,
      letter: plan.letter,
      question,
      usedHint,
      elapsedMs,
      isFirstGradedAttempt,
      hadPriorWrongAttempts,
    };

    // Optimistic: show verdict immediately (FR-A7), then persist (FR-A5).
    dispatch({
      type: "submitted",
      verdict: plan.verdict,
      letter: plan.letter,
      ...(commitFirstCoach ? { commitFirstCoach: true } : {}),
    });
    persistAnswer(pendingAnswerRef.current);
  }, [
    state,
    session,
    planAnswer,
    persistAnswer,
    persistPending,
    commitFirstCoach,
  ]);

  const onRetryPersist = React.useCallback(() => {
    if (session == null || persistPending) return;
    const pending = pendingAnswerRef.current;
    if (pending == null) return;
    persistAnswer(pending);
  }, [session, persistPending, persistAnswer]);

  const onNudge = React.useCallback(() => {
    dispatch({ type: "nudge_requested" });
  }, []);

  const onTryAgain = React.useCallback(() => {
    dispatch({ type: "try_again" });
  }, []);

  const onSeeBreakdown = React.useCallback(() => {
    dispatch({ type: "see_breakdown" });
  }, []);

  const onEscape = React.useCallback(() => {
    if (state.phase !== "answering" || session == null) return;
    const lastWrong = state.coachedLoop?.activeLetter;
    if (lastWrong == null) return;
    const elapsedMs = elapsedMsFrom(state.presentedAt, performance.now());
    escape({
      session,
      question: state.item.question,
      learnerId,
      lastWrongLetter: lastWrong,
      elapsedMs,
      usedHint: true,
      isFirstGradedAttempt: false,
    })
      .then(() => {
        dispatch({ type: "escape_taken" });
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to walk through the item",
        );
      });
  }, [state, session, escape, learnerId]);

  const onFinish = React.useCallback(() => {
    closeAndRouteToSummary();
  }, [closeAndRouteToSummary]);

  // D1 Q-8: End session — same close-with-tally as Finish. G2 (SUM-1
  // reachability): under commit-first with ≥1 resolved item, route to the
  // summary view (score + outcome counts + misconception); 0 resolved →
  // dashboard (today's behavior). Flag-OFF path unchanged — legacy end-session
  // keeps routing to /learn (FR-Q8-6), so the flag-OFF e2e stays green.
  const onEndSession = React.useCallback(() => {
    if (session == null) return;
    dispatch({ type: "end_session" });
    const { correct, total } = state.score;
    const routeToSummary = commitFirstCoach && total > 0;
    closeSession({
      sessionId: session.id,
      scoreCorrect: correct,
      scoreTotal: total,
    })
      .then(() => {
        router.push(
          routeToSummary
            ? `${screen("summary").route}?session=${session.id}`
            : screen("dashboard").route,
        );
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to end the session",
        );
      });
  }, [session, state.score, closeSession, router, commitFirstCoach]);

  if (error != null) {
    return (
      <p role="alert" className="text-danger">
        {error}
      </p>
    );
  }

  if (noContent) {
    return <QuizNoContentState />;
  }

  if (state.phase === "loading" || state.phase === "done") {
    return (
      <p role="status" className="text-muted">
        Loading your next question&hellip;
      </p>
    );
  }

  // FR-A5/A8: Next/Finish stay disabled until the optimistic write lands (or
  // the learner retries successfully). Verdict remains visible (no rollback).
  const advanceBlocked = persistPending || persistError != null;

  const endSessionEnabled =
    session != null &&
    !progressVm.complete &&
    (state.phase === "answering" || state.phase === "reviewing");
  const startedAtIso = session?.started_at ?? null;

  // FR-C2/C3: pre-target controls retain their behavior, but completion is a
  // hard stop. The auto-close Effect owns the target boundary, so no Q31 action
  // or "Keep practising" continuation is rendered.
  // V29 (v3-prototype parity): the SAME controls render in the coached-solve
  // confirm state on the item column, so a coached correct is never a dead end.
  const advanceControls = (
    <div className="flex flex-col gap-3">
      {persistError != null ? (
        <QuizPersistErrorBanner
          message={persistError}
          onRetry={onRetryPersist}
          retrying={persistPending}
        />
      ) : null}
      <div className="flex items-center justify-between gap-3">
        {!progressVm.complete ? (
          <button
            type="button"
            data-testid="quiz-next"
            disabled={advanceBlocked}
            onClick={() => {
              if (advanceBlocked) return;
              pendingAnswerRef.current = null;
              setPersistError(null);
              dispatch({ type: "next" });
            }}
            className="rounded-full bg-accent px-6 py-3 font-semibold text-on-accent disabled:opacity-50"
          >
            Next question →
          </button>
        ) : null}
        {!progressVm.complete ? (
          <button
            type="button"
            data-testid="quiz-finish"
            disabled={advanceBlocked}
            onClick={() => {
              if (advanceBlocked) return;
              onFinish();
            }}
            className="rounded-full border border-border px-6 py-3 font-medium hover:bg-selected disabled:opacity-50"
          >
            Finish & see summary
          </button>
        ) : null}
      </div>
    </div>
  );

  let item: QuizItemResult;
  let content: React.JSX.Element;
  if (state.phase === "answering") {
    item = state.item;
    const vm = toQuizItemVM(state.item.question, skillsById);
    // V29 (v3-prototype parity): a coached solve confirms in place (FR-15) but is
    // SOLVED — the prototype shows "Next question →" on the item column in this
    // state (`showContinue = s.solved`), so the learner is never stuck on a
    // solved item with no forward control. The breakdown stays an opt-in in the
    // coach panel; these controls are the direct advance the panel lacked.
    content = (
      <div className="mx-auto flex max-w-[760px] flex-col gap-6">
        <QuizView
          key={state.item.question.id}
          vm={vm}
          selectedLetter={state.selectedLetter}
          onSelect={(letter) => dispatch({ type: "select", letter })}
          onSubmit={onSubmit}
          hintOpen={state.hintOpen}
          // ADR-0014 (FR-D5/FR-20): the reviewed ladder's probe rung when one
          // exists; the generic stem nudge only as the no-ladder fallback.
          hint={
            state.item.hintLadder[0]?.body_md ??
            socraticHint(state.item.question.stem)
          }
          onToggleHint={() => dispatch({ type: "toggle_hint" })}
          endSessionEnabled={endSessionEnabled && !advanceBlocked}
          onEndSession={onEndSession}
          startedAtIso={startedAtIso}
          commitFirstCoach={commitFirstCoach}
          coachedLoop={state.coachedLoop}
          coachedConfirm={state.coachedConfirm}
          hintLadder={state.item.hintLadder}
          onNudge={onNudge}
          onTryAgain={onTryAgain}
          onEscape={onEscape}
          onSeeBreakdown={onSeeBreakdown}
          // Fullscreen has no CoachPanel — keep the ladder on the item column.
          renderCoachedInline={mode === "fullscreen" || coachRuntime == null}
          ackQuestion={state.item.question}
          whyItemPosition={progressVm.position}
          whyItemTotal={progressVm.total}
        />
        {/* FR-A8: wrong-path coached loop has no Next yet — still surface retry. */}
        {persistError != null && state.coachedConfirm == null ? (
          <QuizPersistErrorBanner
            message={persistError}
            onRetry={onRetryPersist}
            retrying={persistPending}
          />
        ) : null}
        {state.coachedConfirm != null ? advanceControls : null}
      </div>
    );
  } else {
    // reviewing — Feedback is a Quiz sub-state (OD-5), rendered inline with the
    // post-answer actions (Next / Finish). D1 frame chrome sits ABOVE feedback
    // so the chip / End / timer persist across answering→reviewing (FR-Q7-4,
    // FR-Q8-3); keyed by question id so the timer reveal resets on Next (FR-Q9-7).
    item = state.item;
    const itemVm = toQuizItemVM(state.item.question, skillsById);
    const feedback = buildFeedback(
      state.item.question,
      state.verdict,
      { letter: state.answeredLetter },
      state.resolution,
      { skillName: itemVm.skillName },
    );
    // FR-16/17/18: inline pin+focus; drawer open then focus after 220ms; iphone navigate.
    // ADR-0035 (main): pin the wrong letter so the free-ask coach loads the
    // choice-conditional ladder, regardless of which surface branch serves it.
    const onAskCoach = feedback.present
      ? () => {
          const { pin, mode: coachPinMode } = toQuizCoachPin({
            questionId: feedback.askCoachContext.questionId,
            skillId: feedback.askCoachContext.skillId,
            skillName:
              skillsById.get(feedback.askCoachContext.skillId)?.name ?? null,
            position: progressVm.position,
            phase: "reviewing",
          });
          setCoachPin(pin, coachPinMode);
          setCoachChoiceLetter(
            resolveHintChoiceLetter(
              state.answeredLetter,
              state.item.question.answer_letter,
            ),
          );
          if (mode === "fullscreen") {
            router.push(screen("coach").route);
            return;
          }
          if (mode === "drawer") {
            setDrawerOpen(true);
            const delay =
              typeof window !== "undefined" &&
              window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
                ? 0
                : 220;
            window.setTimeout(() => {
              composerFocusRef.current?.focus();
            }, delay);
            return;
          }
          // inline
          if (shellLayout.panelDismissed) setPanelDismissed(false);
          requestAnimationFrame(() => {
            composerFocusRef.current?.focus();
          });
        }
      : undefined;
    content = (
      <div className="mx-auto flex max-w-[760px] flex-col gap-6">
        <QuizFrameChrome
          key={state.item.question.id}
          skillName={itemVm.skillName}
          accentVar={itemVm.accentVar}
          endSessionEnabled={endSessionEnabled && !advanceBlocked}
          onEndSession={onEndSession}
          startedAtIso={startedAtIso}
        />
        {feedback.present ? (
          <FeedbackView
            vm={feedback.vm}
            {...(onAskCoach !== undefined ? { onAskCoach } : {})}
          />
        ) : null}
        {advanceControls}
      </div>
    );
  }

  // S4: the "Question N of M" progress bar, above the item in BOTH phases. Reuses
  // `progressVm` (computed above the phase branch so the S5 done-state banner can
  // share it) — read-only, no engine call, FR-9; math is the translator's (F-R1).
  const framed = (
    <div className="flex flex-col gap-5">
      <QuizProgress vm={progressVm} />
      {content}
    </div>
  );

  // coachMode switch (FR-1/10/18): inline | drawer | fullscreen (no panel).
  if (coachRuntime != null && mode !== "fullscreen") {
    const coachPin = toQuizCoachPin({
      questionId: item.question.id,
      skillId: item.question.skill_id,
      skillName: skillsById.get(item.question.skill_id)?.name ?? null,
      position: progressVm.position,
      phase: state.phase === "reviewing" ? "reviewing" : "answering",
    });
    const itemMax = surface === "desktop" ? "max-w-[720px]" : "max-w-[560px]";
    const coachedLoop = state.phase === "answering" ? state.coachedLoop : null;
    const coachedConfirm =
      state.phase === "answering" ? state.coachedConfirm : null;
    const panel = (
      <CoachPanel
        key={item.question.id}
        runtime={coachRuntime}
        hintLadder={item.hintLadder}
        mode={coachPin.mode}
        pin={coachPin.pin}
        onDismiss={() => setPanelDismissed(true)}
        composerFocusRef={composerFocusRef}
        inlineHost={mode === "inline"}
        className="h-full rounded-none border-0 border-l border-border"
        commitFirstCoach={commitFirstCoach}
        coachedLoop={coachedLoop}
        coachedConfirm={coachedConfirm}
        onNudge={onNudge}
        onTryAgain={onTryAgain}
        onEscape={onEscape}
        onSeeBreakdown={onSeeBreakdown}
        ackQuestion={item.question}
      />
    );

    if (mode === "drawer") {
      // `relative` hosts CoachDrawer (absolute) so the scrim stays inside main
      // and never intercepts left-rail AppNav clicks (Home / Progress / …).
      return (
        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <div
            className={`mx-auto min-h-0 w-full flex-1 overflow-y-auto overscroll-contain ${itemMax} px-6 pb-12 pt-6`}
          >
            {framed}
          </div>
          {!drawerOpen ? (
            <CoachTriggerPill
              ref={pillRef}
              onClick={() => setDrawerOpen(true)}
            />
          ) : null}
          <CoachDrawer
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            restoreFocusRef={pillRef}
          >
            <CoachPanel
              key={`drawer-${item.question.id}`}
              runtime={coachRuntime}
              hintLadder={item.hintLadder}
              mode={coachPin.mode}
              pin={coachPin.pin}
              composerFocusRef={composerFocusRef}
              className="h-full w-full max-w-none rounded-none border-0"
              commitFirstCoach={commitFirstCoach}
              coachedLoop={coachedLoop}
              coachedConfirm={coachedConfirm}
              onNudge={onNudge}
              onTryAgain={onTryAgain}
              onEscape={onEscape}
              onSeeBreakdown={onSeeBreakdown}
              ackQuestion={item.question}
            />
          </CoachDrawer>
        </div>
      );
    }

    // inline
    return (
      <div className="flex min-h-0 flex-1 items-stretch">
        <div
          className={`min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain`}
        >
          <div className={`mx-auto w-full ${itemMax} px-8 pb-12 pt-8`}>
            {framed}
          </div>
        </div>
        {shellLayout.panelDismissed ? null : panel}
      </div>
    );
  }
  return framed;
}
