// B1: 'use client' required — the Dashboard reads the engine bag from
// useEngine() context via useDashboard(), and loads the VM on mount. Domain
// logic lives in loadDashboard / loadRail (F-R1); this page is thin glue.
//
// C1-fix FR-8: Effect A loads greeting/buckets/focus/misses once per mount
// (skipRail); Effect B loads the rail on mount + Retry. Rail retry does not
// re-render the greeting or mastery grid.
"use client";

import * as React from "react";
import { DashboardView } from "@/components/dashboard/DashboardView";
import {
  useDashboard,
  type DashboardVM,
  type RailVM,
} from "@/components/dashboard/use_dashboard";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

const LEARNER_ID = "Garvit";
const LEARNER_DISPLAY_NAME = "Garvit";

type BaseVm = Omit<DashboardVM, "rail">;

export default function DashboardPage(): React.JSX.Element {
  const { load, loadRail } = useDashboard();
  const [baseVm, setBaseVm] = React.useState<BaseVm | null>(null);
  const [rail, setRail] = React.useState<RailVM | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [reloadToken, setReloadToken] = React.useState(0);

  // Effect A — greeting / buckets / focus / misses (once per mount).
  React.useEffect(() => {
    let cancelled = false;
    setError(null);
    load({
      subject: DEFAULT_SUBJECT,
      learnerId: LEARNER_ID,
      displayName: LEARNER_DISPLAY_NAME,
      nowISO: new Date().toISOString(),
      skipRail: true,
    })
      .then((next) => {
        if (cancelled) return;
        const { rail: _ignored, ...rest } = next;
        setBaseVm(rest);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load dashboard");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  // Effect B — rail only (mount + Retry). FR-8: does not touch baseVm.
  React.useEffect(() => {
    let cancelled = false;
    loadRail({
      subject: DEFAULT_SUBJECT,
      learnerId: LEARNER_ID,
      displayName: LEARNER_DISPLAY_NAME,
      nowISO: new Date().toISOString(),
    })
      .then((next) => {
        if (!cancelled) setRail(next);
      })
      .catch(() => {
        // loadRail never rejects (maps errors to unavailable); keep baseVm.
      });
    return () => {
      cancelled = true;
    };
  }, [loadRail, reloadToken]);

  if (error != null) {
    return (
      <p role="alert" className="text-danger">
        {error}
      </p>
    );
  }
  if (baseVm == null || rail == null) {
    return (
      <p role="status" className="text-muted">
        Loading your dashboard&hellip;
      </p>
    );
  }
  return (
    <DashboardView
      vm={{ ...baseVm, rail }}
      onRetryRail={() => setReloadToken((n) => n + 1)}
    />
  );
}
