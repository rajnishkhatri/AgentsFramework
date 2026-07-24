/**
 * HttpEngineDb — browser EngineDb that fans out to BFF `/api/engine/*`
 * (coach-v3 FR-A4 / ADR-0038). Same-origin cookie session (AuthKit); no bearer
 * token. Server-only content writes throw typed — never a silent success.
 *
 * Returns `wire/engine_entities` shapes only (A4/F-R8). Retry/timeout for
 * idempotent reads lands in T A.13.
 */

import type {
  Attempt,
  Hint,
  ProgressPoint,
  Question,
  QuizSession,
  Skill,
  SkillAccuracyRow,
  SkillState,
  TestBlueprint,
  TestItem,
  Tutorial,
} from "../../../wire/engine_entities";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { EngineDb, InsertAttemptResult, SessionClosePatch } from "./engine_db";
import {
  ENGINE_DB_DISPOSITION,
  type EngineDbMethodName,
} from "./engine_db_disposition";

export interface HttpEngineDbOptions {
  /** Origin prefix, e.g. "" or "http://localhost:3000". Trailing slash stripped. */
  readonly baseUrl?: string;
  readonly fetchImpl?: typeof fetch;
}

export class HttpEngineDb implements EngineDb {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: HttpEngineDbOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? "").replace(/\/$/, "");
    this.fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  private serverOnly(): never {
    throw new EngineRepoError("server-only method");
  }

  /** FR-A9.2: only idempotent reads retry; writes surface failures. */
  private static readonly WRITE_METHODS = new Set<EngineDbMethodName>([
    "insertSession",
    "patchSessionClose",
    "setSessionCurrentQuestion",
    "insertAttempt",
    "upsertSkillState",
  ]);

  private async call<T>(method: EngineDbMethodName, args: unknown[]): Promise<T> {
    if (ENGINE_DB_DISPOSITION[method] === "server-only") {
      this.serverOnly();
    }
    const retryable = !HttpEngineDb.WRITE_METHODS.has(method);
    const maxAttempts = retryable ? 3 : 1;
    let lastErr: unknown;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await this.callOnce<T>(method, args);
      } catch (e) {
        lastErr = e;
        const retry =
          retryable &&
          attempt < maxAttempts &&
          e instanceof EngineRepoError &&
          (/\(5\d\d\)$/.test(e.message) || /failed:/.test(e.message));
        if (!retry) throw e;
        await new Promise((r) => setTimeout(r, 25 * attempt));
      }
    }
    throw lastErr;
  }

  private async callOnce<T>(
    method: EngineDbMethodName,
    args: unknown[],
  ): Promise<T> {
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}/api/engine/db/${method}`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ args }),
        cache: "no-store",
      });
    } catch (e) {
      throw new EngineRepoError(
        `${method} failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
    if (!res.ok) {
      throw new EngineRepoError(`${method} failed (${res.status})`);
    }
    // 204 / empty body → undefined
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    if (!text) return undefined as T;
    return JSON.parse(text) as T;
  }

  // --- skill ---
  listSkills(subject: string): Promise<Skill[]> {
    return this.call("listSkills", [subject]);
  }
  getSkillByKey(subject: string, key: string): Promise<Skill | null> {
    return this.call("getSkillByKey", [subject, key]);
  }
  listSkillIds(subject: string): Promise<string[]> {
    return this.call("listSkillIds", [subject]);
  }

  // --- question ---
  nextReviewedQuestion(
    subject: string,
    skillId: string,
    excludeIds?: readonly string[],
  ): Promise<Question | null> {
    return this.call("nextReviewedQuestion", [subject, skillId, excludeIds ?? []]);
  }
  getQuestion(id: string): Promise<Question | null> {
    return this.call("getQuestion", [id]);
  }
  async insertQuestion(_q: Question): Promise<void> {
    this.serverOnly();
  }

  // --- hint ---
  listReviewedHints(
    subject: string,
    questionId: string,
    choiceLetter?: string | null,
  ): Promise<Hint[]> {
    return this.call("listReviewedHints", [
      subject,
      questionId,
      choiceLetter ?? null,
    ]);
  }
  async insertHint(_h: Hint): Promise<void> {
    this.serverOnly();
  }

  // --- test_item / blueprint ---
  listReviewedTestItems(subject: string): Promise<TestItem[]> {
    return this.call("listReviewedTestItems", [subject]);
  }
  async insertTestItem(_item: TestItem): Promise<void> {
    this.serverOnly();
  }
  getTestBlueprint(id: string): Promise<TestBlueprint | null> {
    return this.call("getTestBlueprint", [id]);
  }
  async insertTestBlueprint(_bp: TestBlueprint): Promise<void> {
    this.serverOnly();
  }

  // --- quiz_session ---
  insertSession(s: QuizSession): Promise<void> {
    return this.call("insertSession", [s]);
  }
  getSession(id: string): Promise<QuizSession | null> {
    return this.call("getSession", [id]);
  }
  patchSessionClose(
    id: string,
    patch: SessionClosePatch,
  ): Promise<QuizSession | null> {
    return this.call("patchSessionClose", [id, patch]);
  }
  listClosedSessionsByLearner(
    subject: string,
    learnerId: string,
    options?: { sinceISO?: string },
  ): Promise<QuizSession[]> {
    return this.call("listClosedSessionsByLearner", [subject, learnerId, options]);
  }
  setSessionCurrentQuestion(
    sessionId: string,
    questionId: string | null,
  ): Promise<void> {
    return this.call("setSessionCurrentQuestion", [sessionId, questionId]);
  }
  getNewestOpenSession(
    subject: string,
    learnerId: string,
  ): Promise<QuizSession | null> {
    return this.call("getNewestOpenSession", [subject, learnerId]);
  }

  // --- attempt ---
  insertAttempt(a: Attempt): Promise<InsertAttemptResult> {
    return this.call("insertAttempt", [a]);
  }
  listMisses(subject: string, learnerId: string): Promise<Attempt[]> {
    return this.call("listMisses", [subject, learnerId]);
  }
  async listAlreadyCorrectQuestionIds(
    _subject: string,
    _learnerId: string,
  ): Promise<string[]> {
    // FR-E4: server-only — eligibility is applied in GET /api/engine/next.
    this.serverOnly();
  }
  listSessionQuestionIds(sessionId: string): Promise<string[]> {
    return this.call("listSessionQuestionIds", [sessionId]);
  }
  listSessionAttempts(sessionId: string): Promise<Attempt[]> {
    return this.call("listSessionAttempts", [sessionId]);
  }
  listSessionSkillIds(sessionId: string): Promise<string[]> {
    return this.call("listSessionSkillIds", [sessionId]);
  }
  accuracyRowsBySkill(
    subject: string,
    learnerId: string,
    skillId: string,
    sessions: number,
  ): Promise<SkillAccuracyRow[]> {
    return this.call("accuracyRowsBySkill", [
      subject,
      learnerId,
      skillId,
      sessions,
    ]);
  }

  // --- skill_state ---
  listSkillState(subject: string, learnerId: string): Promise<SkillState[]> {
    return this.call("listSkillState", [subject, learnerId]);
  }
  getSkillState(
    subject: string,
    skillId: string,
    learnerId: string,
  ): Promise<SkillState | null> {
    return this.call("getSkillState", [subject, skillId, learnerId]);
  }
  upsertSkillState(state: SkillState): Promise<void> {
    return this.call("upsertSkillState", [state]);
  }

  // --- content / tutorial / progress ---
  getContentString(
    subject: string,
    key: string,
    locale: string,
  ): Promise<string | null> {
    return this.call("getContentString", [subject, key, locale]);
  }
  listContentStrings(
    subject: string,
    locale: string,
  ): Promise<Array<{ key: string; value: string }>> {
    return this.call("listContentStrings", [subject, locale]);
  }
  getTutorial(subject: string, skillId: string): Promise<Tutorial | null> {
    return this.call("getTutorial", [subject, skillId]);
  }
  listProgressPoints(
    subject: string,
    learnerId: string,
  ): Promise<ProgressPoint[]> {
    return this.call("listProgressPoints", [subject, learnerId]);
  }
}
