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
import { QuizView } from "@/components/quiz/QuizView";
import { QuizProgress } from "@/components/quiz/QuizProgress";
import { QuizDoneBanner } from "@/components/quiz/QuizDoneBanner";
import { FeedbackView } from "@/components/feedback/FeedbackView";
import { CoachPanel } from "@/components/coach/CoachPanel";
import { setCoachPin } from "@/components/coach/coach_thread_store";
import { useSurface } from "@/components/shell/use_surface";
import { useQuiz, type QuizItemResult } from "@/components/quiz/use_quiz";
import { resolveQuizOpenMode } from "@/components/quiz/resolve_focus_mode";
import { toQuizCoachPin } from "@/components/quiz/quiz_coach_pin";
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
import { screen } from "@/components/shell/nav_model";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";
import type { QuizSession } from "@/lib/wire/engine_entities";

// Phase-1 single-learner surface (the plan's "Maya"); see the dashboard page note.
const LEARNER_ID = "maya";

/**
 * A Socratic nudge derived from the stem — deliberately generic so it never
 * names the answer (FR-D5 non-reveal). The real per-item hint is a later content
 * seam (ContentRepo); this keeps the hint control honest and answer-free now.
 */
function socraticHint(stem: string): string {
  return `Before you pick: what is the sentence actually asking? Re-read it — "${stem}"`;
}

