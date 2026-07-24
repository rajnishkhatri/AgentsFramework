/**
 * FR-A4 disposition totality — every EngineDb method resolves to a fine-grained
 * route fetch or a typed server-only throw (T A.5). Proves behavior, not just
 * TypeScript shape.
 */

import { describe, expect, it, vi } from "vitest";
import {
  ENGINE_DB_DISPOSITION,
  FINE_ENGINE_DB_METHODS,
  SERVER_ONLY_ENGINE_DB_METHODS,
  type EngineDbMethodName,
} from "./engine_db_disposition";
import { HttpEngineDb } from "./http_engine_db";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { EngineDb } from "./engine_db";

/** Compile-time: disposition keys cover every EngineDb method. */
const _dispositionCoversEngineDb: {
  [K in keyof EngineDb]: (typeof ENGINE_DB_DISPOSITION)[K & EngineDbMethodName];
} = ENGINE_DB_DISPOSITION;

void _dispositionCoversEngineDb;

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("HttpEngineDb — FR-A4 disposition totality", () => {
  it("disposition table has exactly 32 methods (5 server-only)", () => {
    expect(Object.keys(ENGINE_DB_DISPOSITION)).toHaveLength(32);
    expect(SERVER_ONLY_ENGINE_DB_METHODS).toEqual([
      "insertQuestion",
      "insertHint",
      "insertTestItem",
      "insertTestBlueprint",
      "listAlreadyCorrectQuestionIds",
    ]);
    expect(FINE_ENGINE_DB_METHODS).toHaveLength(27);
  });

  it("the 5 server-only methods throw typed EngineRepoError without fetching", async () => {
    const fetchImpl = vi.fn();
    const db = new HttpEngineDb({ baseUrl: "", fetchImpl });
    for (const method of SERVER_ONLY_ENGINE_DB_METHODS) {
      await expect(
        (db[method] as (...args: never[]) => Promise<unknown>).call(db),
      ).rejects.toSatisfy(
        (err: unknown) =>
          err instanceof EngineRepoError && err.message === "server-only method",
      );
    }
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("every fine-grained method fetches /api/engine/db/<method>", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      // Return a JSON null / empty shape that won't throw on parse for most reads.
      if (url.includes("insertAttempt")) {
        return jsonRes({
          status: "inserted",
          attempt: {
            id: "a1",
            subject: "act-english",
            session_id: "s1",
            question_id: "q1",
            chosen_letter: "A",
            correct: true,
            elapsed_ms: 1,
            used_hint: false,
            created_at: "2026-07-22T00:00:00.000Z",
            idempotency_key: "k1",
          },
        });
      }
      if (
        url.includes("insertSession") ||
        url.includes("upsertSkillState") ||
        url.includes("setSessionCurrentQuestion") ||
        url.includes("insert")
      ) {
        return jsonRes(null);
      }
      if (url.includes("list") || url.includes("accuracy")) {
        return jsonRes([]);
      }
      return jsonRes(null);
    });

    const db = new HttpEngineDb({ baseUrl: "http://localhost", fetchImpl });

    // Representative args per arity — we only assert URL + that fetch ran.
    const calls: Array<[EngineDbMethodName, unknown[]]> = [
      ["listSkillState", ["act-english", "u1"]],
      ["listSkills", ["act-english"]],
      ["getSkillByKey", ["act-english", "punc"]],
      ["listSkillIds", ["act-english"]],
      ["nextReviewedQuestion", ["act-english", "s1", []]],
      ["getQuestion", ["q1"]],
      ["listReviewedHints", ["act-english", "q1"]],
      ["listReviewedTestItems", ["act-english"]],
      ["getTestBlueprint", ["bp1"]],
      ["insertSession", [{ id: "s1" }]],
      ["getSession", ["s1"]],
      ["patchSessionClose", ["s1", { ended_at: "t", score_correct: 0, score_total: 1 }]],
      ["listClosedSessionsByLearner", ["act-english", "u1"]],
      ["setSessionCurrentQuestion", ["s1", "q1"]],
      ["getNewestOpenSession", ["act-english", "u1"]],
      [
        "insertAttempt",
        [
          {
            id: "a1",
            subject: "act-english",
            session_id: "s1",
            question_id: "q1",
            chosen_letter: "A",
            correct: true,
            elapsed_ms: 1,
            used_hint: false,
            created_at: "2026-07-22T00:00:00.000Z",
            idempotency_key: "k1",
          },
        ],
      ],
      ["listMisses", ["act-english", "u1"]],
      ["listSessionQuestionIds", ["s1"]],
      ["listSessionAttempts", ["s1"]],
      ["listSessionSkillIds", ["s1"]],
      ["accuracyRowsBySkill", ["act-english", "u1", "sk1", 5]],
      ["getSkillState", ["act-english", "sk1", "u1"]],
      ["upsertSkillState", [{ id: "ss1" }]],
      ["getContentString", ["act-english", "k", "en"]],
      ["listContentStrings", ["act-english", "en"]],
      ["getTutorial", ["act-english", "sk1"]],
      ["listProgressPoints", ["act-english", "u1"]],
    ];

    expect(calls.map(([m]) => m).sort()).toEqual([...FINE_ENGINE_DB_METHODS].sort());

    for (const [method, args] of calls) {
      fetchImpl.mockClear();
      await (db[method] as (...a: unknown[]) => Promise<unknown>)(...args);
      expect(fetchImpl).toHaveBeenCalledTimes(1);
      const url = String(fetchImpl.mock.calls[0]![0]);
      expect(url).toBe(`http://localhost/api/engine/db/${method}`);
    }
  });
});
