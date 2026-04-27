/**
 * KpiCard — single tile in the dashboard KPI row (S1.3.2).
 *
 * Rule U8 — colour tokens come from `app/globals.css`; this file never hardcodes
 * a hex value.  The colour selection (green/amber/red/neutral) is the only
 * place a numeric threshold lives.
 */
import { cn } from "@/lib/utils";

export type KpiTone = "green" | "amber" | "red" | "neutral";

export interface KpiCardProps {
  label: string;
  value: string;
  tone: KpiTone;
  /** Optional one-line caption for context. */
  caption?: string | undefined;
}

const TONE_RING: Record<KpiTone, string> = {
  green: "ring-[color:var(--color-kpi-green)]",
  amber: "ring-[color:var(--color-kpi-amber)]",
  red: "ring-[color:var(--color-kpi-red)]",
  neutral: "ring-border",
};

const TONE_BG: Record<KpiTone, string> = {
  green: "bg-[color:var(--color-kpi-bg-green)]",
  amber: "bg-[color:var(--color-kpi-bg-amber)]",
  red: "bg-[color:var(--color-kpi-bg-red)]",
  neutral: "bg-[color:var(--color-kpi-bg-neutral)]",
};

const TONE_TEXT: Record<KpiTone, string> = {
  green: "text-[color:var(--color-kpi-text-green)]",
  amber: "text-[color:var(--color-kpi-text-amber)]",
  red: "text-[color:var(--color-kpi-text-red)]",
  neutral: "text-[color:var(--color-kpi-text-neutral)]",
};

export function KpiCard({ label, value, tone, caption }: KpiCardProps) {
  return (
    <article
      aria-label={label}
      className={cn(
        "flex flex-col gap-1 rounded-lg p-4 ring-1 ring-inset",
        TONE_RING[tone],
        TONE_BG[tone],
      )}
      data-tone={tone}
    >
      <span className={cn("text-xs font-medium uppercase tracking-wide", TONE_TEXT[tone])}>
        {label}
      </span>
      <span className={cn("text-2xl font-semibold tabular-nums", TONE_TEXT[tone])}>
        {value}
      </span>
      {caption && (
        <span className={cn("text-xs", TONE_TEXT[tone])}>{caption}</span>
      )}
    </article>
  );
}
