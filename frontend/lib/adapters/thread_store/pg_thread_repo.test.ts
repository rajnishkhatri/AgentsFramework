/**
 * L2 tests for the `pg`-backed thread-store SDK seam (option B — Cloud SQL).
 *
 * Two units under test, both in `pg_thread_repo.ts`:
 *   1. `classifyDsn(url)` — a PURE DSN discriminator (L1-deterministic): which
 *      driver a connection string wants. Mirrors `deploy_piece_c.sh`'s
 *      `case "$DATABASE_URL" in *"/cloudsql/"*` substring test so the deploy
 *      script and the BFF agree on what "is a Cloud SQL DSN" means.
 *   2. `pgDrizzleDb(url)` — the SDK seam that adapts a `pg.Pool` to the narrow
 *      `DrizzleLike` port. It is the ONLY new code that imports the `pg` /
 *      `drizzle-orm/node-postgres` vendor packages.
 *
 * Per the TDD-Agentic-Systems prompt:
 *   - Protocol B (Horizontal / contract-driven): mock the `pg` boundary, never
 *     a live DB; assert the `DrizzleLike` contract, not the query builder.
 *   - Pattern 6 (Mock Provider): a hand-rolled fake `pg.Pool` whose `query()` is
 *     scripted per test — this tests the seam's adaptation logic, not pg itself.
 *   - Failure paths first (Anti-Pattern 6 / Check 4): the driver-rejection →
 *     `ThreadStoreError` translation (A5) is asserted before the happy paths.
 *   - Behavior over implementation (Anti-Pattern 1): `classifyDsn` is asserted
 *     against externally-known DSN shapes, never by re-deriving its branching.
 *
 * The repo-level behavior (NeonThreadRepo over a DrizzleLike: pagination,
 * soft-delete, ownership) is ALREADY covered by `neon_thread_repo.test.ts` and
 * is driver-agnostic — it is intentionally NOT re-tested here. This file's job
 * is narrow: the pg→DrizzleLike adaptation + the DSN classifier.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { classifyDsn, pgDrizzleDb, type PgQueryClient } from "./pg_thread_repo";
import * as pgSeam from "./pg_thread_repo";
import { NeonThreadRepo, selectThreadRepo } from "./neon_thread_repo";
import { InMemoryThreadRepo, ThreadStoreError } from "./neon_free_thread_store";

/**
 * A logical `threads` row, before conversion to the wire shape pg returns.
 */
interface LogicalRow {
  thread_id: string;
  user_id: string;
  title: string;
  messages: unknown;
  metadata: unknown;
  created_at: Date;
  updated_at: Date;
  archived_at: Date | null;
}

/**
 * drizzle's node-postgres driver issues queries with `rowMode: "array"`, so the
 * `pg` client must return each row as a POSITIONAL ARRAY of column values in the
 * SELECT order — NOT an object. That column order, for `db.select().from(threads)`
 * and the `.returning()` on update, is the table's declaration order in
 * `db/schema.ts`. Encoding that order here is the contract this seam test pins:
 * if the schema column order changes, this fixture (and the seam's `toRow`) must
 * agree. (Discovered by probing the real driver, not assumed.)
 */
const SELECT_COLUMN_ORDER = [
  "thread_id",
  "user_id",
  "title",
  "messages",
  "metadata",
  "created_at",
  "updated_at",
  "archived_at",
] as const;

function toPgArrayRow(r: LogicalRow): unknown[] {
  return SELECT_COLUMN_ORDER.map((col) => r[col as keyof LogicalRow]);
}

/**
 * Scripted fake at the `pg` boundary (Pattern 6 — Mock Provider). drizzle's
 * node-postgres driver calls `client.query(config, params) => { rows }` with
 * `rowMode: "array"`; this fake answers from a per-call queue or throws. We let
 * the REAL drizzle build the SQL (no mock of drizzle internals — that would be
 * tautological), and only control what the database returns.
 */
function makePgClient(): {
  client: PgQueryClient;
  enqueueRows: (rows: LogicalRow[]) => void;
  rejectNext: (err: Error) => void;
  calls: Array<{ text: unknown; params: unknown }>;
} {
  const queue: Array<{ kind: "rows"; rows: unknown[] } | { kind: "err"; err: Error }> = [];
  const calls: Array<{ text: unknown; params: unknown }> = [];
  const client: PgQueryClient = {
    query: vi.fn(async (text: unknown, params?: unknown) => {
      calls.push({ text, params });
      const next = queue.shift();
      if (!next) return { rows: [] };
      if (next.kind === "err") throw next.err;
      return { rows: next.rows };
    }),
  };
  return {
    client,
    enqueueRows: (rows) => queue.push({ kind: "rows", rows: rows.map(toPgArrayRow) }),
    rejectNext: (err) => queue.push({ kind: "err", err }),
    calls,
  };
}

const ROW: LogicalRow = {
  thread_id: "t1",
  user_id: "user_abc",
  title: "Trip planning",
  messages: [{ role: "user", content: "hi" }],
  metadata: { source: "test" },
  created_at: new Date("2026-06-18T10:00:00Z"),
  updated_at: new Date("2026-06-18T10:05:00Z"),
  archived_at: null,
};

