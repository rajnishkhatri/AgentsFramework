/**
 * Shared scratch Postgres for T R.9 migrate / insertAttempt integration tests.
 *
 * Managed Docker on a dedicated port (not the persistence-probe container).
 * Bring-your-own: set DATABASE_URL and skip managed lifecycle.
 */

import { spawnSync } from "node:child_process";

export type ScratchOpts = {
  container?: string;
  port?: string;
  dbName?: string;
};

const DEFAULTS = {
  container: "engine-r9-pg",
  port: "55433",
  dbName: "engine_r9",
};

export function dockerAvailable(): boolean {
  const out = spawnSync("docker", ["info"], { encoding: "utf8" });
  return out.status === 0;
}

function sleepMs(ms: number): void {
  spawnSync("sleep", [String(ms / 1000)], { encoding: "utf8" });
}

export function scratchUrl(opts: ScratchOpts = {}): string {
  const port = opts.port ?? DEFAULTS.port;
  const dbName = opts.dbName ?? DEFAULTS.dbName;
  return `postgres://postgres:probe@127.0.0.1:${port}/${dbName}`;
}

export function startScratchPg(opts: ScratchOpts = {}): string {
  const container = opts.container ?? DEFAULTS.container;
  const port = opts.port ?? DEFAULTS.port;
  const dbName = opts.dbName ?? DEFAULTS.dbName;
  spawnSync("docker", ["rm", "-f", container], { encoding: "utf8" });
  // Brief pause so the host port is released after rm (avoids ECONNRESET races).
  sleepMs(500);
  const out = spawnSync(
    "docker",
    [
      "run",
      "--rm",
      "-d",
      "--name",
      container,
      "-e",
      "POSTGRES_PASSWORD=probe",
      "-e",
      `POSTGRES_DB=${dbName}`,
      "-p",
      `${port}:5432`,
      "postgres:16",
    ],
    { encoding: "utf8" },
  );
  if (out.status !== 0) {
    throw new Error(`docker run failed:\n${out.stdout}\n${out.stderr}`);
  }
  // G9: pg_isready runs INSIDE the container (unix socket) and reports ready
  // before Docker Desktop's host-side TCP port-forward proxy is accepting.
  // That gap produced ECONNRESET on the very first client.connect() from the
  // host (T R.9 migrate + insertAttempt integration tests). The fix: after the
  // in-container probe is green, also confirm a real host-side TCP connection
  // to 127.0.0.1:port succeeds before declaring ready. Catches the specific
  // failure of the port-forward proxy lagging the container's unix socket.
  const url = scratchUrl(opts);
  for (let i = 0; i < 40; i++) {
    const ready = spawnSync(
      "docker",
      ["exec", container, "pg_isready", "-U", "postgres", "-d", dbName],
      { encoding: "utf8" },
    );
    if (ready.status === 0) {
      const tcpOk = hostTcpReady(url);
      if (tcpOk) return url;
      // in-container ready but host proxy not yet — keep polling.
    }
    sleepMs(500);
  }
  throw new Error("scratch postgres never became ready (host TCP never accepted)");
}

function hostTcpReady(url: string): boolean {
  const res = spawnSync(process.execPath, ["-e", `
const pg = require("pg");
const c = new pg.Client({ connectionString: ${JSON.stringify(url)} });
c.connect()
  .then(() => c.query("SELECT 1"))
  .then(() => c.end())
  .then(() => process.exit(0))
  .catch(() => process.exit(1));
`], { encoding: "utf8", timeout: 5000 });
  return res.status === 0;
}

export function stopScratchPg(opts: ScratchOpts = {}): void {
  const container = opts.container ?? DEFAULTS.container;
  spawnSync("docker", ["rm", "-f", container], { encoding: "utf8" });
}

/**
 * Prefer an explicit scratch URL; else managed Docker when available.
 *
 * Does **not** read ambient `DATABASE_URL` by default — that often points at a
 * shared/dev Cloud SQL instance. Opt in with `ENGINE_SCRATCH_DATABASE_URL`, or
 * `ENGINE_PG_INTEGRATION=1` + `DATABASE_URL`.
 */
export function resolveScratchDatabaseUrl(opts: ScratchOpts = {}): {
  url: string;
  managed: boolean;
  opts: ScratchOpts;
} | null {
  const explicit = (process.env.ENGINE_SCRATCH_DATABASE_URL ?? "").trim();
  const optedIn =
    Boolean(process.env.ENGINE_PG_INTEGRATION?.trim()) &&
    Boolean(process.env.DATABASE_URL?.trim());
  const provided = explicit || (optedIn ? process.env.DATABASE_URL!.trim() : "");
  if (provided) return { url: provided, managed: false, opts };
  if (!dockerAvailable()) return null;
  return { url: startScratchPg(opts), managed: true, opts };
}
