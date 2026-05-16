"use client";
/**
 * Pie chart for the guardrail fail-action distribution (S2.1.2 AC).
 *
 * Rule B1 — `'use client'` is justified: Recharts' ResponsiveContainer attaches
 * a window-resize listener, which requires a client boundary.
 *
 * Recharts is in the explainability-frontend reviewer's allowlist (FD7.AP13).
 * This file is a thin wrapper around the pure `failActionDistributionToSlices`
 * translator — all data shaping happens upstream so the component itself stays
 * presentational.
 */
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from "recharts";
import type { ActionSlice } from "@/lib/translators/action_distribution";

export interface ActionDistributionPieProps {
  slices: readonly ActionSlice[];
}

// Use only tokenised CSS variables -- no hardcoded hex fallbacks (Sprint 1
// review P2.2): drift-checked tokens live in app/globals.css so the chart
// theme tracks the rest of the dashboard automatically.
const COLOR_VAR: Record<ActionSlice["color"], string> = {
  danger: "var(--color-kpi-red)",
  warning: "var(--color-kpi-amber)",
  info: "var(--color-primary)",
  neutral: "var(--color-muted-foreground)",
};

export function ActionDistributionPie({ slices }: ActionDistributionPieProps) {
  if (slices.length === 0) {
    return (
      <p className="py-8 text-center text-xs text-muted-foreground">
        No guardrail rejections in this window.
      </p>
    );
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={[...slices]}
            dataKey="count"
            nameKey="action"
            innerRadius="40%"
            outerRadius="75%"
            paddingAngle={2}
          >
            {slices.map((s) => (
              <Cell key={s.action} fill={COLOR_VAR[s.color]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number, name: string) => [`${value}`, name]}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
