// B1: 'use client' required — the Coach screen drives a live SSE run over the
// chat AgentRuntimeClient (plan OD-3: the coach is a consumer of the chat runtime
// port, not an engine port) via useCoach(), which owns the run lifecycle (F-R1);
// this page is thin glue that builds the coach-pointed runtime and renders the
// CoachView.
//
// The runtime streams from the coach BFF base (`/api/coach/run/stream`), keeping
// the coach thread + persona (subject-coach-english agent_id) distinct from chat
// while reusing every transport + reducer invariant. No SDK import here (F-R2):
// the concrete adapter is named only inside composition_browser.
"use client";

import * as React from "react";
import { buildBrowserRuntimeClient } from "@/lib/composition_browser";
import { CoachView } from "@/components/coach/CoachView";
import { useCoach } from "@/components/coach/use_coach";

export default function CoachPage(): React.JSX.Element {
  // One coach-pointed runtime for the page's lifetime. Built once (not per
  // render) so the in-flight stream + thread id survive re-renders.
  const runtime = React.useMemo(
    () => buildBrowserRuntimeClient({ baseUrl: "/api/coach" }),
    [],
  );
  const { turns, busy, ask, retry } = useCoach(runtime);

  return (
    <div className="flex h-full flex-col">
      <header className="mb-4 flex flex-col gap-1">
        <h1 className="text-xl font-semibold">Coach</h1>
        <p className="text-sm text-muted">
          Ask why an answer is right — the coach explains, it never just tells.
        </p>
      </header>
      <CoachView turns={turns} busy={busy} onAsk={ask} onRetry={retry} />
    </div>
  );
}
