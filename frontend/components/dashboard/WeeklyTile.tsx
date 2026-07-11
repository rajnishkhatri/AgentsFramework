/**
 * WeeklyTile — presentational weekly-sessions chip for the Dashboard trust rail
 * (FR-2/FR-8). Pure props-in; no ports, no I/O.
 */

import * as React from "react";
import type { WeeklySessionsVM } from "@/lib/translators/weekly_sessions_vm";

export function WeeklyTile(props: { vm: WeeklySessionsVM }): React.JSX.Element {
  const { vm } = props;
  const aria = `Weekly sessions: ${Math.min(vm.count, vm.target)} of ${vm.target}`;
  return (
    <div
      data-testid="weekly-tile"
      aria-label={aria}
      className="rounded-md border border-border px-3 py-2 text-sm"
    >
      <p className="font-medium text-fg">{vm.label}</p>
    </div>
  );
}
