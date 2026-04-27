/**
 * Wire-layer Zod schemas — mirrors of explainability_app/wire/responses.py.
 *
 * Rule W7: each schema is co-exported alongside its inferred TS type.
 * Rule W2: __python_schema_baseline__.json tracks the Python-side JSON Schema;
 *           baseline_drift.test.ts asserts they stay in sync.
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

export const HealthResponseSchema = z.object({
  status: z.string(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const ErrorResponseSchema = z.object({
  detail: z.string(),
});
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