describe("classifyDsn [Protocol B / pure]", () => {
  // Cloud SQL: the prod `database-url` secret is a unix-socket DSN. The marker
  // is the literal `/cloudsql/` substring (matching deploy_piece_c.sh).
  it.each([
    "postgresql://agent:pw@/agent?host=/cloudsql/agent-prod-gcp-dev:us-central1:agent-db",
    "postgres://u:p@/db?host=/cloudsql/proj:region:inst&sslmode=disable",
    "postgresql:///agent?host=/cloudsql/proj:region:inst",
  ])("maps a /cloudsql/ socket DSN to 'cloudsql': %s", (url) => {
    expect(classifyDsn(url)).toBe("cloudsql");
  });

  // Neon: the abandoned dev-tier stack used Neon HTTP/WS over a *.neon.tech host.
  it.each([
    "postgresql://u:p@ep-cool-darkness-123456.us-east-2.aws.neon.tech/db?sslmode=require",
    "postgres://user:pass@my-project.neon.tech/main",
  ])("maps a .neon.tech host to 'neon': %s", (url) => {
    expect(classifyDsn(url)).toBe("neon");
  });

  // Ambiguous / generic TCP Postgres → 'tcp'. pg is the safe general driver, so
  // the selector routes both 'cloudsql' and 'tcp' to pgDrizzleDb; only explicit
  // .neon.tech hosts get the Neon HTTP driver.
  it.each([
    "postgresql://u:p@localhost:5432/agent",
    "postgres://u:p@10.0.0.5:5432/db?sslmode=require",
    "postgresql://u:p@db.internal:5432/threads",
  ])("maps a bare TCP host to 'tcp': %s", (url) => {
    expect(classifyDsn(url)).toBe("tcp");
  });

  it("treats /cloudsql/ as higher-precedence than a neon-looking query value", () => {
    // A socket DSN whose params happen to mention neon must still route to pg.
    const url =
      "postgresql://u:p@/agent?host=/cloudsql/proj:region:inst&application_name=neon-compat";
    expect(classifyDsn(url)).toBe("cloudsql");
  });
});

describe("pgDrizzleDb seam [Protocol B / contract-driven]", () => {
  const DSN = "postgresql://u:p@/agent?host=/cloudsql/proj:region:inst";

  // ── Failure paths first (Anti-Pattern 6 / Check 4) ───────────────────────

  it("rejects an empty DSN with no injected client (A5, guards the seam)", () => {
    expect(() => pgDrizzleDb("")).toThrow(ThreadStoreError);
  });

  it("a driver rejection surfaces as ThreadStoreError, not a raw pg error (A5)", async () => {
    // The NeonThreadRepo wrapper owns A5 translation; the pg seam must let the
    // rejection propagate so the wrapper can translate it. This proves no raw
    // vendor error escapes the adapter boundary (F-R8).
    const { client, rejectNext } = makePgClient();
    rejectNext(new Error("ECONNREFUSED /cloudsql/proj:region:inst"));
    const repo = new NeonThreadRepo(pgDrizzleDb(DSN, client));
    await expect(repo.findOne("t1")).rejects.toBeInstanceOf(ThreadStoreError);
  });

  it("a rejection on insert is translated, never swallowed", async () => {
    const { client, rejectNext } = makePgClient();
    rejectNext(new Error("unique_violation"));
    const repo = new NeonThreadRepo(pgDrizzleDb(DSN, client));
    await expect(
      repo.insert({
        thread_id: "t1",
        user_id: "user_abc",
        title: "x",
        messages: [],
        metadata: {},
        created_at: "2026-06-18T10:00:00Z",
        updated_at: "2026-06-18T10:00:00Z",
        archived_at: null,
      }),
    ).rejects.toBeInstanceOf(ThreadStoreError);
  });

  // ── Happy-path adaptation: pg rows → DrizzleLike → ThreadRow ──────────────

  it("findThread maps a pg row to the vendor-free ThreadRow shape", async () => {
    const { client, enqueueRows } = makePgClient();
    const seam = pgDrizzleDb(DSN, client);
    enqueueRows([ROW]); // drizzle issues one SELECT
    const row = await seam.findThread("t1");
    expect(row).not.toBeNull();
    expect(row!.thread_id).toBe("t1");
    expect(row!.user_id).toBe("user_abc");
    expect(row!.title).toBe("Trip planning");
    expect(row!.messages).toEqual([{ role: "user", content: "hi" }]);
    expect(row!.metadata).toEqual({ source: "test" });
    // timestamptz columns are normalised to ISO strings (no Date escapes the seam).
    expect(typeof row!.created_at).toBe("string");
    expect(row!.created_at).toBe("2026-06-18T10:00:00.000Z");
    expect(row!.archived_at).toBeNull();
  });

  it("findThread returns null when pg yields no rows", async () => {
    const { client, enqueueRows } = makePgClient();
    const seam = pgDrizzleDb(DSN, client);
    enqueueRows([]);
    expect(await seam.findThread("missing")).toBeNull();
  });

  it("listThreads maps every row and scopes the query (WHERE user_id, not archived)", async () => {
    const { client, enqueueRows, calls } = makePgClient();
    const seam = pgDrizzleDb(DSN, client);
    const rowB: LogicalRow = {
      ...ROW,
      thread_id: "t2",
      created_at: new Date("2026-06-18T09:00:00Z"),
    };
    enqueueRows([ROW, rowB]); // no cursor → single SELECT returns both rows
    const rows = await seam.listThreads({ ownerSub: "user_abc", cursor: null, limit: 20 });
    expect(rows.map((r) => r.thread_id)).toEqual(["t1", "t2"]);
    // The SQL drizzle built must scope by user_id and exclude archived rows —
    // assert the query text reflects that without re-deriving the full string.
    const cfg = calls[0]?.text as { text?: string } | string | undefined;
    const sql = (typeof cfg === "string" ? cfg : (cfg?.text ?? "")).toLowerCase();
    expect(sql).toContain("where");
    expect(sql).toContain('"user_id"');
    expect(sql).toContain('"archived_at"');
  });

  it("updateThread returns the updated row mapped to ThreadRow", async () => {
    const { client, enqueueRows } = makePgClient();
    const seam = pgDrizzleDb(DSN, client);
    enqueueRows([{ ...ROW, title: "Renamed" }]);
    const row = await seam.updateThread("t1", { title: "Renamed" });
    expect(row!.title).toBe("Renamed");
  });

  it("updateThread returns null when the row vanished (concurrent delete)", async () => {
    const { client, enqueueRows } = makePgClient();
    const seam = pgDrizzleDb(DSN, client);
    enqueueRows([]);
    expect(await seam.updateThread("t1", { title: "x" })).toBeNull();
  });

  it("accepts an injected client without a DSN (test-injection seam)", () => {
    const { client } = makePgClient();
    expect(() => pgDrizzleDb("", client)).not.toThrow();
  });
});

