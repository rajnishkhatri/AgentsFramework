/**
 * Phase 2.1 — coach BFF stream route (FR-F, §5; L1).
 *
 * The coach rides the CHAT runtime (plan OD-3), so this route is the same thin
 * auth-gate + byte-forward as /api/run/stream (B6/F-R4/FE-AP-3): authenticate via
 * the AuthProvider port, forward to the middleware with the WorkOS bearer + SSE
 * accept, pipe the response through proxySSE. No business logic; no secrets
 * (F-R9). The coach `agent_id` rides in the client body, not this route.
 *
 * Failure path first: no session → 401, and the request is NEVER forwarded.
 */

import { describe, expect, it, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const getSession = vi.fn();
const getAccessToken = vi.fn();
const forwardToMiddleware = vi.fn();
const proxySSE = vi.fn();
const isSubmitted = vi.fn();
const markSubmitted = vi.fn();

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession, getAccessToken },
  }),
  coachMarkerRepo: () => ({ isSubmitted, markSubmitted }),
  forwardToMiddleware: (...args: unknown[]) => forwardToMiddleware(...args),
}));
vi.mock("@/lib/transport/edge_proxy", () => ({
  proxySSE: (...args: unknown[]) => proxySSE(...args),
}));

import { POST } from "./route";

