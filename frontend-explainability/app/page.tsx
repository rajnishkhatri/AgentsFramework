/**
 * / — Dashboard landing page (S1.3.2).
 *
 * Server Component: fetches dashboard metrics + recent runs in parallel via the
 * adapter, then composes KPI cards, time-series charts, and the recent-runs
 * table.  No 'use client' on this file (rule B1).
 */
import { buildAdapters } from "@/lib/composition";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { TimeSeriesChart } from "@/components/dashboard/TimeSeriesChart";
import { WorkflowsTable } from "@/components/traces/WorkflowsTable";
import {
  averageCost,
  chainValidTone,
  costTone,
  guardrailRejectTone,
  latencyTone,
  runCountTone,
} from "@/components/dashboard/kpi_thresholds";

export const metadata = {
  title: "Dashboard — Explainability",
};

// Skip static prerender — every render reads live backend metrics over HTTP.
export const dynamic = "force-dynamic";

const RECENT_RUNS_LIMIT = 10;

function formatUsd(value: number): string {
  return `$${value.toFixed(4)}`;
}

function formatMs(value: number): string {
  if (value <= 0) return "—";
  if (value < 1000) return `${value.toFixed(0)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default async function DashboardPage() {
  const { explainabilityClient } = buildAdapters();
  const [metrics, workflows] = await Promise.all([
    explainabilityClient.getDashboardMetrics(),
    explainabilityClient.listWorkflows(),
  ]);

  const recentRuns = workflows.slice(0, RECENT_RUNS_LIMIT);
  const avgCost = averageCost(metrics.total_cost_usd, metrics.total_runs);
  const rejectRate = 1 - metrics.guardrail_pass_rate;
  const totalChain = metrics.hash_chain_valid_count + metrics.hash_chain_invalid_count;
  const chainValidPct = totalChain > 0 ? metrics.hash_chain_valid_count / totalChain : 0;

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Aggregate signals across all recorded workflows.
        </p>
      </header>

      <section
        aria-label="Key performance indicators"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5"
      >
        <KpiCard
          label="Total Runs"
          value={metrics.total_runs.toString()}
          tone={runCountTone()}
          caption={metrics.total_runs === 0 ? "No data yet" : undefined}
        />
        <KpiCard
          label="Avg Cost"
          value={avgCost === null ? "—" : formatUsd(avgCost)}
          tone={costTone(metrics.total_cost_usd)}
          caption={`Total ${formatUsd(metrics.total_cost_usd)}`}
        />
        <KpiCard
          label="P95 Latency"
          value={formatMs(metrics.p95_latency_ms)}
          tone={latencyTone(metrics.p95_latency_ms)}
          caption={`P50 ${formatMs(metrics.p50_latency_ms)}`}
        />
        <KpiCard
          label="Guardrail Reject %"
          value={metrics.total_runs === 0 ? "—" : formatPct(rejectRate)}
          tone={guardrailRejectTone(metrics.guardrail_pass_rate)}
          caption={
            metrics.total_runs === 0
              ? undefined
              : `Pass ${formatPct(metrics.guardrail_pass_rate)}`
          }
        />
        <KpiCard
          label="Chain Valid %"
          value={totalChain === 0 ? "—" : formatPct(chainValidPct)}
          tone={chainValidTone(
            metrics.hash_chain_valid_count,
            metrics.hash_chain_invalid_count,
          )}
          caption={
            totalChain === 0
              ? undefined
              : `${metrics.hash_chain_invalid_count} broken / ${totalChain}`
          }
        />
      </section>

      <section className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <TimeSeriesChart
          title="Cost over time"
          unit="USD per hour"
          data={metrics.time_series_cost}
        />
        <TimeSeriesChart
          title="P95 Latency over time"
          unit="ms per hour"
          data={metrics.time_series_latency}
        />
      </section>

      <section className="grid grid-cols-1 gap-3">
        <TimeSeriesChart
          title="Tokens over time"
          unit="tokens per hour"
          data={metrics.time_series_tokens}
        />
      </section>

      <section className="flex flex-col gap-3">
        <header className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Recent runs
          </h2>
          <span className="text-xs text-muted-foreground">
            Showing {recentRuns.length} of {workflows.length}
          </span>
        </header>
        <WorkflowsTable workflows={recentRuns} />
      </section>
    </div>
  );
}
