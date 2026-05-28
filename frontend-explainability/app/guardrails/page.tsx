/**
 * /guardrails — Guardrail Monitor (S2.1.2).
 *
 * Server Component (no `'use client'`): fetches the guardrail summary via the
 * adapter, then composes KPI row, per-validator table, fail-action pie, and
 * recent-failures table linked back to /traces/[wf_id].
 *
 * Rule B1 (RSC by default) — only the chart wrapper escapes to a client
 * boundary.
 * Rule U6 — every class merge is via `cn()` (delegated to child components).
 */
import { buildAdapters } from "@/lib/composition";
import { failActionDistributionToSlices } from "@/lib/translators/action_distribution";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { guardrailRejectTone } from "@/components/dashboard/kpi_thresholds";
import { ValidatorTable } from "@/components/guardrails/ValidatorTable";
import { ActionDistributionPie } from "@/components/guardrails/ActionDistributionPie";
import { RecentFailuresTable } from "@/components/guardrails/RecentFailuresTable";

export const metadata = {
  title: "Guardrail Monitor — Explainability",
};

// Skip static prerender — every render reads live guardrail signals over HTTP.
export const dynamic = "force-dynamic";

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatSignedPct(delta: number): string {
  const pct = `${(Math.abs(delta) * 100).toFixed(1)}%`;
  if (delta > 0) return `▲ ${pct}`;
  if (delta < 0) return `▼ ${pct}`;
  return `— ${pct}`;
}

export default async function GuardrailsPage() {
  const { explainabilityClient } = buildAdapters();
  const summary = await explainabilityClient.getGuardrailSummary();
  const slices = failActionDistributionToSlices(summary.fail_action_distribution);

  const passPct = summary.total_checks === 0 ? 0 : summary.pass_rate;
  const rejectPct = summary.total_checks === 0 ? 0 : 1 - summary.pass_rate;

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Guardrail Monitor</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pass rate, validator breakdown, and recent rejections across all
          recorded workflows.
        </p>
      </header>

      <section
        aria-label="Guardrail KPIs"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        <KpiCard
          label="Total Checks"
          value={summary.total_checks.toString()}
          tone="neutral"
          caption={
            summary.total_checks === 0
              ? "No data yet"
              : `${summary.pass_count} pass · ${summary.fail_count} fail`
          }
        />
        <KpiCard
          label="Pass %"
          value={summary.total_checks === 0 ? "—" : formatPct(passPct)}
          tone={guardrailRejectTone(summary.pass_rate)}
          caption={
            summary.total_checks === 0
              ? undefined
              : `Reject ${formatPct(rejectPct)}`
          }
        />
        <KpiCard
          label="Trend vs prior"
          value={
            summary.total_checks === 0
              ? "—"
              : formatSignedPct(summary.trend_pass_rate_delta)
          }
          tone={trendTone(summary.trend_pass_rate_delta)}
          caption="Δ pass-rate (window-over-window)"
        />
        <KpiCard
          label="Validators"
          value={summary.per_validator.length.toString()}
          tone="neutral"
          caption={
            summary.per_validator.length === 0
              ? undefined
              : "Distinct validators observed"
          }
        />
      </section>

      <section className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <article className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
          <header>
            <h2 className="text-sm font-semibold text-foreground">
              Per-validator breakdown
            </h2>
            <p className="text-xs text-muted-foreground">
              Pass/fail counts for every validator that ran in the window.
            </p>
          </header>
          <ValidatorTable validators={summary.per_validator} />
        </article>

        <article className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
          <header>
            <h2 className="text-sm font-semibold text-foreground">
              Fail-action distribution
            </h2>
            <p className="text-xs text-muted-foreground">
              How rejected calls were handled — reject, redact, escalate, retry.
            </p>
          </header>
          <ActionDistributionPie slices={slices} />
        </article>
      </section>

      <section className="flex flex-col gap-2">
        <header>
          <h2 className="text-sm font-semibold text-foreground">
            Recent failures
          </h2>
          <p className="text-xs text-muted-foreground">
            Latest guardrail rejections — click a workflow to inspect its
            timeline.
          </p>
        </header>
        <RecentFailuresTable failures={summary.recent_failures} />
      </section>
    </div>
  );
}

function trendTone(delta: number): "green" | "amber" | "red" | "neutral" {
  if (delta >= 0.05) return "green";
  if (delta <= -0.05) return "red";
  if (delta <= -0.01) return "amber";
  return "neutral";
}
