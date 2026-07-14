/**
 * TrendChart — hand-built SVG accuracy sparkline (Epic F FR-9 / Q-D2).
 *
 * One consumer (ProgressView). Inline in components/learn/ — G1: no shared
 * chart primitive until a 2nd consumer lands. Theme stroke via
 * `var(--color-accent)`; per-point circle markers (non-color signal); visually-
 * hidden a11y summary. No charting lib. CSP-safe (no dynamic nonce styles).
 */

"use client";

import * as React from "react";
import type { TrendPoint } from "@/lib/translators/progress_screen_vm";

export interface TrendChartProps {
  readonly points: readonly TrendPoint[];
  /** Accessible name (default "Accuracy trend"). */
  readonly label?: string;
}

const VB_W = 320;
const VB_H = 120;
const PAD_X = 12;
const PAD_Y = 14;

function toSvgPoints(points: readonly TrendPoint[]): string {
  const n = points.length;
  if (n === 0) return "";
  const xs =
    n === 1
      ? [VB_W / 2]
      : points.map((_, i) => PAD_X + (i / (n - 1)) * (VB_W - 2 * PAD_X));
  return points
    .map((p, i) => {
      const pct = Math.max(0, Math.min(100, p.accuracyPct));
      const y = PAD_Y + (1 - pct / 100) * (VB_H - 2 * PAD_Y);
      return `${xs[i]!.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function a11ySummary(points: readonly TrendPoint[]): string {
  if (points.length === 0) {
    return "Accuracy trend, no sessions yet";
  }
  const first = points[0]!;
  const last = points[points.length - 1]!;
  return `Accuracy trend, ${points.length} sessions, ${first.accuracyPct}% to ${last.accuracyPct}%`;
}

export function TrendChart(props: TrendChartProps): React.JSX.Element {
  const { points, label = "Accuracy trend" } = props;
  const showLine = points.length >= 2;
  const svgPoints = showLine ? toSvgPoints(points) : "";
  const markerCoords = points.map((p, i) => {
    const n = points.length;
    const x =
      n === 1
        ? VB_W / 2
        : PAD_X + (i / Math.max(n - 1, 1)) * (VB_W - 2 * PAD_X);
    const pct = Math.max(0, Math.min(100, p.accuracyPct));
    const y = PAD_Y + (1 - pct / 100) * (VB_H - 2 * PAD_Y);
    return { x, y, pct: p.accuracyPct };
  });

  if (points.length === 0) {
    return (
      <div
        data-testid="trend-chart-empty"
        role="img"
        aria-label={a11ySummary(points)}
        className="flex h-28 items-center justify-center text-sm text-muted"
      >
        Not enough history yet
      </div>
    );
  }

  return (
    <div data-testid="trend-chart" className="w-full">
      <svg
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        role="img"
        aria-label={label}
        className="h-28 w-full"
      >
        {/* Faint baseline only — no goal guide (FR-3 / Q-D1). */}
        <line
          x1={PAD_X}
          y1={VB_H - PAD_Y}
          x2={VB_W - PAD_X}
          y2={VB_H - PAD_Y}
          stroke="var(--color-border)"
          strokeWidth={1}
          opacity={0.5}
        />
        {showLine ? (
          <polyline
            points={svgPoints}
            fill="none"
            stroke="var(--color-accent)"
            strokeWidth={2.5}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ) : null}
        {markerCoords.map((m, i) => (
          <circle
            key={i}
            cx={m.x}
            cy={m.y}
            r={3.5}
            fill="var(--color-accent)"
          />
        ))}
      </svg>
      <table
        data-testid="trend-chart-a11y"
        className="sr-only"
      >
        <caption>{a11ySummary(points)}</caption>
        <thead>
          <tr>
            <th scope="col">Session</th>
            <th scope="col">Accuracy</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p, i) => (
            <tr key={p.atISO}>
              <td>{i + 1}</td>
              <td>{p.accuracyPct}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