function req(body = '{"thread_id":"t1","input":{},"agent_id":"subject-coach-english"}'): NextRequest {
  return new NextRequest("http://localhost/api/coach/run/stream", {
    method: "POST",
    body,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("coach stream route — failure path first (auth gate)", () => {
  it("returns 401 and does NOT forward when there is no session", async () => {
    getSession.mockResolvedValue(null);
    const res = await POST(req());
    expect(res.status).toBe(401);
    expect(forwardToMiddleware).not.toHaveBeenCalled();
  });

  it("treats a getSession throw as unauthenticated (401, no forward)", async () => {
    getSession.mockRejectedValue(new Error("cookie parse failed"));
    const res = await POST(req());
    expect(res.status).toBe(401);
    expect(forwardToMiddleware).not.toHaveBeenCalled();
  });
});

describe("coach stream route — authed: forward only", () => {
  it("forwards to /run/stream with bearer + SSE accept, pipes through proxySSE", async () => {
    getSession.mockResolvedValue({ sub: "u1" });
    getAccessToken.mockResolvedValue("tok-123");
    const upstream = new Response("data: hi\n\n");
    forwardToMiddleware.mockResolvedValue(upstream);
    const proxied = new Response("proxied");
    proxySSE.mockReturnValue(proxied);

    const res = await POST(req());

    expect(forwardToMiddleware).toHaveBeenCalledTimes(1);
    const [path, init] = forwardToMiddleware.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/run/stream");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers.authorization).toBe("Bearer tok-123");
    expect(headers.accept).toBe("text/event-stream");
    expect(proxySSE).toHaveBeenCalledWith(upstream);
    expect(res).toBe(proxied);
  });
});

describe("coach stream route — ADR-0012 sanitizer (FR-19/FR-21)", () => {
  const question = {
    id: "q-punc-1",
    stem: "Which choice best fixes the underlined portion?",
    answer_letter: "B",
    per_choice_rationale: { A: "unclosed" },
    why_correct_md: "closes the clause",
    why_tempted_md: "reads fine",
  };

  function coachBody(mode: string) {
    return JSON.stringify({
      thread_id: "t1",
      agent_id: "subject-coach-english",
      input: {
        messages: [{ role: "user", content: "help" }],
        coach_context: {
          mode,
          question_id: "q-punc-1",
          skill_id: "s-punc",
          question,
        },
      },
    });
  }

  function forwardedBody(): Record<string, unknown> {
    const [, init] = forwardToMiddleware.mock.calls[0] as [string, RequestInit];
    return JSON.parse(init.body as string);
  }

  beforeEach(() => {
    getSession.mockResolvedValue({ sub: "maya" });
    getAccessToken.mockResolvedValue("tok-123");
    forwardToMiddleware.mockResolvedValue(new Response("data: hi\n\n"));
    proxySSE.mockReturnValue(new Response("proxied"));
  });

  it("SPOOF first: no marker + client claims post_feedback ⇒ 4 fields stripped", async () => {
    isSubmitted.mockResolvedValue(false);
    await POST(req(coachBody("post_feedback")));

    const body = forwardedBody();
    const ctx = (body.input as Record<string, unknown>)
      .coach_context as Record<string, unknown>;
    const q = ctx.question as Record<string, unknown>;
    expect(ctx.mode).toBe("pre_submit");
    for (const field of [
      "answer_letter",
      "per_choice_rationale",
      "why_correct_md",
      "why_tempted_md",
    ]) {
      expect(q).not.toHaveProperty(field);
    }
    expect(q.stem).toBe(question.stem);
    // Mode derived from the SERVER-side session subject, never client input.
    expect(isSubmitted).toHaveBeenCalledWith("maya", "q-punc-1");
  });

  it("marker present ⇒ post_feedback with full question forwarded (FR-21)", async () => {
    isSubmitted.mockResolvedValue(true);
    await POST(req(coachBody("pre_submit")));

    const ctx = (forwardedBody().input as Record<string, unknown>)
      .coach_context as Record<string, unknown>;
    expect(ctx.mode).toBe("post_feedback");
    expect(ctx.question).toHaveProperty("answer_letter", "B");
  });

  it("marker lookup failure fails CLOSED to pre_submit (fields stripped)", async () => {
    isSubmitted.mockRejectedValue(new Error("store down"));
    await POST(req(coachBody("post_feedback")));

    const ctx = (forwardedBody().input as Record<string, unknown>)
      .coach_context as Record<string, unknown>;
    expect(ctx.mode).toBe("pre_submit");
    expect(ctx.question).not.toHaveProperty("answer_letter");
  });

  it("plain chat body (no coach_context) is forwarded byte-identical", async () => {
    const body = '{"thread_id":"t1","input":{"messages":[]}}';
    await POST(req(body));
    const [, init] = forwardToMiddleware.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe(body);
    expect(isSubmitted).not.toHaveBeenCalled();
  });

  it("coach_context with MISSING question_id still fails CLOSED (fields stripped, no lookup)", async () => {
    // Review finding C1: the sanitize block must not be gated on a parseable
    // question_id — a coach_context without one is a malformed/adversarial
    // body and gets the pre_submit strip, never a byte-identical forward.
    isSubmitted.mockResolvedValue(true);
    const body = JSON.stringify({
      thread_id: "t1",
      agent_id: "subject-coach-english",
      input: {
        messages: [{ role: "user", content: "help" }],
        coach_context: { mode: "post_feedback", skill_id: "s-punc", question },
      },
    });
    await POST(req(body));

    const ctx = (forwardedBody().input as Record<string, unknown>)
      .coach_context as Record<string, unknown>;
    expect(ctx.mode).toBe("pre_submit");
    expect(ctx.question).not.toHaveProperty("answer_letter");
    expect(isSubmitted).not.toHaveBeenCalled();
  });

  it("question_id ↔ question.id MISMATCH fails CLOSED even when the marker says submitted", async () => {
    // Review finding C2: the marker is keyed by question_id — without the
    // cross-check, a client could name an already-submitted question_id
    // while embedding a DIFFERENT question's answer fields.
    isSubmitted.mockResolvedValue(true);
    const body = JSON.stringify({
      thread_id: "t1",
      agent_id: "subject-coach-english",
      input: {
        messages: [{ role: "user", content: "help" }],
        coach_context: {
          mode: "post_feedback",
          question_id: "q-already-submitted",
          skill_id: "s-punc",
          question, // question.id === "q-punc-1" ≠ q-already-submitted
        },
      },
    });
    await POST(req(body));

    const ctx = (forwardedBody().input as Record<string, unknown>)
      .coach_context as Record<string, unknown>;
    expect(ctx.mode).toBe("pre_submit");
    expect(ctx.question).not.toHaveProperty("answer_letter");
    expect(isSubmitted).not.toHaveBeenCalled();
  });
});
