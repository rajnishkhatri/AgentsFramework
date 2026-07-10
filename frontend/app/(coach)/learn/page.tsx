// B1: 'use client' required — the Dashboard reads the engine bag from
// useEngine() context via useDashboard(), and loads the VM on mount. Domain
// logic lives in loadDashboard (F-R1); this page is thin glue.
"use client";

import * as React from "react";
import { DashboardView } from "@/components/dashboard/DashboardView";
import { useDashboard, type DashboardVM } from "@/components/dashboard/use_dashboard";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

const LEARNER_ID = "maya";

export default function DashboardPage(): React.JSX.Element {
  const { load } = useDashboard();
  const [vm, setVm] = React.useState<DashboardVM | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [reloadToken, setReloadToken] = React.useState(0);

  React.useEffect(() => {
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
  }, [load, reloadToken]);

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
  return (
    <DashboardView
      vm={vm}
      onRetryRail={() => setReloadToken((n) => n + 1)}
    />
  );
}
