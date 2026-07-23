/**
 * Coarse EngineClient loaders (coach-v3 FR-A6 / T A.11).
 *
 * Each method is ONE fetch to a coarse `/api/engine/*` endpoint. Heavy read
 * hooks call these under the durable_engine flag so the atomic HttpEngineDb
 * swap does not regress N-repo fan-out into N network round-trips.
 */

import { EnvVarFlagsAdapter } from "../feature_flags/env_var_flags_adapter";
import { EngineRepoError } from "../../ports/engine/errors";
import type {
  Attempt,
  Hint,
  Question,
  QuizSession,
  Skill,
  SkillAccuracyRow,
  SkillState,
  Tutorial,
} from "../../wire/engine_entities";

export function durableEngineEnabled(
  env: Readonly<Record<string, string | undefined>> = process.env as Record<
    string,
    string | undefined
  >,
): boolean {
  return new EnvVarFlagsAdapter({ env }).isEnabled("durable_engine");
}

export interface EngineClientOptions {
  readonly baseUrl?: string;
  readonly fetchImpl?: typeof fetch;
}

export type DashboardPayload = {
  skills: Skill[];
  skill_states: SkillState[];
  misses: Attempt[];
  sessions: QuizSession[];
  focus_skill_id: string | null;
  focus_question: Question | null;
  review_misses_count: number;
};

export type SummaryPayload = {
  session: QuizSession;
  skills: Skill[];
  skill_states: SkillState[];
  misses: Attempt[];
  served_question_ids: string[];
  attempts: Attempt[];
  /** Served + miss question bodies (folded server-side; one BFF call). */
  miss_questions: Question[];
  questions?: Question[];
};

export type SkillDetailPayload = {
  skill: Skill | null;
  skills: Skill[];
  tutorial: Tutorial | null;
  skill_states: SkillState[];
  misses: Attempt[];
  accuracy_rows: SkillAccuracyRow[];
  miss_questions: Question[];
};

export type NextItemPayload = {
  empty: boolean;
  reason?: string;
  question: Question | null;
  hints: Hint[];
  skill_id: string | null;
};

export class EngineClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: EngineClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? "").replace(/\/$/, "");
    this.fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  private async getJson<T>(path: string): Promise<T> {
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}${path}`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
      });
    } catch (e) {
      throw new EngineRepoError(
        `engine client failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
    if (!res.ok) {
      throw new EngineRepoError(`engine client failed (${res.status})`);
    }
    return (await res.json()) as T;
  }

  private async postJson<T>(path: string, body: unknown): Promise<T> {
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}${path}`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (e) {
      throw new EngineRepoError(
        `engine client failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
    if (!res.ok) {
      throw new EngineRepoError(`engine client failed (${res.status})`);
    }
    return (await res.json()) as T;
  }

  loadDashboard(args: {
    subject: string;
    sinceISO?: string;
    nowISO?: string;
  }): Promise<DashboardPayload> {
    const q = new URLSearchParams({ subject: args.subject });
    if (args.sinceISO) q.set("since", args.sinceISO);
    if (args.nowISO) q.set("now", args.nowISO);
    return this.getJson(`/api/engine/dashboard?${q}`);
  }

  loadSummary(sessionId: string): Promise<SummaryPayload> {
    const q = new URLSearchParams({ session: sessionId });
    return this.getJson(`/api/engine/summary?${q}`);
  }

  loadSkillDetail(args: {
    subject: string;
    skillId: string;
    sessions?: number;
  }): Promise<SkillDetailPayload> {
    const q = new URLSearchParams({ subject: args.subject });
    if (args.sessions != null) q.set("sessions", String(args.sessions));
    return this.getJson(`/api/engine/skill/${encodeURIComponent(args.skillId)}?${q}`);
  }

  nextItem(sessionId: string): Promise<NextItemPayload> {
    const q = new URLSearchParams({ session: sessionId });
    return this.getJson(`/api/engine/next?${q}`);
  }

  /** FR-C1: server computes the authoritative commit-first tally. */
  closeSession(sessionId: string): Promise<QuizSession> {
    return this.postJson("/api/engine/session/close", {
      session_id: sessionId,
    });
  }
}

let _client: EngineClient | null = null;

/** Browser singleton used by heavy hooks under the durable flag. */
export function browserEngineClient(): EngineClient {
  if (_client) return _client;
  _client = new EngineClient({ baseUrl: "" });
  return _client;
}

/** Test-only. */
export function _resetBrowserEngineClient(): void {
  _client = null;
}
