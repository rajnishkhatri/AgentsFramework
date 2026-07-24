/**
 * FR-A9.2 / T A.13 — retry idempotent reads; surface write failures.
 */

import { describe, expect, it, vi } from "vitest";
import { HttpEngineDb } from "./http_engine_db";
import { EngineRepoError } from "../../../ports/engine/errors";

describe("HttpEngineDb retry (FR-A9.2)", () => {
  it("retries a transient 5xx read then succeeds", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(
        new Response("nope", { status: 503 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );
    const db = new HttpEngineDb({ baseUrl: "http://x", fetchImpl });
    await expect(db.listSkills("act-english")).resolves.toEqual([]);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("does not retry a failed write", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("nope", { status: 503 }));
    const db = new HttpEngineDb({ baseUrl: "http://x", fetchImpl });
    await expect(
      db.setSessionCurrentQuestion("s1", "q1"),
    ).rejects.toBeInstanceOf(EngineRepoError);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
