/**
 * L2 tests for EnvVarFlagsAdapter (S3.3.5).
 *
 * Sync-by-design (P5 exception). Tests pass an explicit env dictionary so
 * the adapter is fully deterministic.
 */

import { describe, expect, it } from "vitest";
import { EnvVarFlagsAdapter } from "./env_var_flags_adapter";

describe("EnvVarFlagsAdapter defaults", () => {
  it("returns false for unknown flags (never throws)", () => {
    const flags = new EnvVarFlagsAdapter({ env: {} });
    expect(flags.isEnabled("voice_mode")).toBe(false);
  });

  it("returns false for pyramid_panel and voice_mode by default in V3", () => {
    const flags = new EnvVarFlagsAdapter({ env: {} });
    expect(flags.isEnabled("pyramid_panel")).toBe(false);
    expect(flags.isEnabled("voice_mode")).toBe(false);
    expect(flags.isEnabled("per_tool_authorization")).toBe(false);
    expect(flags.isEnabled("json_run_export")).toBe(false);
  });
});

describe("EnvVarFlagsAdapter env-var truthy parsing", () => {
  it("treats '1', 'true', 'on', 'yes' as enabled (case insensitive)", () => {
    for (const v of ["1", "true", "TRUE", "on", "ON", "yes", "YES"]) {
      const flags = new EnvVarFlagsAdapter({
        env: { NEXT_PUBLIC_FF_PYRAMID_PANEL: v },
      });
      expect(flags.isEnabled("pyramid_panel"), `value "${v}" should enable`).toBe(
        true,
      );
    }
  });

  it("treats other values as disabled", () => {
    for (const v of ["0", "false", "off", "no", ""]) {
      const flags = new EnvVarFlagsAdapter({
        env: { NEXT_PUBLIC_FF_PYRAMID_PANEL: v },
      });
      expect(flags.isEnabled("pyramid_panel"), `value "${v}" should disable`).toBe(
        false,
      );
    }
  });
});

describe("EnvVarFlagsAdapter env reads at module load (frozen)", () => {
  it("does not see env mutations after construction (snapshot semantics)", () => {
    const env: Record<string, string | undefined> = {};
    const flags = new EnvVarFlagsAdapter({ env });
    env.NEXT_PUBLIC_FF_VOICE_MODE = "true";
    expect(flags.isEnabled("voice_mode")).toBe(false);
  });
});

describe("EnvVarFlagsAdapter commit_first_coach (staged ON)", () => {
  it("defaults ON when env is unset (v3 is now the prod default)", () => {
    // Rollout complete: commit-first coach is the unconditional default in
    // every environment, including prod (NODE_ENV unset / production). The
    // only way to get the legacy reveal-and-explain coach is an explicit
    // NEXT_PUBLIC_FF_COMMIT_FIRST_COACH=0.
    const flags = new EnvVarFlagsAdapter({ env: {} });
    expect(flags.isEnabled("commit_first_coach")).toBe(true);
  });

  it("defaults ON under an explicit prod NODE_ENV (no env flag set)", () => {
    const flags = new EnvVarFlagsAdapter({
      env: { NODE_ENV: "production" },
    });
    expect(flags.isEnabled("commit_first_coach")).toBe(true);
  });

  it("stays ON when E2E_BYPASS_AUTH=1 (dev/bypass soak)", () => {
    const flags = new EnvVarFlagsAdapter({
      env: { E2E_BYPASS_AUTH: "1" },
    });
    expect(flags.isEnabled("commit_first_coach")).toBe(true);
  });

  it("stays ON when NODE_ENV=development", () => {
    const flags = new EnvVarFlagsAdapter({
      env: { NODE_ENV: "development" },
    });
    expect(flags.isEnabled("commit_first_coach")).toBe(true);
  });

  it("honors an explicit NEXT_PUBLIC_FF_COMMIT_FIRST_COACH=0 kill switch", () => {
    // Explicit falsy wins over every default — the only way back to the
    // legacy coach, in prod or anywhere else.
    const offInProd = new EnvVarFlagsAdapter({
      env: { NODE_ENV: "production", NEXT_PUBLIC_FF_COMMIT_FIRST_COACH: "0" },
    });
    expect(offInProd.isEnabled("commit_first_coach")).toBe(false);

    const offOverBypass = new EnvVarFlagsAdapter({
      env: {
        E2E_BYPASS_AUTH: "1",
        NEXT_PUBLIC_FF_COMMIT_FIRST_COACH: "0",
      },
    });
    expect(offOverBypass.isEnabled("commit_first_coach")).toBe(false);

    const on = new EnvVarFlagsAdapter({
      env: { NEXT_PUBLIC_FF_COMMIT_FIRST_COACH: "true" },
    });
    expect(on.isEnabled("commit_first_coach")).toBe(true);
  });
});
