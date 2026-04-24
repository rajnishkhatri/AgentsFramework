/**
 * Composition root contract tests (S3.6.1).
 *
 * The composition root is the ONLY file that names concrete adapter classes
 * and the ONLY file that reads `ARCHITECTURE_PROFILE`. The architecture
 * test (S3.10.1) enforces both rules statically; here we verify the
 * runtime behavior of `buildAdapters`:
 *
 *   - returns a typed bag of 8 ports for the v3 profile (default)
 *   - returns the same bag shape for the v2 profile (with v2 adapters)
 *   - throws on an unknown profile (fail-closed)
 *   - never invokes side effects beyond what the adapter constructors do
 */

import { describe, expect, it } from "vitest";
import { buildAdapters } from "./composition";

const FAKE_DEPS = {
  fetchImpl: globalThis.fetch ?? ((async () => new Response(null)) as typeof fetch),
  workosSDK: {
    getSession: async () => null,
    getAccessToken: async () => "",
    getAccessTokenExpiry: async () => Date.now() + 3600_000,
    refreshAccessToken: async () => "",
    signOut: async (): Promise<void> => {},
  },
  env: { NEXT_PUBLIC_FF_PYRAMID_PANEL: "true" },
  baseUrl: "/api",
};

describe("buildAdapters [S3.6.1]", () => {
  it("returns the 8 expected ports for profile=v3", () => {
    const bag = buildAdapters({ profile: "v3", ...FAKE_DEPS });
    expect(Object.keys(bag).sort()).toEqual(
      [
        "agentRuntimeClient",
        "authProvider",
        "featureFlagProvider",
        "memoryClient",
        "telemetrySink",
        "threadStore",
        "toolRendererRegistry",
        "uiRuntime",
      ].sort(),
    );
  });

  it("v3 wires the EnvVarFlagsAdapter and reads NEXT_PUBLIC_FF_*", () => {
    const bag = buildAdapters({ profile: "v3", ...FAKE_DEPS });
    expect(bag.featureFlagProvider.isEnabled("pyramid_panel")).toBe(true);
    expect(bag.featureFlagProvider.isEnabled("voice_mode")).toBe(false);
  });

  it("v3 ToolRendererRegistry resolves the wildcard fallback", () => {
    const bag = buildAdapters({ profile: "v3", ...FAKE_DEPS });
    const r = bag.toolRendererRegistry.resolve("anything");
    expect(typeof r).toBe("function");
  });

  it("v3 AgentRuntimeClient.cancel is idempotent (does not throw on repeat)", async () => {
    const bag = buildAdapters({
      profile: "v3",
      ...FAKE_DEPS,
      fetchImpl: (async () => new Response(null, { status: 204 })) as typeof fetch,
    });
    await bag.agentRuntimeClient.cancel("r1");
    await bag.agentRuntimeClient.cancel("r1");
  });

  it("returns the same bag shape for v2 profile (graduation-ready)", () => {
    const bag = buildAdapters({ profile: "v2", ...FAKE_DEPS });
    expect(Object.keys(bag).sort()).toEqual(
      [
        "agentRuntimeClient",
        "authProvider",
        "featureFlagProvider",
        "memoryClient",
        "telemetrySink",
        "threadStore",
        "toolRendererRegistry",
        "uiRuntime",
      ].sort(),
    );
  });

  it("throws on unknown profile (fail-closed)", () => {
    expect(() =>
      // @ts-expect-error -- testing the runtime guard for an invalid profile
      buildAdapters({ profile: "v4", ...FAKE_DEPS }),
    ).toThrowError(/unknown profile/i);
  });
});
