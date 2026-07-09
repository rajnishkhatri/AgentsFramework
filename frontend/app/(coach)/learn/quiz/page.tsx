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
import { FeedbackView } from "@/components/feedback/FeedbackView";
import { CoachPanel } from "@/components/coach/CoachPanel";
import { useSurface } from "@/components/shell/use_surface";
import { useQuiz, type QuizItemResult } from "@/components/quiz/use_quiz";
import { resolveFocusMode } from "@/components/quiz/resolve_focus_mode";
import { buildFeedback } from "@/components/feedback/use_feedback";
import {
  initialQuizScreen,
  quizScreenReducer,
  elapsedMsFrom,
} from "@/components/quiz/quiz_screen_reducer";
import { stashQuizSession } from "@/components/quiz/quiz_session_store";
import { toQuizItemVM } from "@/lib/translators/quiz_item_vm";
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
  const { openSession, openItem, submit, closeSession, listSkillIds } = useQuiz();
  const router = useRouter();
  // FR-A5 / S2 (FR-6): a `?focus=<skillId>` deep-link (from the Summary skill
  // name or a Dashboard bucket card) opens the session as a DRILL on that skill.
  // The value is validated against the known skill ids before use; an
  // absent/unknown param falls back to adaptive (resolve_focus_mode).
  const focusParam = useSearchParams().get("focus");
  // FR-J3: on the iPad surface the Quiz renders as a SPLIT — item on the left,
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

  // Effect 1: open the session ONCE and snapshot skill_state at start (§14
  // sanctioned useEffect — an external async data source). The snapshot is
  // stashed for the Summary route; the first item load is triggered by effect 2
  // once the session exists.
  React.useEffect(() => {
    let cancelled = false;
    // FR-6: resolve the `?focus=` param against the known skills, then open a
    // drill (valid focus) or adaptive (absent/unknown). listSkillIds is
    // read-only taxonomy; the decision itself is the pure resolveFocusMode.
    listSkillIds(DEFAULT_SUBJECT)
      .then((skillIds) => {
        if (cancelled) return;
        const focusMode = resolveFocusMode(focusParam, skillIds);
        return openSession({
          subject: DEFAULT_SUBJECT,
          learnerId: LEARNER_ID,
          ...focusMode,
        });
      })
      .then((opened) => {
        if (cancelled || opened == null) return;
        stashQuizSession(opened.session.id, opened.skillStateAtStart);
        setSession(opened.session);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to start the session");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [openSession, listSkillIds, focusParam]);

  // Effect 2: whenever we enter `loading` (initial + after Next) and a session
  // exists, fetch the next scheduled item and fold it into the phase machine.
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
    content = (
      <div className="mx-auto flex max-w-[760px] flex-col gap-6">
        {feedback.present ? <FeedbackView vm={feedback.vm} /> : null}
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            data-testid="quiz-next"
            onClick={() => dispatch({ type: "next" })}
            className="rounded-full bg-accent px-6 py-3 font-semibold text-on-accent"
          >
            Next question →
          </button>
          <button
            type="button"
            data-testid="quiz-finish"
            onClick={onFinish}
            className="rounded-full border border-border px-6 py-3 font-medium hover:bg-selected"
          >
            Finish &amp; see summary
          </button>
        </div>
      </div>
    );
  }

  // iPad split (FR-J3): item on the left, the persistent live coach panel on
  // the right. Keyed by question id so the panel's nudge tier resets per item
  // (FR-J3a); the coach THREAD itself lives in coach_thread_store and survives.
  if (coachRuntime != null) {
    return (
      <div className="flex items-start gap-6">
        <div className="min-w-0 flex-1">{content}</div>
        <CoachPanel
          key={item.question.id}
          runtime={coachRuntime}
          hintLadder={item.hintLadder}
        />
      </div>
    );
  }
  return content;
}
