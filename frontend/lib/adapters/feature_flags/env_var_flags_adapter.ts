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
  commit_first_coach: "NEXT_PUBLIC_FF_COMMIT_FIRST_COACH",
};

const TRUTHY = new Set(["1", "true", "on", "yes"]);
const FALSY = new Set(["0", "false", "off", "no", ""]);

function isTruthy(v: string | undefined): boolean {
  if (typeof v !== "string") return false;
  return TRUTHY.has(v.toLowerCase());
}

/** True when the env var is an explicit disable (incl. empty string). */
function isExplicitFalsy(v: string | undefined): boolean {
  if (typeof v !== "string") return false;
  return FALSY.has(v.toLowerCase());
}

/**
 * commit_first_coach default (FR-14): ON in dev or E2E bypass soak; OFF in
 * prod until staged. Explicit NEXT_PUBLIC_FF_COMMIT_FIRST_COACH wins.
 */
function commitFirstCoachDefault(
  env: Readonly<Record<string, string | undefined>>,
): boolean {
  const explicit = env.NEXT_PUBLIC_FF_COMMIT_FIRST_COACH;
  if (isTruthy(explicit)) return true;
  if (isExplicitFalsy(explicit)) return false;
  if (env.E2E_BYPASS_AUTH === "1") return true;
  if (env.NODE_ENV === "development") return true;
  return false;
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
      commit_first_coach: false,
    };
    for (const [flag, key] of Object.entries(FLAG_TO_ENV) as Array<
      [FeatureFlagName, string]
    >) {
      if (flag === "commit_first_coach") {
        snap[flag] = commitFirstCoachDefault(opts.env);
      } else {
        snap[flag] = isTruthy(opts.env[key]);
      }
    }
    this.snapshot = Object.freeze(snap);
    log.info("flag snapshot loaded", {
      adapter: "env_var_flags",
      pyramid_panel: snap.pyramid_panel,
      voice_mode: snap.voice_mode,
      per_tool_authorization: snap.per_tool_authorization,
      json_run_export: snap.json_run_export,
      commit_first_coach: snap.commit_first_coach,
    });
  }

  isEnabled(flag: FeatureFlagName): boolean {
    return this.snapshot[flag] ?? false;
  }
}
