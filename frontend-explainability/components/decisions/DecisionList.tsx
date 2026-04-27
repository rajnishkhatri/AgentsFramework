"use client";
/**
 * Phase-grouped decision list with filter chips and a collapsible rationale
 * JSON viewer.
 *
 * Rule B1 — `'use client'` is justified: filter-chip toggles and per-row
 * collapse state both need React state.
 *
 * Rule FD4.SEM — every clickable affordance is a `<button>`, never a `<div onClick>`.
 * Rule FD4.LBL — filter chips expose `aria-pressed`.
 */
import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { DecisionRecord } from "@/lib/wire/responses";

const PHASES = [
  "initialization",
  "input_validation",
  "routing",
  "model_invocation",
  "tool_execution",
  "evaluation",
  "continuation",
  "output_validation",
  "completion",
] as const;
type Phase = (typeof PHASES)[number];

export interface DecisionListProps {
  decisions: readonly DecisionRecord[];
}

export function DecisionList({ decisions }: DecisionListProps) {
  const [activePhases, setActivePhases] = useState<Set<Phase>>(new Set());

  const visible = useMemo(() => {
    if (activePhases.size === 0) return decisions;
    return decisions.filter((d) => activePhases.has(d.phase as Phase));
  }, [decisions, activePhases]);

  const grouped = useMemo(() => {
    const map = new Map<string, DecisionRecord[]>();
    for (const decision of visible) {
      const list = map.get(decision.phase) ?? [];
      list.push(decision);
      map.set(decision.phase, list);
    }
    return [...map.entries()];
  }, [visible]);

  if (decisions.length === 0) {
    return (
      <div
        role="status"
        aria-label="No decisions"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-16 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No decisions recorded for this workflow.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">Filter by phase</legend>
        {PHASES.map((phase) => {
          const isActive = activePhases.has(phase);
          return (
            <button
              key={phase}
              type="button"
              aria-pressed={isActive}
              onClick={() =>
                setActivePhases((prev) => {
                  const next = new Set(prev);
                  if (next.has(phase)) next.delete(phase);
                  else next.add(phase);
                  return next;
                })
              }
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium",
                "transition-colors",
                isActive
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card text-muted-foreground hover:bg-accent",
              )}
            >
              {phase}
            </button>
          );
        })}
      </fieldset>

      {grouped.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No decisions match the selected filters.
        </p>
      ) : (
        grouped.map(([phase, rows]) => (
          <section
            key={phase}
            aria-label={`Phase ${phase}`}
            className="rounded-lg border border-border bg-card"
          >
            <header className="border-b border-border bg-muted/30 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {phase}{" "}
              <span className="font-normal lowercase">
                ({rows.length} decision{rows.length === 1 ? "" : "s"})
              </span>
            </header>
            <ol className="divide-y divide-border">
              {rows.map((decision, idx) => (
                <DecisionRow
                  key={`${decision.timestamp ?? "no-ts"}-${idx}`}
                  decision={decision}
                />
              ))}
            </ol>
          </section>
        ))
      )}
    </div>
  );
}

function DecisionRow({ decision }: { decision: DecisionRecord }) {
  const [open, setOpen] = useState(false);
  const confidencePct = Math.round(
    Math.max(0, Math.min(1, decision.confidence)) * 100,
  );

  return (
    <li className="px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">
            {decision.description}
          </p>
          {decision.alternatives.length > 0 && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              Alternatives:{" "}
              <span className="font-mono">
                {decision.alternatives.join(", ")}
              </span>
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1 text-xs">
          <label className="flex items-center gap-2">
            <span className="text-muted-foreground">Confidence</span>
            <progress
              value={confidencePct}
              max={100}
              aria-valuenow={confidencePct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="h-2 w-24"
            />
            <span className="tabular-nums text-foreground">{confidencePct}%</span>
          </label>
          {decision.timestamp && (
            <time className="text-muted-foreground">
              {new Date(decision.timestamp).toLocaleString(undefined, {
                dateStyle: "short",
                timeStyle: "medium",
              })}
            </time>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn(
          "mt-2 text-xs text-primary underline-offset-4 hover:underline",
        )}
      >
        {open ? "Hide rationale" : "Show rationale"}
      </button>
      {open && (
        <pre
          className={cn(
            "mt-2 overflow-x-auto rounded border border-border bg-background",
            "p-2 font-mono text-xs text-foreground",
          )}
        >
          {decision.rationale}
        </pre>
      )}
    </li>
  );
}
