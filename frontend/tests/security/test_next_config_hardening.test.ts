/**
 * next.config.ts hardening verification (S4.1.1).
 *
 * Sprint 4 §S4.1.1 acceptance criteria:
 *   - `productionBrowserSourceMaps: false` [FD3.SEC3]
 *   - `images.remotePatterns` is an explicit allowlist (empty or pinned) [FD3.SEC4]
 *
 * These are L1 deterministic tests — they parse the config export and
 * assert exact values. No I/O, no network, no non-determinism.
 *
 * Failure-paths first per TAP-4.
 */

import { describe, expect, it } from "vitest";
import config from "../../next.config";

describe("next.config.ts hardening (S4.1.1)", () => {
  // ── Failure-path: source maps MUST be disabled ──────────────────────
  it("REJECTS productionBrowserSourceMaps = true [FD3.SEC3]", () => {
    expect(config.productionBrowserSourceMaps).not.toBe(true);
  });

  it("productionBrowserSourceMaps is explicitly false", () => {
    expect(config.productionBrowserSourceMaps).toBe(false);
  });

  // ── Failure-path: remotePatterns MUST NOT be a wildcard ─────────────
  it("REJECTS images.remotePatterns containing a wildcard hostname", () => {
    const patterns = config.images?.remotePatterns ?? [];
    for (const pattern of patterns) {
      expect(pattern.hostname).not.toBe("**");
      expect(pattern.hostname).not.toBe("*");
    }
  });

  it("images.remotePatterns is an explicit allowlist (array)", () => {
    expect(Array.isArray(config.images?.remotePatterns)).toBe(true);
  });

  // ── reactStrictMode should be on ────────────────────────────────────
  it("reactStrictMode is enabled", () => {
    expect(config.reactStrictMode).toBe(true);
  });
});
