/**
 * POST /api/engine/session/open — auth + identity failure paths (FR-A1, FR-A2).
 *
 * T A.1: no WorkOS session → 401, and the engine DB seam is never touched.
 * T A.2: a client body naming learnerId is ignored; handler uses session-derived id.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const { getSession, insertSession, engineDb } = vi.hoisted(() => {
  const insertSession = vi.fn();
  return {
    getSession: vi.fn(),
    insertSession,
    engineDb: vi.fn(() => ({ insertSession })),
  };
});

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession },
  }),
  engineDb,
}));

import { POST } from "./route";

function req(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/engine/session/open", {
    method: "POST",
    body: typeof body === "string" ? body : JSON.stringify(body),
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  insertSession.mockResolvedValue(undefined);
});

describe("POST /api/engine/session/open — FR-A1 (no session → 401, no DB)", () => {
  it("401 and engineDb is never called when there is no WorkOS session", async () => {
    getSession.mockResolvedValue(null);
    const res = await POST(req({ subject: "act-english", mode: "adaptive" }));
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
    expect(insertSession).not.toHaveBeenCalled();
  });

  it("401 and engineDb is never called when getSession throws", async () => {
    getSession.mockRejectedValue(new Error("cookie parse failed"));
    const res = await POST(req({ subject: "act-english", mode: "adaptive" }));
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
  });
});

describe("POST /api/engine/session/open — FR-A2 (server-derived learnerId)", () => {
  it("ignores a client-supplied learnerId and uses the session subject", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    const res = await POST(
      req({
        subject: "act-english",
        mode: "adaptive",
        learnerId: "learner-B-liar",
        learner_id: "learner-B-liar",
      }),
    );
    expect(res.status).toBe(200);
    expect(engineDb).toHaveBeenCalledTimes(1);
    expect(insertSession).toHaveBeenCalledTimes(1);
    const inserted = insertSession.mock.calls[0]![0] as { learner_id: string };
    expect(inserted.learner_id).toBe("learner-A");
  });
});
