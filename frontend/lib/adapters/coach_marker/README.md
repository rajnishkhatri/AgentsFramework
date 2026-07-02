# adapters/coach_marker — coach-session marker store (ADR-0012 Amendment)

**Port:** `frontend/lib/ports/coach_session_marker_repo.ts` (`CoachSessionMarkerRepo`)

The mode-derivation source of truth for the coach context contract (agent
spec FR-19/FR-21): `{user_id, question_id, submitted_at}` markers, written
fire-and-forget from the quiz submit path, read by the coach BFF stream
route. Monotonic — no unmark/delete method exists.

## Implementations

| Adapter | When | Notes |
|---|---|---|
| `InMemoryCoachMarkerRepo` | no `DATABASE_URL` (dev/shadow) | `globalThis`-backed so the write route and the coach stream route share one store across Next-dev route bundles |
| `PgCoachMarkerRepo` | `DATABASE_URL` set | `pg` + drizzle (node-postgres); insert-only (`ON CONFLICT DO NOTHING`); reads fail CLOSED to `false` (pre-submit) |

**Swap trigger:** durable markers required (multi-instance BFF, or sessions
that must survive a dev-server restart) ⇒ set `DATABASE_URL`; the table is
whitelisted in `drizzle.config.ts` (IR-NEON-5).

**Selection:** `selectCoachMarkerRepo(env)` — called only from
`lib/bff/server_composition.ts` (C1).
