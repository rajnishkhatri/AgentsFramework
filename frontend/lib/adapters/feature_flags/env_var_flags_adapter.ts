/**
 * EnvVarFlagsAdapter (S3.3.5, V3 FeatureFlagProvider).
 *
 * Reads `NEXT_PUBLIC_FF_*` env vars at construction time and caches the
 * snapshot. Lookups are pure dictionary access so React components can call
 * `isEnabled()` at render time without paying for a Suspense round trip
 * (P5 exception, justified in `lib/ports/feature_flag_provider.ts`).
 *
 * SDK isolation: no SDK -- this adapter has no third-party deps.
 */

import type {
  FeatureFlagName,
  FeatureFlagProvider,
} from "../../ports/feature_flag_provider";
import { createAdapterLogger, type Logger } from "../_logger";

const log: Logger = createAdapterLogger("feature_flags");

const FLAG_TO_ENV: Record<FeatureFlagName, string> = {
  pyramid_panel: "NEXT_PUBLIC_FF_PYRAMID_PANEL",
  voice_mode: "NEXT_PUBLIC_FF_VOICE_MODE",
  per_tool_authorization: "NEXT_PUBLIC_FF_PER_TOOL_AUTHORIZATION",
  json_run_export: "NEXT_PUBLIC_FF_JSON_RUN_EXPORT",
};

const TRUTHY = new Set(["1", "true", "on", "yes"]);

function isTruthy(v: string | undefined): boolean {
  if (typeof v !== "string") return false;
  return TRUTHY.has(v.toLowerCase());
}

export interface EnvVarFlagsAdapterOptions {
  readonly env: Readonly<Record<string, string | undefined>>;
}

export class EnvVarFlagsAdapter implements FeatureFlagProvider {
  private readonly snapshot: Readonly<Record<FeatureFlagName, boolean>>;

  constructor(opts: EnvVarFlagsAdapterOptions) {
    const snap: Record<FeatureFlagName, boolean> = {
      pyramid_panel: false,
      voice_mode: false,
      per_tool_authorization: false,
      json_run_export: false,
    };
    for (const [flag, key] of Object.entries(FLAG_TO_ENV) as Array<
      [FeatureFlagName, string]
    >) {
      snap[flag] = isTruthy(opts.env[key]);
    }
    this.snapshot = Object.freeze(snap);
    log.info("flag snapshot loaded", {
      adapter: "env_var_flags",
      pyramid_panel: snap.pyramid_panel,
      voice_mode: snap.voice_mode,
      per_tool_authorization: snap.per_tool_authorization,
      json_run_export: snap.json_run_export,
    });
  }

  isEnabled(flag: FeatureFlagName): boolean {
    return this.snapshot[flag] ?? false;
  }
}
