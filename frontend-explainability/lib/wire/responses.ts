/**
 * Wire-layer Zod schemas — mirrors of explainability_app/wire/responses.py.
 *
 * Rule W7: each schema is co-exported alongside its inferred TS type.
 * Rule W2: __python_schema_baseline__.json tracks the Python-side JSON Schema
 *          for every shape in this file; baseline_drift.test.ts asserts they
 *          stay in sync (per-shape comparison, fails on any drift).
 *
 * @sdk zod ^3.0.0
 */
import { z } from "zod";

export const WorkflowSummarySchema = z.object({
  workflow_id: z.string(),
  started_at: z.string().datetime({ offset: true }).nullable(),
  event_count: z.number().int().nonnegative(),
  status: z.string(),
  primary_agent_id: z.string().nullable(),
});
export type WorkflowSummary = z.infer<typeof WorkflowSummarySchema>;

export const WorkflowSummaryListSchema = z.array(WorkflowSummarySchema);
export type WorkflowSummaryList = z.infer<typeof WorkflowSummaryListSchema>;

export const BlackBoxEventSchema = z.object({
  event_id: z.string(),
  workflow_id: z.string(),
  event_type: z.string(),
  timestamp: z.string().datetime({ offset: true }).nullable(),
  step: z.number().int().nullable(),
  details: z.record(z.unknown()),
  integrity_hash: z.string(),
});
export type BlackBoxEvent = z.infer<typeof BlackBoxEventSchema>;

export const WorkflowEventsSchema = z.object({
  workflow_id: z.string(),
  event_count: z.number().int().nonnegative(),
  hash_chain_valid: z.boolean(),
  events: z.array(BlackBoxEventSchema),
});
export type WorkflowEvents = z.infer<typeof WorkflowEventsSchema>;

export const DecisionRecordSchema = z.object({
  workflow_id: z.string(),
  phase: z.string(),
  description: z.string(),
  alternatives: z.array(z.string()),
  rationale: z.string(),
  confidence: z.number(),
  timestamp: z.string().datetime({ offset: true }).nullable(),
});
export type DecisionRecord = z.infer<typeof DecisionRecordSchema>;

export const DecisionRecordListSchema = z.array(DecisionRecordSchema);
export type DecisionRecordList = z.infer<typeof DecisionRecordListSchema>;

export const TimeSeriesPointSchema = z.object({
  bucket: z.string().datetime({ offset: true }),
  value: z.number(),
});
export type TimeSeriesPoint = z.infer<typeof TimeSeriesPointSchema>;

export const DashboardMetricsSchema = z.object({
  total_runs: z.number().int().nonnegative(),
  p50_latency_ms: z.number(),
  p95_latency_ms: z.number(),
  total_cost_usd: z.number(),
  guardrail_pass_rate: z.number(),
  hash_chain_valid_count: z.number().int().nonnegative(),
  hash_chain_invalid_count: z.number().int().nonnegative(),
  time_series_cost: z.array(TimeSeriesPointSchema),
  time_series_latency: z.array(TimeSeriesPointSchema),
  time_series_tokens: z.array(TimeSeriesPointSchema),
  model_distribution: z.record(z.number().int().nonnegative()),
});
export type DashboardMetrics = z.infer<typeof DashboardMetricsSchema>;

export const HealthResponseSchema = z.object({
  status: z.string(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const ErrorResponseSchema = z.object({
  detail: z.string(),
});
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