/**
 * `selectThreadRepo` is the composition-seam DSN router (lives in
 * neon_thread_repo.ts; called from bff/server_composition.ts). Option B adds the
 * pg branch. We spy on the two SDK seams to assert WHICH driver each DSN class
 * routes to — `instanceof NeonThreadRepo` cannot distinguish them (both seams
 * yield a NeonThreadRepo over a DrizzleLike), so the routing is the thing to
 * pin. The spies also keep the test offline: neither real seam opens a socket.
 */
describe("selectThreadRepo DSN routing [composition seam / Pattern 7-adjacent]", () => {
  afterEach(() => vi.restoreAllMocks());

  it("routes a /cloudsql/ socket DSN to the pg seam, never the Neon driver", () => {
    const pgSpy = vi.spyOn(pgSeam, "pgDrizzleDb").mockReturnValue({} as never);
    const dsn =
      "postgresql://agent:pw@/agent?host=/cloudsql/agent-prod-gcp-dev:us-central1:agent-db";
    const repo = selectThreadRepo({ DATABASE_URL: dsn });
    expect(repo).toBeInstanceOf(NeonThreadRepo);
    expect(pgSpy).toHaveBeenCalledWith(dsn);
  });

  it("routes a .neon.tech URL to the Neon HTTP seam (not pg)", () => {
    // `neonDrizzleDb` is a same-module call inside selectThreadRepo, so an
    // external spy can't intercept it under ESM. We prove the neon path the
    // sound way: the pg seam was NOT taken and a real NeonThreadRepo was built
    // (the neon seam is lazy — no socket opens at selection time).
    const pgSpy = vi.spyOn(pgSeam, "pgDrizzleDb").mockReturnValue({} as never);
    const dsn = "postgresql://u:p@ep-test.us-east-2.aws.neon.tech/db?sslmode=require";
    const repo = selectThreadRepo({ DATABASE_URL: dsn });
    expect(repo).toBeInstanceOf(NeonThreadRepo);
    expect(pgSpy).not.toHaveBeenCalled();
  });

  it("routes a generic TCP Postgres DSN to the pg seam (safe default)", () => {
    const pgSpy = vi.spyOn(pgSeam, "pgDrizzleDb").mockReturnValue({} as never);
    const dsn = "postgresql://u:p@10.0.0.5:5432/threads?sslmode=require";
    selectThreadRepo({ DATABASE_URL: dsn });
    expect(pgSpy).toHaveBeenCalledWith(dsn);
  });

  it("falls back to in-memory when DATABASE_URL is unset/blank (no seam touched)", () => {
    const pgSpy = vi.spyOn(pgSeam, "pgDrizzleDb");
    for (const env of [{}, { DATABASE_URL: "" }, { DATABASE_URL: "   " }]) {
      expect(selectThreadRepo(env)).toBeInstanceOf(InMemoryThreadRepo);
    }
    expect(pgSpy).not.toHaveBeenCalled();
  });
});
