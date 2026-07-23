/**
 * Phase 4 — methods #30/#31 + in-adapter idempotent insertAttempt (FR-A9.1).
 * Red/green against InMemoryEngineDb (same EngineDb contract as drizzle).
 */

import { describe, expect, it } from "vitest";

import type { Attempt, QuizSession } from "../../../wire/engine_entities";
import { InMemoryEngineDb } from "./in_memory_engine_db";

const SUBJECT = "act-english";

function session(over: Partial<QuizSession> = {}): QuizSession {
  return {
    id: "sess-1",
    subject: SUBJECT,
    learner_id: "learner-a",
    mode: "adaptive",
    skill_focus: null,
    started_at: "2026-07-22T12:00:00.000Z",
    ended_at: null,
    score_correct: 0,
    score_total: 0,
    target_count: 30,
    current_question_id: null,
    ...over,
  };
}

function attempt(over: Partial<Attempt> = {}): Attempt {
  return {
    id: "att-1",
    subject: SUBJECT,
    session_id: "sess-1",
    question_id: "ti-gen-aaaaaaaaaaaaaaaa",
    chosen_letter: "A",
    correct: true,
    elapsed_ms: 1000,
    used_hint: false,
    created_at: "2026-07-22T12:01:00.000Z",
    resolution: "first_try",
    idempotency_key: "11111111-1111-4111-8111-111111111111",
    ...over,
  };
}

describe("setSessionCurrentQuestion (#30) + getNewestOpenSession (#31)", () => {
  it("pointer round-trips via getSession", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession(session());
    await db.setSessionCurrentQuestion("sess-1", "ti-gen-q4");
    const got = await db.getSession("sess-1");
    expect(got?.current_question_id).toBe("ti-gen-q4");
    await db.setSessionCurrentQuestion("sess-1", null);
    expect((await db.getSession("sess-1"))?.current_question_id).toBeNull();
  });

  it("getNewestOpenSession returns newest open and never a closed one", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession(
      session({
        id: "old-open",
        started_at: "2026-07-22T10:00:00.000Z",
      }),
    );
    await db.insertSession(
      session({
        id: "closed",
        started_at: "2026-07-22T11:00:00.000Z",
        ended_at: "2026-07-22T11:30:00.000Z",
        score_correct: 5,
        score_total: 10,
      }),
    );
    await db.insertSession(
      session({
        id: "newest-open",
        started_at: "2026-07-22T12:00:00.000Z",
      }),
    );
    const got = await db.getNewestOpenSession(SUBJECT, "learner-a");
    expect(got?.id).toBe("newest-open");
    expect(got?.ended_at).toBeNull();
  });

  it("getNewestOpenSession returns null when no open session", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession(
      session({
        id: "only-closed",
        ended_at: "2026-07-22T11:30:00.000Z",
      }),
    );
    expect(await db.getNewestOpenSession(SUBJECT, "learner-a")).toBeNull();
  });
});

describe("insertAttempt idempotency (FR-A9.1 DB half)", () => {
  it("same-key double insert → one row + already-existed", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession(session());
    const key = "22222222-2222-4222-8222-222222222222";
    const first = await db.insertAttempt(attempt({ id: "att-a", idempotency_key: key }));
    expect(first.status).toBe("inserted");
    const second = await db.insertAttempt(
      attempt({
        id: "att-b",
        idempotency_key: key,
        chosen_letter: "B", // different payload — stored row wins
      }),
    );
    expect(second.status).toBe("already-existed");
    expect(second.attempt.id).toBe("att-a");
    expect(second.attempt.chosen_letter).toBe("A");
    const rows = await db.listSessionAttempts("sess-1");
    expect(rows).toHaveLength(1);
  });

  it("new key → new row", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession(session());
    await db.insertAttempt(
      attempt({
        id: "att-1",
        idempotency_key: "33333333-3333-4333-8333-333333333333",
      }),
    );
    const second = await db.insertAttempt(
      attempt({
        id: "att-2",
        idempotency_key: "44444444-4444-4444-8444-444444444444",
        chosen_letter: "C",
      }),
    );
    expect(second.status).toBe("inserted");
    expect(await db.listSessionAttempts("sess-1")).toHaveLength(2);
  });
});
