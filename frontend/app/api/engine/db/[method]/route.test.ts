/**
 * Fine-grained /api/engine/db/<method> — auth + server-only 404 (T A.10).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const { getSession, listSkills, insertQuestion, engineDb } = vi.hoisted(() => {
  const listSkills = vi.fn();
  const insertQuestion = vi.fn();
  return {
    getSession: vi.fn(),
    listSkills,
    insertQuestion,
    engineDb: vi.fn(() => ({ listSkills, insertQuestion })),
  };
});

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession },
  }),
  engineDb,
}));

import { POST } from "./route";

function req(method: string, args: unknown[]): NextRequest {
  return new NextRequest(`http://localhost/api/engine/db/${method}`, {
    method: "POST",
    body: JSON.stringify({ args }),
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("POST /api/engine/db/[method]", () => {
  it("401 and no DB when unauthenticated", async () => {
    getSession.mockResolvedValue(null);
    const res = await POST(req("listSkills", ["act-english"]), {
      params: Promise.resolve({ method: "listSkills" }),
    });
    expect(res.status).toBe(401);
    expect(engineDb).not.toHaveBeenCalled();
  });

  it("404 for server-only content writes (no handler surface)", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    const res = await POST(req("insertQuestion", [{}]), {
      params: Promise.resolve({ method: "insertQuestion" }),
    });
    expect(res.status).toBe(404);
    expect(insertQuestion).not.toHaveBeenCalled();
  });

  it("dispatches a fine-grained read", async () => {
    getSession.mockResolvedValue({ sub: "learner-A" });
    listSkills.mockResolvedValue([]);
    const res = await POST(req("listSkills", ["act-english"]), {
      params: Promise.resolve({ method: "listSkills" }),
    });
    expect(res.status).toBe(200);
    expect(listSkills).toHaveBeenCalledWith("act-english");
  });
});
