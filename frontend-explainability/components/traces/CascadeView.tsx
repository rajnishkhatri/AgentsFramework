/**
 * CascadeView — Server Component (no `'use client'`).
 *
 * Renders the Cascade Analysis tab for /traces/[wf_id] (S4.1.1).
 *
 * The component is a pure renderer of an already-translated `CascadeReport`
 * (rule T1 stays in the translator).  Brainstorm §2b layout: ROOT_CAUSE,
 * IMMEDIATE_EFFECT, PROPAGATION chain, SYSTEM_RESPONSE, PLAN_VS_ACTUAL grid.
 *
 * Rule U6: every class merge runs through `cn()`.
 * Rule FD2.B1: RSC by default — no interactive state on this view.
 */
import { cn } from "@/lib/utils";
import type {
  CascadeReport,
  PlanStatus,
  PropagationFrame,
} from "@/lib/translators/cascade_analysis";

export interface CascadeViewProps {
  report: CascadeReport;
}

const STATUS_COLOR: Record<PlanStatus, string> = {
  ok: "bg-green-50 text-green-700 ring-green-600/20",
  error: "bg-red-50 text-red-700 ring-red-600/20",
  skipped: "bg-amber-50 text-amber-700 ring-amber-600/20",
  missing: "bg-muted text-muted-foreground ring-border",
};

const SYSTEM_RESPONSE_LABEL: Record<string, string> = {
  workflow_terminated_no_recovery:
    "Workflow terminated without recovery after the error.",
  workflow_completed_after_error:
    "Workflow completed after the error (downstream steps still ran).",
  workflow_in_progress: "Workflow still in progress at the time of capture.",
  no_response_observed: "No system response observed.",
};

export function CascadeView({ report }: CascadeViewProps) {
  if (!report.has_errors) {
    return (
      <div
        role="status"
        aria-label="No errors"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-16 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No errors recorded for this workflow.</p>
        <p className="mt-1 text-xs">
          Cascade analysis activates when at least one error_occurred event is
          present.
        </p>
      </div>
    );
  }

  return (
    <section
      aria-label="Cascade analysis"
      className="grid grid-cols-1 gap-4 lg:grid-cols-2"
    >
      <RootCauseCard report={report} />
      <ImmediateEffectCard report={report} />
      <PropagationCard report={report} />
      <SystemResponseCard report={report} />
      <PlanVsActualCard report={report} />
    </section>
  );
}

function Card({
  title,
  caption,
  children,
  span,
}: {
  title: string;
  caption?: string;
  children: React.ReactNode;
  span?: "full";
}) {
  return (
    <article
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border bg-card p-4",
        span === "full" && "lg:col-span-2",
      )}
    >
      <header>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {caption !== undefined && (
          <p className="text-xs text-muted-foreground">{caption}</p>
        )}
      </header>
      <div className="text-sm">{children}</div>
    </article>
  );
}

function RootCauseCard({ report }: { report: CascadeReport }) {
  const root = report.root_cause;
  if (root === null) return null;
  return (
    <Card title="Root cause" caption="First error_occurred event in the trace.">
      <dl className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-muted-foreground">Step</dt>
          <dd className="mt-0.5 tabular-nums text-foreground">
            {root.step ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Model</dt>
          <dd className="mt-0.5 text-foreground">{root.model ?? "—"}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-muted-foreground">Error</dt>
          <dd className="mt-0.5 break-all font-mono text-xs text-red-700">
            {root.error_message || "(unspecified)"}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-muted-foreground">Event id</dt>
          <dd className="mt-0.5 break-all font-mono text-xs text-foreground">
            {root.event_id}
          </dd>
        </div>
      </dl>
    </Card>
  );
}

function ImmediateEffectCard({ report }: { report: CascadeReport }) {
  const effect = report.immediate_effect;
  return (
    <Card
      title="Immediate effect"
      caption="The first downstream consequence of the root error."
    >
      {effect === null ? (
        <p className="text-muted-foreground">No downstream effect detected.</p>
      ) : (
        <dl className="flex flex-col gap-1 text-xs">
          <div>
            <dt className="text-muted-foreground">Effect</dt>
            <dd className="mt-0.5 text-foreground">{effect.description}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Step</dt>
            <dd className="mt-0.5 tabular-nums text-foreground">
              {effect.step ?? "—"}
            </dd>
          </div>
        </dl>
      )}
    </Card>
  );
}

function PropagationCard({ report }: { report: CascadeReport }) {
  const items = report.propagation;
  return (
    <Card
      title="Propagation"
      caption="Every event downstream of the root cause."
      span="full"
    >
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No propagation observed. The error did not cascade further.
        </p>
      ) : (
        <ol className="flex flex-col gap-2">
          {items.map((frame: PropagationFrame, idx) => (
            <li
              key={frame.event_id}
              className={cn(
                "flex items-center justify-between gap-3 rounded-md border border-border",
                "bg-background px-3 py-2 text-xs",
              )}
            >
              <span className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="tabular-nums text-muted-foreground"
                >
                  #{idx + 1}
                </span>
                <span className="text-foreground">{frame.description}</span>
              </span>
              <span className="font-mono text-[10px] text-muted-foreground">
                {frame.event_id}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function SystemResponseCard({ report }: { report: CascadeReport }) {
  const key = report.system_response ?? "no_response_observed";
  return (
    <Card title="System response" caption="How the runtime reacted to the error.">
      <p className="text-foreground">
        {SYSTEM_RESPONSE_LABEL[key] ?? "Unknown system response."}
      </p>
    </Card>
  );
}

function PlanVsActualCard({ report }: { report: CascadeReport }) {
  const rows = report.plan_vs_actual;
  return (
    <Card
      title="Plan vs actual"
      caption="What was planned at each step versus what actually happened."
    >
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No planned steps recorded — nothing to compare.
        </p>
      ) : (
        <table className="w-full table-fixed text-xs">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="w-12 py-1 font-medium">Step</th>
              <th className="py-1 font-medium">Planned</th>
              <th className="py-1 font-medium">Actual</th>
              <th className="w-20 py-1 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row) => (
              <tr key={row.step}>
                <td className="py-1 tabular-nums text-foreground">
                  {row.step}
                </td>
                <td className="py-1 text-foreground">{row.planned}</td>
                <td className="py-1 text-foreground">{row.actual}</td>
                <td className="py-1">
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset",
                      STATUS_COLOR[row.status],
                    )}
                  >
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
