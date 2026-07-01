// B1: 'use client' required — the Summary reads the engine bag from useEngine()
// context (the browser-safe InMemoryEngineDb substrate, ADR-0005 local-first) via
// useSummary(), reads the session id from the URL, and loads the VM on mount. The
// domain logic (stored-score read + mastery delta + recommended-next pick) lives
// in loadSummary (F-R1); this page is thin glue that renders the loaded SummaryVM.
//
// Session-resume limitation (ADR-0011 §4): a Summary reached by reload/deep-link
// has no in-memory `skillStateAtStart` snapshot, so the mastery-delta tile renders
// "—". Within an unbroken session the snapshot is carried from openQuizSession; a
// persisted snapshot is a later decision (ADR-0011 §4 decision trigger).
"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { SummaryView } from "@/components/summary/SummaryView";
import { useSummary, type SummaryVM } from "@/components/summary/use_summary";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";
import type { SkillState } from "@/lib/wire/engine_entities";

// Phase-1 single-learner surface (the plan's "Maya"); see the dashboard page note.
const LEARNER_ID = "maya";

export default function SummaryPage(): React.JSX.Element {
  const { load } = useSummary();
  const params = useSearchParams();
  const sessionId = params.get("session");
  const [vm, setVm] = React.useState<SummaryVM | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (sessionId == null) {
      setError("No session to summarize.");
      return;
    }
    // Sync to the async engine read on mount (sanctioned useEffect §14: an
    // external, non-React data source). `cancelled` guards a late resolve after
    // unmount. The start snapshot is empty here — a fresh page load lost it
    // (ADR-0011 §4), so the delta renders "—".
    let cancelled = false;
    setError(null);
    const emptySnapshot: ReadonlyMap<string, SkillState> = new Map();
    load({
      subject: DEFAULT_SUBJECT,
      learnerId: LEARNER_ID,
      sessionId,
      skillStateAtStart: emptySnapshot,
      nowISO: new Date().toISOString(),
    })
      .then((next) => {
        if (!cancelled) setVm(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load summary");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [load, sessionId]);

  if (error != null) {
    return (
      <p role="alert" className="text-danger">
        {error}
      </p>
    );
  }
  if (vm == null) {
    return (
      <p role="status" className="text-muted">
        Loading your summary&hellip;
      </p>
    );
  }
  return <SummaryView vm={vm} />;
}
