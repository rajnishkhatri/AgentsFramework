// B1: 'use client' required — the Summary reads the engine bag from useEngine()
// context (the browser-safe InMemoryEngineDb substrate, ADR-0005 local-first) via
// useSummary(), reads the session id from the URL, and loads the VM on mount. The
// domain logic (stored-score read + mastery delta + recommended-next pick) lives
// in loadSummary (F-R1); this page is thin glue that renders the loaded SummaryVM.
//
// Session-resume limitation (ADR-0011 §4): a Summary reached by reload/deep-link
// has no in-memory `skillStateAtStart` snapshot, so the mastery-delta tile renders
// "—". Within an unbroken session the snapshot is carried from openQuizSession via
// the quiz_session_store (read below by session id); a persisted snapshot is a
// later decision (ADR-0011 §4 decision trigger).
"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { SummaryView } from "@/components/summary/SummaryView";
import { useSummary, type SummaryVM } from "@/components/summary/use_summary";
import { readQuizSessionSnapshot } from "@/components/quiz/quiz_session_store";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";
import type { SkillState } from "@/lib/wire/engine_entities";

export default function SummaryPage(): React.JSX.Element {
  const { learnerId } = useLearnIdentity();
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
    // unmount. The start snapshot comes from the quiz_session_store when the
    // learner reached here via the in-session Finish CTA; a fresh page load /
    // deep-link finds nothing → empty map → delta "—" (ADR-0011 §4).
    let cancelled = false;
    setError(null);
    const emptySnapshot: ReadonlyMap<string, SkillState> = new Map();
    const skillStateAtStart =
      readQuizSessionSnapshot(sessionId) ?? emptySnapshot;
    load({
      subject: DEFAULT_SUBJECT,
      learnerId,
      sessionId,
      skillStateAtStart,
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
  }, [load, sessionId, learnerId]);

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
