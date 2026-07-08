// B1: 'use client' required — Test Mode is a live, timed, client-only surface: it
// runs a countdown (browser clock), holds the answers map in a reducer, and grades
// the whole section at submit via the pure engine Grader from useEngine(). The
// domain logic lives in the React-free test_runner_reducer + format_clock + the
// injected Grader (F-R1); this page is the thin glue.
//
// DECOUPLING (plan): Test Mode shares NOTHING with the adaptive /learn/quiz drip —
// no use_quiz, no scheduler, no sessionRepo, no attempt/FSRS write. It reads a
// fixed corpus (the converted Test-01 English section), grades once with the
// stateless Grader, and shows a raw score + official scale band. Grep the imports:
// only the Grader (via useEngine), the wire shapes, and presentational views.
"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useEngine } from "@/app/engine-provider";
import { TestItemView } from "@/components/test/TestItemView";
import { TestResultsView } from "@/components/test/TestResultsView";
import {
  initialTestRunner,
  testRunnerReducer,
  type GradeFn,
} from "@/components/test/test_runner_reducer";
import { useCountdown } from "@/components/test/use_countdown";
import { toQuizItemVM } from "@/lib/translators/quiz_item_vm";
import { COACH_BASE } from "@/components/shell/nav_model";
import {
  TEST01_SERVED_MINUTES,
  TEST01_SERVED_QUESTIONS,
} from "@/lib/adapters/engine/_test01_split";

const SECTION_LABEL = "English";
const FULL_DURATION_MS = TEST01_SERVED_MINUTES * 60_000;

/**
 * Non-prod `?dur=<ms>` override so an e2e spec can drive the countdown to zero in
 * milliseconds (auto-submit) instead of waiting out the section clock. Ignored in
 * prod, and clamped to a sane floor so a stray query can't zero the clock
 * instantly for a real learner in dev. Falls back to the full section duration.
 */
function resolveDurationMs(param: string | null): number {
  if (process.env.NODE_ENV === "production") return FULL_DURATION_MS;
  if (param == null) return FULL_DURATION_MS;
  const parsed = Number(param);
  if (!Number.isFinite(parsed) || parsed <= 0) return FULL_DURATION_MS;
  return parsed;
}

export default function TestModePage(): React.JSX.Element {
  const { grader } = useEngine();
  const searchParams = useSearchParams();
  const durationMs = React.useMemo(
    () => resolveDurationMs(searchParams?.get("dur") ?? null),
    [searchParams],
  );

  const [state, dispatch] = React.useReducer(
    testRunnerReducer,
    TEST01_SERVED_QUESTIONS,
    initialTestRunner,
  );

  // The section grade fn is the pure engine Grader (exact-letter). Stable across
  // renders so the countdown's onExpire callback need not re-arm.
  const grade = React.useCallback<GradeFn>(
    (question, letter) => grader.grade(question, { letter })?.correct === true,
    [grader],
  );

  const submitSection = React.useCallback(() => {
    dispatch({ type: "submit_section", grade });
  }, [grade]);

  // Auto-submit when the countdown reaches zero. The hook fires onExpire once;
  // submit_section is idempotent, so a manual submit landing first is harmless.
  const inSection = state.phase === "in_section";
  const { remainingMs } = useCountdown(durationMs, inSection ? submitSection : undefined);

  if (state.phase === "intro") {
    return (
      <section
        data-testid="test-intro"
        aria-label="Timed test intro"
        className="mx-auto flex max-w-[560px] flex-col gap-5 text-center"
      >
        <h1 className="text-xl font-semibold">Timed {SECTION_LABEL} section</h1>
        <p className="text-muted">
          {TEST01_SERVED_QUESTIONS.length} questions · {TEST01_SERVED_MINUTES} minutes.
          The clock starts when you begin and submits automatically at zero. You can
          revisit and change answers until you submit.
        </p>
        <button
          type="button"
          data-testid="test-start"
          onClick={() => dispatch({ type: "start" })}
          className="mx-auto rounded-full bg-accent px-6 py-3 font-semibold text-white"
        >
          Start the timed section
        </button>
      </section>
    );
  }

  if (state.phase === "results") {
    return (
      <TestResultsView
        correct={state.correct}
        total={state.total}
        sectionLabel={SECTION_LABEL}
        dashboardHref={COACH_BASE}
      />
    );
  }

  // in_section
  const question = state.questions[state.index]!;
  const vm = toQuizItemVM(question);
  const selectedLetter = state.answers[question.id] ?? null;
  const answeredCount = Object.keys(state.answers).length;

  return (
    <TestItemView
      vm={vm}
      selectedLetter={selectedLetter}
      onSelect={(letter) => dispatch({ type: "select", letter })}
      index={state.index}
      count={state.questions.length}
      answeredCount={answeredCount}
      remainingMs={remainingMs}
      sectionLabel={SECTION_LABEL}
      onPrev={() => dispatch({ type: "prev" })}
      onNext={() => dispatch({ type: "next" })}
      onSubmitSection={submitSection}
    />
  );
}
