/**
 * Normalize a Postgres URL for the Node `pg` driver (T R.2 / FR-F1).
 *
 * The shared `database-url` secret is historically documented as
 * `postgresql+asyncpg://…` (SQLAlchemy dialect). Node `pg` rejects that
 * scheme. Strip any `+<dialect>` marker so the same secret works for both
 * the Python checkpointer and the frontend BFF / migrate_engine.mjs.
 *
 * Pure — no I/O. Keep the regex in sync with `frontend/scripts/migrate_engine.mjs`.
 */
export function toNodePgConnectionString(url: string): string {
  return url.replace(/^postgres(ql)?\+[A-Za-z0-9_]+:\/\//i, "postgres$1://");
}

/**
 * Bounded `pg.Pool` `max` from the env (T R.13 — Cloud SQL connection budget).
 *
 * Cloud SQL `max_connections=50` is shared across the frontend's three `pg`
 * pools (engine + threads + coach-marker) plus the on-demand migrate/probe
 * clients. An uncapped pool defaults to 10; three of those (30) plus probes
 * sit too close to 50 under concurrency. This knob caps each pool to a
 * bounded value so the per-service sum stays under the budget.
 *
 * Reads `ENGINE_PG_POOL_MAX` (int), falls back to `defaultMax`, and clamps to
 * `[1, 20]` so a misconfigured knob can never claim the whole budget. Pure —
 * no I/O; takes the env explicitly so tests inject a scripted value.
 */
const PG_POOL_MAX_CEILING = 20;
const PG_POOL_MAX_FLOOR = 1;

export function pgPoolMax(
  env: NodeJS.ProcessEnv | Record<string, string | undefined>,
  defaultMax: number,
): number {
  const raw = env.ENGINE_PG_POOL_MAX;
  const parsed = raw == null || raw === "" ? defaultMax : Number(raw);
  if (!Number.isInteger(parsed)) return defaultMax;
  return Math.min(PG_POOL_MAX_CEILING, Math.max(PG_POOL_MAX_FLOOR, parsed));
}
