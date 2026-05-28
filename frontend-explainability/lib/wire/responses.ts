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

export const ValidatorStatSchema = z.object({
  name: z.string(),
  total_checks: z.number().int().nonnegative(),
  pass_count: z.number().int().nonnegative(),
  fail_count: z.number().int().nonnegative(),
  pass_rate: z.number(),
});
export type ValidatorStat = z.infer<typeof ValidatorStatSchema>;

export const GuardrailFailureSchema = z.object({
  workflow_id: z.string(),
  validator: z.string(),
  fail_action: z.string().nullable(),
  timestamp: z.string().datetime({ offset: true }).nullable(),
});
export type GuardrailFailure = z.infer<typeof GuardrailFailureSchema>;

export const GuardrailSummarySchema = z.object({
  total_checks: z.number().int().nonnegative(),
  pass_count: z.number().int().nonnegative(),
  fail_count: z.number().int().nonnegative(),
  pass_rate: z.number(),
  fail_action_distribution: z.record(z.number().int().nonnegative()),
  per_validator: z.array(ValidatorStatSchema),
  recent_failures: z.array(GuardrailFailureSchema),
  trend_pass_rate_delta: z.number(),
});
export type GuardrailSummary = z.infer<typeof GuardrailSummarySchema>;

export const CapabilitySchema = z.object({
  name: z.string(),
  description: z.string(),
  parameters: z.record(z.unknown()),
});
export type Capability = z.infer<typeof CapabilitySchema>;

export const PolicySchema = z.object({
  name: z.string(),
  description: z.string(),
  rules: z.record(z.unknown()),
});
export type Policy = z.infer<typeof PolicySchema>;

/**
 * S2.2 / Phase 1 trust correction: ``signature_verification_status``
 * distinguishes ``verified`` (HMAC matched), ``failed`` (mismatch or
 * non-active status), and ``unavailable`` (verify could not run, e.g. no
 * secret).  Newer UIs MUST consume the status string when rendering a
 * verification badge; the legacy ``signature_verified`` boolean is kept
 * for back-compat (true only for ``verified``).
 */
export const SignatureVerificationStatusSchema = z.enum([
  "verified",
  "failed",
  "unavailable",
]);
export type SignatureVerificationStatus = z.infer<
  typeof SignatureVerificationStatusSchema
>;

export const AgentCardSchema = z.object({
  agent_id: z.string(),
  agent_name: z.string(),
  owner: z.string(),
  version: z.string(),
  description: z.string(),
  capabilities: z.array(CapabilitySchema),
  policies: z.array(PolicySchema),
  status: z.string(),
  valid_until: z.string().datetime({ offset: true }).nullable(),
  parent_agent_id: z.string().nullable(),
  signature_truncated: z.string(),
  signature_verified: z.boolean(),
  signature_verification_status: SignatureVerificationStatusSchema,
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type AgentCard = z.infer<typeof AgentCardSchema>;

export const AgentCardListSchema = z.array(AgentCardSchema);
export type AgentCardList = z.infer<typeof AgentCardListSchema>;

export const AgentAuditEntrySchema = z.object({
  agent_id: z.string(),
  action: z.string(),
  performed_by: z.string(),
  timestamp: z.string().datetime({ offset: true }),
  details: z.record(z.unknown()),
});
export type AgentAuditEntry = z.infer<typeof AgentAuditEntrySchema>;

export const AgentAuditEntryListSchema = z.array(AgentAuditEntrySchema);
export type AgentAuditEntryList = z.infer<typeof AgentAuditEntryListSchema>;

export const IntegrityReportSchema = z.object({
  workflow_id: z.string(),
  chain_valid: z.boolean(),
  broken_at_event_id: z.string().nullable(),
  expected_hash: z.string().nullable(),
  actual_hash: z.string().nullable(),
});
export type IntegrityReport = z.infer<typeof IntegrityReportSchema>;

export const CorrelationHealthSchema = z.object({
  has_trace_id: z.boolean(),
  has_user_id: z.boolean(),
  has_task_id: z.boolean(),
  has_agent_id: z.boolean(),
  missing_keys: z.array(z.string()),
});
export type CorrelationHealth = z.infer<typeof CorrelationHealthSchema>;

export const ComplianceBundleSchema = z.object({
  workflow_id: z.string(),
  event_count: z.number().int().nonnegative(),
  hash_chain_valid: z.boolean(),
  bundle_type: z.string(),
  exported_at: z.string().datetime({ offset: true }).nullable(),
  events: z.array(BlackBoxEventSchema),
  identity_cards: z.record(AgentCardSchema.nullable()),
  audit_trails: z.record(z.array(AgentAuditEntrySchema)),
  phase_decisions: z.array(DecisionRecordSchema),
  correlation_health: CorrelationHealthSchema,
  /**
   * Sprint 3 review F4: bundle now embeds the full IntegrityReport so the
   * Workflow Deep Dive Recording quadrant can name the broken event id.
   */
  integrity: IntegrityReportSchema,
});
export type ComplianceBundle = z.infer<typeof ComplianceBundleSchema>;

/**
 * Sprint 3 review F3 fix: batched compliance summary contract.
 *
 * Replaces the per-row N+1 fan-out where the page used to call
 * `getWorkflowIntegrity` once per workflow.  One network round-trip now
 * returns every workflow + integrity row, plus the bounds the server
 * actually applied.
 */
export const WorkflowIntegritySummarySchema = z.object({
  workflow: WorkflowSummarySchema,
  integrity: IntegrityReportSchema.nullable(),
});
export type WorkflowIntegritySummary = z.infer<
  typeof WorkflowIntegritySummarySchema
>;

export const ComplianceSummarySchema = z.object({
  rows: z.array(WorkflowIntegritySummarySchema),
  generated_at: z.string().datetime({ offset: true }),
  since: z.string().datetime({ offset: true }).nullable(),
  until: z.string().datetime({ offset: true }).nullable(),
});
export type ComplianceSummary = z.infer<typeof ComplianceSummarySchema>;

export const LogRowSchema = z.object({
  concern: z.string(),
  timestamp: z.string().datetime({ offset: true }).nullable(),
  logger: z.string(),
  level: z.string(),
  message: z.string(),
  raw: z.string(),
});
export type LogRow = z.infer<typeof LogRowSchema>;

export const LogRowListSchema = z.array(LogRowSchema);
export type LogRowList = z.infer<typeof LogRowListSchema>;

/**
 * Stable list of log concern keys -- mirror of `DEFAULT_LOG_CONCERNS` in
 * `services/explainability_service.py`.  Adding a new handler in
 * `logging.json` requires a new entry here AND a matching entry on the
 * Python side.
 */
export const LOG_CONCERN_KEYS = [
  "prompts",
  "guards",
  "evals",
  "tools",
  "routing",
  "black_box",
  "phases",
  "identity",
  "drift",
  "framework_telemetry",
  "trust_trace",
  "authorization",
  "long_term_memory",
  "agent_ui_adapter_server",
  "agent_ui_adapter_transport",
  "agent_ui_adapter_translators",
  "explainability",
] as const;

export type LogConcern = (typeof LOG_CONCERN_KEYS)[number];

export const LOG_LEVELS = ["INFO", "WARN", "ERROR"] as const;
export type LogLevel = (typeof LOG_LEVELS)[number];

export const HealthResponseSchema = z.object({
  status: z.string(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const ErrorResponseSchema = z.object({
  detail: z.string(),
});
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
