/**
 * requireOwnedSession — FR-A2a ownership guard (T A.3).
 */

import { describe, expect, it, vi } from "vitest";
import { requireOwnedSession, type SessionLookup } from "./engine_guard";
import type { QuizSession } from "../wire/engine_entities";

function session(over: Partial<QuizSession> = {}): QuizSession {
  return {
    id: "sess-1",
    subject: "act-english",
    learner_id: "learner-A",
    mode: "adaptive",
    skill_focus: null,
    started_at: "2026-07-22T00:00:00.000Z",
    ended_at: null,
    score_correct: 0,
    score_total: 0,
    target_count: 30,
    current_question_id: null,
    ...over,
  };
}

describe("requireOwnedSession — FR-A2a", () => {
  it("returns ok + session when learner_id matches", async () => {
    const row = session();
    const getSession = vi.fn().mockResolvedValue(row);
    const db: SessionLookup = { getSession };
    const result = await requireOwnedSession(db, "sess-1", "learner-A");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.session).toEqual(row);
    expect(getSession).toHaveBeenCalledWith("sess-1");
  });

  it("404 when session is missing (before any dependent query)", async () => {
    const getSession = vi.fn().mockResolvedValue(null);
    const db: SessionLookup = { getSession };
    const result = await requireOwnedSession(db, "missing", "learner-A");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.response.status).toBe(404);
  });

  it("404 when learner A guesses learner B's session id", async () => {
    const getSession = vi.fn().mockResolvedValue(session({ learner_id: "learner-B" }));
    const db: SessionLookup = { getSession };
    const result = await requireOwnedSession(db, "sess-1", "learner-A");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.response.status).toBe(404);
    expect(getSession).toHaveBeenCalledTimes(1);
  });
});
