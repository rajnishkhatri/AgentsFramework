/**
 * StreakTile — presentational streak chip for the Dashboard trust rail (FR-2/FR-7).
 * Pure props-in; no ports, no I/O.
 */

import * as React from "react";
import type { StreakVM } from "@/lib/translators/streak_vm";

export function StreakTile(props: { vm: StreakVM }): React.JSX.Element {
  const { vm } = props;
  const label = vm.present ? `${vm.days}-day streak` : "Start a streak";
  const aria = vm.present ? `Streak: ${vm.days} days` : "Streak: start a streak";
  return (
    <div
      data-testid="streak-tile"
      aria-label={aria}
      className="rounded-md border border-border px-3 py-2 text-sm"
    >
      <p className="font-medium text-fg">{label}</p>
    </div>
  );
}
