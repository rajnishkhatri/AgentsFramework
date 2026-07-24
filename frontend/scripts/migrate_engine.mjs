#!/usr/bin/env node
/**
 * migrate_engine.mjs — plain SQL runner for the durable frontend engine (FR-F2/F3).
 *
 * Applies `frontend/drizzle/0*.sql` in lexicographic order, one transaction per
 * file, ledgered in `_frontend_migrations` (filename + applied_at; skip
 * already-applied). Then applies `seed_*.sql` **every run** (idempotent
 * DO UPDATE reconciliation — ledgering the seed would skip a re-emit and
 * reintroduce FR-G2 drift).
 *
 * Usage:
 *   DATABASE_URL=postgres://... node frontend/scripts/migrate_engine.mjs
 *
 * Pre-traffic deploy step only — never at Cloud Run boot (cold starts must
 * not race a migration). Uses the `pg` package already in frontend deps;
 * no drizzle-kit.
 *
 * T R.9: `runMigrate({ databaseUrl, drizzleDir })` is exported for scratch-pg
 * integration tests (replay + mid-file rollback). Optional `ENGINE_DRIZZLE_DIR`
 * overrides the drizzle folder for the CLI.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_DRIZZLE_DIR = path.resolve(__dirname, "../drizzle");

function die(msg) {
  console.error(`migrate_engine: ${msg}`);
  process.exit(1);
}

function listSql(drizzleDir, prefix) {
  if (!fs.existsSync(drizzleDir)) {
    throw new Error(`drizzle dir missing: ${drizzleDir}`);
  }
  return fs
    .readdirSync(drizzleDir)
    .filter((name) => name.startsWith(prefix) && name.endsWith(".sql"))
    .sort()
    .map((name) => ({
      name,
      full: path.join(drizzleDir, name),
      sql: fs.readFileSync(path.join(drizzleDir, name), "utf8"),
    }));
}

async function ensureLedger(client) {
  await client.query(`
    CREATE TABLE IF NOT EXISTS "_frontend_migrations" (
      "filename" text PRIMARY KEY NOT NULL,
      "applied_at" timestamptz NOT NULL DEFAULT now()
    );
  `);
}

async function alreadyApplied(client, filename) {
  const res = await client.query(
    `SELECT 1 FROM "_frontend_migrations" WHERE "filename" = $1 LIMIT 1`,
    [filename],
  );
  return res.rowCount > 0;
}

async function applyNumbered(client, file) {
  if (await alreadyApplied(client, file.name)) {
    console.log(`skip (ledger) ${file.name}`);
    return { applied: false, name: file.name };
  }
  console.log(`apply ${file.name}`);
  try {
    await client.query("BEGIN");
    await client.query(file.sql);
    await client.query(
      `INSERT INTO "_frontend_migrations" ("filename") VALUES ($1)`,
      [file.name],
    );
    await client.query("COMMIT");
  } catch (err) {
    try {
      await client.query("ROLLBACK");
    } catch {
      /* ignore rollback errors */
    }
    throw new Error(`${file.name} failed (rolled back): ${err.message}`);
  }
  return { applied: true, name: file.name };
}

async function applySeed(client, file) {
  console.log(`seed (always) ${file.name}`);
  try {
    await client.query("BEGIN");
    await client.query(file.sql);
    await client.query("COMMIT");
  } catch (err) {
    try {
      await client.query("ROLLBACK");
    } catch {
      /* ignore */
    }
    throw new Error(`${file.name} failed (rolled back): ${err.message}`);
  }
  return { applied: true, name: file.name };
}

/**
 * @param {{ databaseUrl: string, drizzleDir?: string }} opts
 * @returns {Promise<{
 *   ok: true,
 *   drizzle_dir: string,
 *   applied: string[],
 *   skipped: string[],
 *   numbered_total: number,
 *   seed_total: number,
 * }>}
 */
export async function runMigrate(opts) {
  const rawUrl = opts?.databaseUrl;
  if (!rawUrl || !String(rawUrl).trim()) {
    throw new Error("DATABASE_URL is required");
  }
  // Keep in sync with frontend/lib/adapters/db/node_pg_url.ts (T R.2).
  const url = String(rawUrl).replace(
    /^postgres(ql)?\+[A-Za-z0-9_]+:\/\//i,
    "postgres$1://",
  );

  const drizzleDir =
    opts.drizzleDir?.trim() ||
    process.env.ENGINE_DRIZZLE_DIR?.trim() ||
    DEFAULT_DRIZZLE_DIR;

  const numbered = listSql(drizzleDir, "0");
  const seeds = listSql(drizzleDir, "seed_");
  if (numbered.length === 0) {
    throw new Error(`no numbered migrations (0*.sql) under ${drizzleDir}`);
  }

  const client = new pg.Client({ connectionString: url });
  await client.connect();
  try {
    await ensureLedger(client);
    const results = [];
    for (const file of numbered) {
      results.push(await applyNumbered(client, file));
    }
    for (const file of seeds) {
      results.push(await applySeed(client, file));
    }
    const applied = results.filter((r) => r.applied).map((r) => r.name);
    const skipped = results.filter((r) => !r.applied).map((r) => r.name);
    return {
      ok: true,
      drizzle_dir: drizzleDir,
      applied,
      skipped,
      numbered_total: numbered.length,
      seed_total: seeds.length,
    };
  } finally {
    await client.end();
  }
}

async function main() {
  const rawUrl = process.env.DATABASE_URL;
  if (!rawUrl || !rawUrl.trim()) {
    die("DATABASE_URL is required");
  }
  try {
    const summary = await runMigrate({
      databaseUrl: rawUrl,
      drizzleDir: process.env.ENGINE_DRIZZLE_DIR || DEFAULT_DRIZZLE_DIR,
    });
    console.log(JSON.stringify(summary));
  } catch (err) {
    die(err?.message || String(err));
  }
}

const isMain =
  process.argv[1] != null &&
  path.resolve(fileURLToPath(import.meta.url)) === path.resolve(process.argv[1]);

if (isMain) {
  main().catch((err) => die(err?.stack || String(err)));
}