export default function QuizPage(): React.JSX.Element {
  const { openSession, openItem, resumeSession, submit, closeSession, listSkillIds } =
    useQuiz();
  const router = useRouter();
  const searchParams = useSearchParams();
  // FR-A5 / S2 (FR-6): `?focus=<skillId>` → drill. FR-A6 / FR-C5: `?mode=review`
  // → miss-pool session (Dashboard "Review my misses").
  const focusParam = searchParams.get("focus");
  const modeParam = searchParams.get("mode");
  // Deep-link intent: open the requested mode, do not resume a prior adaptive walk.
  const wantsFreshSession =
    modeParam === "review" || (focusParam != null && focusParam.length > 0);  // FR-J3: on the iPad surface the Quiz renders as a SPLIT — item on the left,
  // the persistent live coach panel on the right, feeding the SAME coach
  // thread as the Coach screen. The coach-pointed runtime is built only when
  // the split is live (page-level composition access, Rule C1).
  const surface = useSurface();
  const coachRuntime = React.useMemo(
    () =>
      surface === "ipad"
        ? buildBrowserRuntimeClient({ baseUrl: "/api/coach" })
        : null,
    [surface],
  );
  const [state, dispatch] = React.useReducer(
    quizScreenReducer,
    initialQuizScreen,
  );

  // The open session (+ its id, the Summary handoff key) for the page's life.
  const [session, setSession] = React.useState<QuizSession | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  // Effect 1: resume an in-tab active pointer (FLAG-4) OR open a fresh session.
  // Resume skips openSession so Coach ← Back restores the left item (FR-3).
  // Stale pointer → clear + fresh open (FR-4). Snapshot stash only on fresh open
  // (resume reuses the snapshot already keyed by sessionId).
  React.useEffect(() => {
    let cancelled = false;

    async function start(): Promise<void> {
      const pointer = readActiveQuiz();
      if (pointer != null && !wantsFreshSession) {
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
            feedback,
          });
          return;
        }
        // FR-4: session/question gone — honest recovery, never fabricate progress.
        clearActiveQuiz();
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
        learnerId: LEARNER_ID,
        ...openMode,
      });
      if (cancelled || opened == null) return;
      stashQuizSession(opened.session.id, opened.skillStateAtStart);
      setSession(opened.session);
    }

    start().catch((err: unknown) => {
      if (!cancelled) {
        setError(err instanceof Error ? err.message : "Failed to start the session");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [openSession, resumeSession, listSkillIds, focusParam, modeParam, wantsFreshSession]);

  // Effect 2: whenever we enter `loading` (initial + after Next) and a session
  // exists, fetch the next scheduled item and fold it into the phase machine.
  // Skipped on FLAG-4 resume (resume_item lands in answering, not loading).
  React.useEffect(() => {
    if (session == null || state.phase !== "loading") return;
    let cancelled = false;
    // S3: pass the session id so openItem derives this session's served-ids and
    // never re-serves a question already answered this session (FR-9/FR-13).
    openItem({ subject: DEFAULT_SUBJECT, learnerId: LEARNER_ID, sessionId: session.id })
      .then((item) => {
        // D0 elapsed timing: stamp the monotonic clock the moment the item is
        // presented (clock start); onSubmit stops it to record a real elapsed_ms.
        if (!cancelled) dispatch({ type: "item_loaded", item, presentedAt: performance.now() });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load the next question");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [session, state.phase, openItem]);

  // Effect 3: keep the in-tab active pointer current while Quiz is live (FR-1).
  // Retained across unmount so Coach ← Back can resume; cleared only on Finish.
  // Feedback stash includes verdict + letter so remount restores reviewing (same N).
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
  }, [session, state]);

  // Effect 4: desktop has no CoachPanel — keep coach_thread_store pin aligned
  // with the live item so sidebar "Coach" matches Ask-the-coach (not cold/stale Q1).
  // iPad CoachPanel already writes the same store; skip to avoid a duplicate path.
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
      position: progressVm.position,
      phase: state.phase,
    });
    setCoachPin(pin, mode);
  }, [coachRuntime, session, state]);

  const onSubmit = React.useCallback(() => {
    if (state.phase !== "answering" || session == null) return;
    const letter = state.selectedLetter;
    const { question } = state.item;
    const usedHint = state.usedHint;
    // D0 elapsed timing: real per-item latency (monotonic stop − start), replacing
    // the former hardcoded `elapsedMs: 0`. Clamped non-negative / whole-ms by the helper.
    const elapsedMs = elapsedMsFrom(state.presentedAt, performance.now());
    submit({
      session,
      question,
      learnerId: LEARNER_ID,
      letter,
      elapsedMs,
      usedHint,
    })
      .then((result) => {
        dispatch({ type: "submitted", verdict: result.verdict, letter });
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to grade your answer");
      });
  }, [state, session, submit]);

  const onFinish = React.useCallback(() => {
    if (session == null) return;
    dispatch({ type: "finish" });
    // Close the session with the running tally BEFORE navigating so the stored
    // score is durably written when the Summary reads it (FR-D3/G1 — Summary
    // never re-tallies). Awaiting avoids a race where the route change reads the
    // session before the close lands. `close` is idempotent. The reducer carried
    // the tally across the whole walk; read it here.
    const { correct, total } = state.score;
    closeSession({ sessionId: session.id, scoreCorrect: correct, scoreTotal: total })
      .then(() => {
        // FR-2: Finish clears the resume pointer; mastery snapshot stays for Summary.
        clearActiveQuiz();
        // The snapshot is already in the store, so the delta renders live (not "—").
        router.push(`${screen("summary").route}?session=${session.id}`);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to close the session");
      });
  }, [session, state.score, closeSession, router]);

  if (error != null) {
    return (
      <p role="alert" className="text-danger">
        {error}
      </p>
    );
  }

  if (state.phase === "loading" || state.phase === "done") {
    return (
      <p role="status" className="text-muted">
        Loading your next question&hellip;
      </p>
    );
  }

  // S4/S5: the progress VM (position + "reached the target?") derived from the
  // reducer tally + the open session's target_count. Computed BEFORE the phase
  // branch so the reviewing branch can read `progressVm.complete` for the S5
  // milestone banner (the threshold math stays in the translator — F-R1). Read-
  // only, no engine call (FR-9). `session` is non-null here (loading/done returned
  // above); `state.score`/`session` are not mutated between here and the render.
  const progressVm = toQuizProgressVM(
    state.score.total,
    state.phase,
    session?.target_count ?? null,
  );

  let item: QuizItemResult;
  let content: React.JSX.Element;
  if (state.phase === "answering") {
    item = state.item;
    const vm = toQuizItemVM(state.item.question);
    content = (
      <QuizView
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
      />
    );
  } else {
    // reviewing — Feedback is a Quiz sub-state (OD-5), rendered inline with the
    // post-answer actions (Next / Finish).
    item = state.item;
    const feedback = buildFeedback(
      state.item.question,
      state.verdict,
      { letter: state.answeredLetter },
    );
    // FR-5 / F-6: desktop Ask-the-coach writes store pin + navigates; iPad
    // already has the live CoachPanel (FR-8 — do not duplicate the bridge).
    const onAskCoach =
      surface !== "ipad" && feedback.present
        ? () => {
            const { pin, mode } = toQuizCoachPin({
              questionId: feedback.askCoachContext.questionId,
              skillId: feedback.askCoachContext.skillId,
              position: progressVm.position,
              phase: "reviewing",
            });
            setCoachPin(pin, mode);
            router.push(screen("coach").route);
          }
        : undefined;
    content = (
      <div className="mx-auto flex max-w-[760px] flex-col gap-6">
        {/* S5 done-state (FR-4/FR-5): once the graded tally reaches the target,
            the milestone shows ABOVE the item's feedback (which stays visible —
            the learner still sees #30's answer). `complete` is the translator's
            call; endless/over-run handled there. */}
        {progressVm.complete ? (
          <QuizDoneBanner targetCount={session?.target_count ?? 0} />
        ) : null}
        {feedback.present ? (
          <FeedbackView vm={feedback.vm} onAskCoach={onAskCoach} />
        ) : null}
        <div className="flex items-center justify-between gap-3">
          {/* S5 (FR-6/FR-7): the two actions keep their ORIGINAL labels
              ("Next question" / "Finish & see summary") for every pre-target
              review, and FLIP to "Keep practising" / "See summary" only once the
              target is reached (gated on `progressVm.complete`, in lock-step with
              the milestone banner — reverted 2026-07-09 from the unconditional
              relabel). Label text is the ONLY thing that changes — testids +
              handlers are unchanged, so S3/S4 selectors and the loop behaviour are
              untouched (FR-10). "Next question"/"Keep practising" both dispatch the
              same `next` (continuing the SAME session; past the target that is
              over-run, tally kept); the finish control closes + routes either way
              (Summary never re-tallies).
              Review sessions (FR-A6): the miss pool is finite — once complete,
              hide "Keep practising" (no over-run) so the learner only sees
              "See summary" instead of an empty-pool error. */}
          {!(session?.mode === "review" && progressVm.complete) ? (
            <button
              type="button"
              data-testid="quiz-next"
              onClick={() => dispatch({ type: "next" })}
              className="rounded-full bg-accent px-6 py-3 font-semibold text-on-accent"
            >
              {progressVm.complete ? "Keep practising" : "Next question →"}
            </button>
          ) : null}
          <button
            type="button"
            data-testid="quiz-finish"
            onClick={onFinish}
            className={
              session?.mode === "review" && progressVm.complete
                ? "rounded-full bg-accent px-6 py-3 font-semibold text-on-accent"
                : "rounded-full border border-border px-6 py-3 font-medium hover:bg-selected"
            }
          >
            {progressVm.complete ? "See summary" : "Finish & see summary"}
          </button>
        </div>
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

  // iPad split (FR-J3): item on the left, the persistent live coach panel on
  // the right. Keyed by question id so the panel's nudge tier resets per item
  // (FR-J3a); the coach THREAD itself lives in coach_thread_store and survives.
  if (coachRuntime != null) {
    const coachPin = toQuizCoachPin({
      questionId: item.question.id,
      skillId: item.question.skill_id,
      position: progressVm.position,
      phase: state.phase === "reviewing" ? "reviewing" : "answering",
    });
    return (
      <div className="flex items-start gap-6">
        <div className="min-w-0 flex-1">{framed}</div>
        <CoachPanel
          key={item.question.id}
          runtime={coachRuntime}
          hintLadder={item.hintLadder}
          mode={coachPin.mode}
          pin={coachPin.pin}
        />
      </div>
    );
  }
  return framed;
}
