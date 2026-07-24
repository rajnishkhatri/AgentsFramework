/**
 * coach_session_marker adapters (ADR-0012 Amendment).
 *
 * Implements `CoachSessionMarkerRepo` (P1). Two members:
 *
 *   - `InMemoryCoachMarkerRepo` — dev/shadow default. Backed by a
 *     `globalThis`-stashed map so the marker-WRITE route and the coach
 *     stream (READ) route share one store even though Next dev compiles
 *     each route into its own module-registry copy (the thread-repo
 *     per-route-bundle lesson).
 *   - `PgCoachMarkerRepo` — durable table via `pg` + drizzle-orm
 *     (node-postgres). Lazy pool: no connection until the first query.
 *
 * `selectCoachMarkerRepo(env)` mirrors `selectThreadRepo`: DATABASE_URL ⇒
 * pg-backed, else in-memory. Called ONLY from the server composition seam.
 *
 * Monotonic contract: INSERT … ON CONFLICT DO NOTHING is the sole write —
 * no update/delete statement exists in this module.
 *
 * SDK pin (A9): pg ^8, drizzle-orm ^0.45 (package.json), confined to
 * `lib/adapters/**` (F-R2). Error posture (A5): `markSubmitted` failures
 * are the fire-and-forget path — the caller logs and continues (a missed
 * marker fails CLOSED to pre_submit); `isSubmitted` failures also return
 * `false` (fail-closed) rather than throw, so a DB blip can never leak
 * answer fields.
 */

import { drizzle } from "drizzle-orm/node-postgres";
import { sql } from "drizzle-orm";
import { Pool } from "pg";
import { pgPoolMax, toNodePgConnectionString } from "@/lib/adapters/db/node_pg_url";
import type { CoachSessionMarkerRepo } from "@/lib/ports/coach_session_marker_repo";
import { coach_session_marker } from "./db/schema";

// ── in-memory (dev/shadow) ──────────────────────────────────────────────

// NUL separator, written as the \u0000 ESCAPE -- a literal NUL byte makes
// this file binary to git (unreviewable diffs). No printable id contains
// NUL, so the key can never collide across (userId, questionId) pairs.
type MarkerKey = `${string}\u0000${string}`;

function markerKey(userId: string, questionId: string): MarkerKey {
  return `${userId}\u0000${questionId}`;
}

const GLOBAL_KEY = "__coach_session_markers__";

function globalStore(): Set<MarkerKey> {
  const bag = globalThis as Record<string, unknown>;
  if (!(bag[GLOBAL_KEY] instanceof Set)) {
    bag[GLOBAL_KEY] = new Set<MarkerKey>();
  }
  return bag[GLOBAL_KEY] as Set<MarkerKey>;
}

export class InMemoryCoachMarkerRepo implements CoachSessionMarkerRepo {
  async markSubmitted(userId: string, questionId: string): Promise<void> {
    globalStore().add(markerKey(userId, questionId));
  }

  async isSubmitted(userId: string, questionId: string): Promise<boolean> {
    return globalStore().has(markerKey(userId, questionId));
  }
}

/** Test-only seam: clears the globalThis-backed store between tests. */
export function _resetInMemoryCoachMarkers(): void {
  (globalThis as Record<string, unknown>)[GLOBAL_KEY] = new Set<MarkerKey>();
}

// ── pg-backed (durable) ─────────────────────────────────────────────────

export class PgCoachMarkerRepo implements CoachSessionMarkerRepo {
  private _db: ReturnType<typeof drizzle> | null = null;

  constructor(private readonly connectionString: string) {}

  private db() {
    if (!this._db) {
      this._db = drizzle(
        new Pool({
          connectionString: toNodePgConnectionString(this.connectionString),
          // T R.13 — bounded pool (shared Cloud SQL budget). Default 5.
          max: pgPoolMax(process.env, 5),
        }),
      );
    }
    return this._db;
  }

  async markSubmitted(userId: string, questionId: string): Promise<void> {
    await this.db()
      .insert(coach_session_marker)
      .values({ user_id: userId, question_id: questionId })
      .onConflictDoNothing();
  }

  async isSubmitted(userId: string, questionId: string): Promise<boolean> {
    try {
      const rows = await this.db()
        .select({ one: sql`1` })
        .from(coach_session_marker)
        .where(
          sql`${coach_session_marker.user_id} = ${userId} AND ${coach_session_marker.question_id} = ${questionId}`,
        )
        .limit(1);
      return rows.length > 0;
    } catch {
      // Fail CLOSED: an unreadable store derives pre_submit (fields
      // stripped) — a DB blip must never leak answer fields.
      return false;
    }
  }
}

// ── composition seam ────────────────────────────────────────────────────

export function selectCoachMarkerRepo(
  env: Readonly<Record<string, string | undefined>>,
): CoachSessionMarkerRepo {
  const url = env.DATABASE_URL;
  if (url && url.trim()) {
    return new PgCoachMarkerRepo(url);
  }
  return new InMemoryCoachMarkerRepo();
}
