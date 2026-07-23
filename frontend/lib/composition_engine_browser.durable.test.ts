/**
 * T A.7 — flag-gated atomic swap: durable_engine ON → HttpEngineDb;
 * OFF → InMemoryEngineDb (coexist during validation).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { buildBrowserEngineAdapters } from "./composition_engine_browser";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("buildBrowserEngineAdapters — durable_engine flag (T A.7)", () => {
  it("flag off → InMemoryEngineDb (no network)", async () => {
    vi.stubEnv("NEXT_PUBLIC_FF_DURABLE_ENGINE", "0");
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const bag = buildBrowserEngineAdapters();
    const skills = await bag.skillTaxonomy.list("act-english");
    expect(skills).toEqual([]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("flag on → HttpEngineDb (fetches /api/engine/db/*)", async () => {
    vi.stubEnv("NEXT_PUBLIC_FF_DURABLE_ENGINE", "1");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const bag = buildBrowserEngineAdapters({ questionSource: "bank" });
    await bag.skillTaxonomy.list("act-english");
    expect(fetchSpy).toHaveBeenCalled();
    expect(String(fetchSpy.mock.calls[0]![0])).toContain("/api/engine/db/");
  });
});
