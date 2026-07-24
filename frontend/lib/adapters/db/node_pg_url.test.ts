/**
 * node_pg_url.test.ts — pure URL normalization for Node pg (T R.2) + pool budget (T R.13).
 */
import { describe, expect, it } from "vitest";
import { pgPoolMax, toNodePgConnectionString } from "./node_pg_url";

describe("toNodePgConnectionString", () => {
  it("strips +asyncpg dialect marker", () => {
    expect(
      toNodePgConnectionString(
        "postgresql+asyncpg://agent:pw@/agent?host=/cloudsql/proj:region:inst",
      ),
    ).toBe("postgresql://agent:pw@/agent?host=/cloudsql/proj:region:inst");
  });

  it("strips +psycopg and leaves host/query intact", () => {
    expect(
      toNodePgConnectionString(
        "postgresql+psycopg://u:p@localhost:5432/db?sslmode=require",
      ),
    ).toBe("postgresql://u:p@localhost:5432/db?sslmode=require");
  });

  it("is a no-op for plain postgresql:// and postgres://", () => {
    const a = "postgresql://u:p@localhost:5432/db";
    const b = "postgres://u:p@/db?host=/cloudsql/p:r:i";
    expect(toNodePgConnectionString(a)).toBe(a);
    expect(toNodePgConnectionString(b)).toBe(b);
  });
});

describe("pgPoolMax (T R.13 — Cloud SQL connection budget)", () => {
  it("returns the env override when set and within bounds", () => {
    expect(pgPoolMax({ ENGINE_PG_POOL_MAX: "3" }, 5)).toBe(3);
    expect(pgPoolMax({ ENGINE_PG_POOL_MAX: "12" }, 5)).toBe(12);
  });

  it("falls back to the bounded default when unset / unparseable", () => {
    expect(pgPoolMax({}, 5)).toBe(5);
    expect(pgPoolMax({ ENGINE_PG_POOL_MAX: "not-a-number" }, 5)).toBe(5);
  });

  it("clamps to a sane ceiling so a misconfigured knob can never exhaust max_connections", () => {
    // Cloud SQL max_connections=50; three frontend pools share it, so a single
    // pool must never claim the whole budget. Clamp to [1, 20].
    expect(pgPoolMax({ ENGINE_PG_POOL_MAX: "0" }, 5)).toBe(1);
    expect(pgPoolMax({ ENGINE_PG_POOL_MAX: "-5" }, 5)).toBe(1);
    expect(pgPoolMax({ ENGINE_PG_POOL_MAX: "1000" }, 5)).toBe(20);
  });
});
