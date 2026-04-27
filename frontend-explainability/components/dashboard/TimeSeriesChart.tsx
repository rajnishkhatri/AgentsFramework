"use client";
/**
 * Recharts time-series wrapper.
 *
 * Rule B1 — `'use client'` is justified: Recharts uses ResponsiveContainer's
 * window-resize listener which requires a client boundary.
 *
 * Recharts is one of the seven SDK libs in the explainability frontend
 * reviewer's allowlist (FD7.AP13).
 */
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import type { TimeSeriesPoint } from "@/lib/wire/responses";

export interface TimeSeriesChartProps {
  title: string;
  unit: string;
  data: readonly TimeSeriesPoint[];
}

export function TimeSeriesChart({ title, unit, data }: TimeSeriesChartProps) {
  const chartData = data.map((p) => ({
    bucket: new Date(p.bucket).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
    }),
    value: p.value,
  }));

  return (
    <section
      aria-label={title}
      className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <span className="text-xs text-muted-foreground">{unit}</span>
      </header>
      {chartData.length === 0 ? (
        <p className="py-8 text-center text-xs text-muted-foreground">
          No data in the selected range.
        </p>
      ) : (
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="value"
                stroke="var(--color-primary)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
