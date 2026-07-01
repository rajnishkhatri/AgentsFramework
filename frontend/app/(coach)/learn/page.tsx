// B1: 'use client' required — the Dashboard reads the engine bag from
// useEngine() context (the browser-safe InMemoryEngineDb substrate, ADR-0005
// local-first) via useDashboard(), and loads the VM on mount. The domain logic
// (gather + weakest-due pick + misses count) lives in loadDashboard (F-R1);
// this page is thin glue that renders the loaded DashboardVM.
//
// When the engine graduates to the server pg seam, this becomes an RSC page that
// builds the VM server-side (plan §"Where the engine runs"); the DashboardView
// and loadDashboard are unchanged by that swap.
"use client";

import * as React from "react";
import { DashboardView } from "@/components/dashboard/DashboardView";
import { useDashboard, type DashboardVM } from "@/components/dashboard/use_dashboard";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

// Phase-1 single-learner surface (the plan's "Maya"). A real identity seam
// (WorkOS session → learner id) is a later wiring; hard-coding it here keeps the
// dashboard renderable now without inventing an auth dependency.
const LEARNER_ID = "maya";

export default function DashboardPage(): React.JSX.Element {
  const { load } = useDashboard();
  const [vm, setVm] = React.useState<DashboardVM | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    // Sync to the async engine read on mount (a sanctioned useEffect case §14:
    // an external, non-React data source). `cancelled` guards a late resolve
    // after unmount.
    let cancelled = false;
    setError(null);
    load({
      subject: DEFAULT_SUBJECT,
      learnerId: LEARNER_ID,
      nowISO: new Date().toISOString(),
    })
      .then((next) => {
        if (!cancelled) setVm(next);
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
        Loading your dashboard&hellip;
      </p>
    );
  }
  return <DashboardView vm={vm} />;
}
