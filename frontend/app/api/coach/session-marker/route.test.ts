/**
 * Coach session-marker write route (ADR-0012 Amendment; FR-19) — L2.
 *
 * Fire-and-forget target of the quiz submit path. Failure paths first:
 * unauthenticated ⇒ 401 and the store is NEVER touched; malformed body ⇒
 * 400 and the store is never touched. The `user_id` is the SERVER-derived
 * session subject (S3) — a client-supplied user_id in the body is ignored.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const getSession = vi.fn();
const markSubmitted = vi.fn();
const isSubmitted = vi.fn();

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession },
  }),
  coachMarkerRepo: () => ({ markSubmitted, isSubmitted }),
}));

import { POST } from "./route";

function req(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/coach/session-marker", {
    method: "POST",
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("marker write route — failure paths first", () => {
  it("401 and NO write when there is no session", async () => {
    getSession.mockResolvedValue(null);
    const res = await POST(req({ question_id: "q-punc-1" }));
    expect(res.status).toBe(401);
    expect(markSubmitted).not.toHaveBeenCalled();
  });

  it("400 and NO write on a body without question_id", async () => {
    getSession.mockResolvedValue({ sub: "Garvit" });
    const res = await POST(req({}));
    expect(res.status).toBe(400);
    expect(markSubmitted).not.toHaveBeenCalled();
  });

  it("400 and NO write on unparseable JSON", async () => {
    getSession.mockResolvedValue({ sub: "Garvit" });
    const res = await POST(req("{not json"));
    expect(res.status).toBe(400);
    expect(markSubmitted).not.toHaveBeenCalled();
  });
});

describe("marker write route — authed write", () => {
  it("writes {server user_id, question_id} and returns 204", async () => {
    getSession.mockResolvedValue({ sub: "Garvit" });
    markSubmitted.mockResolvedValue(undefined);
    const res = await POST(req({ question_id: "q-punc-1" }));
    expect(res.status).toBe(204);
    expect(markSubmitted).toHaveBeenCalledTimes(1);
    expect(markSubmitted).toHaveBeenCalledWith("Garvit", "q-punc-1");
  });

  it("IGNORES a client-supplied user_id (S3: server-derived subject only)", async () => {
    getSession.mockResolvedValue({ sub: "Garvit" });
    markSubmitted.mockResolvedValue(undefined);
    await POST(req({ question_id: "q-punc-1", user_id: "someone-else" }));
    expect(markSubmitted).toHaveBeenCalledWith("Garvit", "q-punc-1");
  });
});
