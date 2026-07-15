// Epic F: 'use client' — Progress surface reads the engine bag via useProgressScreen.
"use client";

import * as React from "react";
import { ProgressView } from "@/components/learn/ProgressView";
import { useProgressScreen } from "@/components/learn/use_progress_screen";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import type { ProgressRange } from "@/lib/translators/progress_screen_vm";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

export default function ProgressPage(): React.JSX.Element {
  const { learnerId } = useLearnIdentity();
  // iPhone defaults to all-time (tabs hidden via @container — DT-6).
  const [range, setRange] = React.useState<ProgressRange>("all");
  const { vm, loading } = useProgressScreen({
    subject: DEFAULT_SUBJECT,
    learnerId,
    range,
  });

  if (loading || vm == null) {
    return (
      <div data-testid="progress-loading" className="p-6 text-sm text-muted">
        Loading progress…
      </div>
    );
  }

  return (
    <ProgressView vm={vm} range={range} onRangeChange={setRange} />
  );
}
