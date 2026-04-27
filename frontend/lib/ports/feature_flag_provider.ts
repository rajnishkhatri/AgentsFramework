/**
 * FeatureFlagProvider -- vendor-neutral feature flag port.
 *
 * V3 implementation: EnvVarFlagsAdapter (reads `NEXT_PUBLIC_FF_*` at module
 * load time). Future implementations may include LaunchDarkly, Statsig, etc.
 *
 * Port rules: P1, P2, P3, P4, **P5 sync exception** (justified below), P6.
 */

export type FeatureFlagName =
  | "pyramid_panel"
  | "voice_mode"
  | "per_tool_authorization"
  | "json_run_export";

/**
 * Vendor-neutral feature flag port.
 *
 * Behavioral contract:
 *   - **P5 exception**: lookups are SYNCHRONOUS by design. React components
 *     read flags at render time; an async lookup would force a Suspense
 *     boundary on every flag-gated component, causing avoidable waterfalls.
 *     The `EnvVarFlagsAdapter` reads `process.env.NEXT_PUBLIC_FF_*` at
 *     module load time so all lookups become pure dictionary access.
 *   - Unknown flags MUST return `false` (or the documented default) -- never
 *     throw -- so adding a new flag without an adapter update is safe.
 *   - `pyramid_panel`, `voice_mode`, `per_tool_authorization`, and
 *     `json_run_export` are off by default in V3.
 */
export interface FeatureFlagProvider {
  /**
   * Returns whether the flag is on. Synchronous render-time lookup (P5
   * exception). Unknown flags return `false`.
   */
  isEnabled(flag: FeatureFlagName): boolean;
}
