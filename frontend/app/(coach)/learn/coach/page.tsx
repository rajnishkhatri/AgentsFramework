// B1 + BP-1.5 + BP-2: 'use client' — Coach screen drives a live SSE run via
// useCoach() (F-R1); this page is thin glue: surface → layout, Back/Wrap-up
// nav (C2), store pin → chrome (C1), CoachWorkspace composition.
//
// Runtime streams from `/api/coach/run/stream`. No SDK import here (F-R2).
"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { buildBrowserRuntimeClient } from "@/lib/composition_browser";
import { CoachWorkspace } from "@/components/coach/CoachWorkspace";
import { useCoach } from "@/components/coach/use_coach";
import { useCoachSurface } from "@/components/coach/use_coach_surface";
import {
  coachThreadSnapshot,
  subscribeCoachThread,
} from "@/components/coach/coach_thread_store";
import { readActiveQuiz } from "@/components/quiz/quiz_session_store";
import { useSurface } from "@/components/shell/use_surface";
import { screen } from "@/components/shell/nav_model";
import {
  COACH_CHIP_SEEDS,
  toCoachSurfaceVM,
} from "@/lib/translators/coach_surface_vm";
import { honestCoachOpener } from "@/lib/translators/honest_coach_opener";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

export default function CoachPage(): React.JSX.Element {
  const { learnerId } = useLearnIdentity();
  const router = useRouter();
  const surface = useSurface();
  const runtime = React.useMemo(
    () => buildBrowserRuntimeClient({ baseUrl: "/api/coach" }),
    [],
  );
  const { countMissesOnSkill, skillNameById } = useCoachSurface();

  const snap = React.useSyncExternalStore(
    subscribeCoachThread,
    coachThreadSnapshot,
    coachThreadSnapshot,
  );
  const pin = snap.pin;
  const mode = snap.mode;

  const { turns, busy, ask, retry } = useCoach(runtime, { mode });

  const [missesOnSkill, setMissesOnSkill] = React.useState<number | null>(null);
  // C-3: resolve the pinned skillId to a friendly name so the history line reads
  // "Commas" not a raw "s-gram" id. null while resolving / when unresolved —
  // the VM falls back to omitting the label, never echoing the raw id.
  const [skillLabel, setSkillLabel] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    if (pin?.skillId == null) {
      setMissesOnSkill(null);
      setSkillLabel(null);
      return;
    }
    void countMissesOnSkill({
      subject: DEFAULT_SUBJECT,
      learnerId,
      skillId: pin.skillId,
    }).then((n) => {
      if (!cancelled) setMissesOnSkill(n);
    });
    void skillNameById(DEFAULT_SUBJECT, pin.skillId).then((name) => {
      if (!cancelled) setSkillLabel(name);
    });
    return () => {
      cancelled = true;
    };
  }, [
    pin?.skillId,
    pin?.kind === "item" ? pin.questionId : null,
    countMissesOnSkill,
    skillNameById,
    learnerId,
  ]);

  const surfaceVm = React.useMemo(
    () =>
      toCoachSurfaceVM({
        mode,
        pin,
        missesOnSkill,
        skillLabel,
        chipSeeds: COACH_CHIP_SEEDS,
      }),
    [mode, pin, missesOnSkill, skillLabel],
  );

  const layout = surface === "desktop" ? "rail" : "strip";

  const openerMarkdown = React.useMemo(
    () =>
      honestCoachOpener({
        pin,
        missesOnSkill,
        transcriptEmpty: turns.length === 0,
      }),
    [pin, missesOnSkill, turns.length],
  );

  const onBack = React.useCallback(() => {
    // D-F b (FLAG-4): "Back" resumes practice where the learner left off, NOT the
    // browser's previous entry. `router.back()` lands on Feedback when the coach
    // was reached via Feedback→Ask-the-coach — it does not honor "resume the item
    // I left". Pushing the bare quiz route triggers the quiz page's active-pointer
    // resume (Effect 1: readActiveQuiz → resumeSession restores the left item,
    // feedback phase included). No `?focus=`, so it resumes rather than drills.
    router.push(screen("quiz").route);
  }, [router]);

  const onWrapUp = React.useCallback(() => {
    // C2 FR-18: append ?session=<id> when continuity-fixes substrate is present;
    // FR-4 honest recovery — fall back to bare summary when readActiveQuiz null.
    const sessionId = readActiveQuiz()?.sessionId;
    const base = screen("summary").route;
    router.push(sessionId ? `${base}?session=${sessionId}` : base);
  }, [router]);

  return (
    <CoachWorkspace
      vm={surfaceVm}
      turns={turns}
      busy={busy}
      onAsk={ask}
      onRetry={retry}
      onBack={onBack}
      onWrapUp={onWrapUp}
      layout={layout}
      openerMarkdown={openerMarkdown}
    />
  );
}
