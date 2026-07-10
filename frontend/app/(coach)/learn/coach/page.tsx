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
import { useSurface } from "@/components/shell/use_surface";
import { screen } from "@/components/shell/nav_model";
import {
  COACH_CHIP_SEEDS,
  toCoachSurfaceVM,
} from "@/lib/translators/coach_surface_vm";
import { honestCoachOpener } from "@/lib/translators/honest_coach_opener";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

const LEARNER_ID = "maya";

export default function CoachPage(): React.JSX.Element {
  const router = useRouter();
  const surface = useSurface();
  const runtime = React.useMemo(
    () => buildBrowserRuntimeClient({ baseUrl: "/api/coach" }),
    [],
  );
  const { countMissesOnSkill } = useCoachSurface();

  const snap = React.useSyncExternalStore(
    subscribeCoachThread,
    coachThreadSnapshot,
    coachThreadSnapshot,
  );
  const pin = snap.pin;
  const mode = snap.mode;

  const { turns, busy, ask, retry } = useCoach(runtime, { mode });

  const [missesOnSkill, setMissesOnSkill] = React.useState<number | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    if (pin?.skillId == null) {
      setMissesOnSkill(null);
      return;
    }
    void countMissesOnSkill({
      subject: DEFAULT_SUBJECT,
      learnerId: LEARNER_ID,
      skillId: pin.skillId,
    }).then((n) => {
      if (!cancelled) setMissesOnSkill(n);
    });
    return () => {
      cancelled = true;
    };
  }, [pin?.skillId, countMissesOnSkill]);

  const surfaceVm = React.useMemo(
    () =>
      toCoachSurfaceVM({
        mode,
        pin,
        missesOnSkill,
        skillLabel: null,
        chipSeeds: COACH_CHIP_SEEDS,
      }),
    [mode, pin, missesOnSkill],
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
    // C2: prefer history; cold-open / no history → quiz.
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push(screen("quiz").route);
  }, [router]);

  const onWrapUp = React.useCallback(() => {
    // C2: summary; session query appended in B2 when quiz session id is known.
    router.push(screen("summary").route);
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
