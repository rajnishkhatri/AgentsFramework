/**
 * T A.9 / A.11 — coarse loaders make exactly ONE fetch each.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  EngineClient,
  _resetBrowserEngineClient,
} from "./engine_client";

afterEach(() => {
  _resetBrowserEngineClient();
  vi.restoreAllMocks();
});

describe("EngineClient — one call per coarse loader (FR-A6 / §7)", () => {
  it("loadDashboard / loadSummary / loadSkillDetail / nextItem each fetch once", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("next")
        ? { empty: true, question: null, hints: [], skill_id: null }
        : {
            skills: [],
            skill_states: [],
            misses: [],
            sessions: [],
            focus_skill_id: null,
            focus_question: null,
            review_misses_count: 0,
            session: {
              id: "s1",
              subject: "act-english",
              learner_id: "u1",
              mode: "adaptive",
              skill_focus: null,
              started_at: "t",
              ended_at: null,
              score_correct: 0,
              score_total: 0,
              target_count: 30,
            },
            served_question_ids: [],
            attempts: [],
            miss_questions: [],
            skill: null,
            tutorial: null,
            accuracy_rows: [],
          };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });

    const client = new EngineClient({ baseUrl: "http://x", fetchImpl });

    await client.loadDashboard({ subject: "act-english" });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(String(fetchImpl.mock.calls[0]![0])).toContain("/api/engine/dashboard");

    fetchImpl.mockClear();
    await client.loadSummary("sess-1");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(String(fetchImpl.mock.calls[0]![0])).toContain("/api/engine/summary");

    fetchImpl.mockClear();
    await client.loadSkillDetail({ subject: "act-english", skillId: "s-punc" });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(String(fetchImpl.mock.calls[0]![0])).toContain("/api/engine/skill/s-punc");

    fetchImpl.mockClear();
    await client.nextItem("sess-1");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(String(fetchImpl.mock.calls[0]![0])).toContain("/api/engine/next");
  });

  it("closeSession posts only the session id to the server-tally endpoint (FR-C1)", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          id: "sess-1",
          subject: "act-english",
          learner_id: "u1",
          mode: "adaptive",
          skill_focus: null,
          started_at: "t",
          ended_at: "t2",
          score_correct: 1,
          score_total: 2,
          target_count: 2,
          current_question_id: null,
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );
    const client = new EngineClient({ baseUrl: "http://x", fetchImpl });

    await client.closeSession("sess-1");

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://x/api/engine/session/close",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ session_id: "sess-1" }),
      }),
    );
  });
});
