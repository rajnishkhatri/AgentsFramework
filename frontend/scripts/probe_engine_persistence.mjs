#!/usr/bin/env node
/**
 * probe_engine_persistence.mjs — on-demand engine durability probe (Phase Z / T Z.1).
 *
 * Proves against a fresh (or provided) Postgres that:
 *   (a) migrate_engine.mjs applies 0000→0004 + seed_engine_content.sql
 *   (b) per-table seed counts match the committed emitter sources (FR-G1)
 *   (c) re-seed UPDATEs a mutated row and soft-retires a dropped row without
 *       deleting attempt history (FR-G2)
 *   (d/e DB-schema smoke) attempt + newest-open SQL shape still round-trip
 *       (NOT an authenticated FR-A5/FR-B4 claim — see T R.6)
 *
 * Authenticated full-stack submit + cross-context resume (FR-A5 / FR-B4) lives
 * ONLY in Playwright:
 *   frontend/e2e/full-stack/engine-persistence-probe.spec.ts
 * Optional: set PROBE_BASE_URL + PROBE_COOKIE to also exercise BFF HTTP here.
 *
 * Usage (managed local Postgres — default when DATABASE_URL unset):
 *   node frontend/scripts/probe_engine_persistence.mjs
 *
 * Usage (bring-your-own DATABASE_URL — never destroys existing data beyond
 * the probe's own learner/orphan rows):
 *   DATABASE_URL=postgres://... node frontend/scripts/probe_engine_persistence.mjs
 *
 * Not CI. Paste the JSON summary into the Phase Z / T R.6 close-out.
 */

import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import pg from "pg";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(__dirname, "..");
const MIGRATE = path.join(__dirname, "migrate_engine.mjs");

/** Expected counts from the committed seed emitter (T G.3 evidence). */
const EXPECTED_COUNTS = {
  skill: 6,
  test_item: 987,
  hint: 7857,
  tutorial: 1,
  content_string: 3,
  test_blueprint: 1,
};

const REQUIRED_MIGRATIONS = [
  "0000_frontend_baseline.sql",
  "0001_add_misconception_to_test_item.sql",
  "0002_add_tutorial_teaching_fields.sql",
  "0003_add_attempt_resolution.sql",
  "0004_durable_progress.sql",
];

const CONTAINER = "engine-probe-pg";
const MANAGED_PORT = "55432";
const MANAGED_URL = `postgres://postgres:probe@127.0.0.1:${MANAGED_PORT}/engine_probe`;

function die(msg) {
  console.error(`probe_engine_persistence: ${msg}`);
  process.exit(1);
}

function run(cmd, args, env = process.env) {
  const res = spawnSync(cmd, args, {
    encoding: "utf8",
    env,
    cwd: FRONTEND_ROOT,
  });
  if (res.status !== 0) {
    die(
      `${cmd} ${args.join(" ")} failed (status=${res.status}):\n${res.stdout}\n${res.stderr}`,
    );
  }
  return res.stdout;
}

function sleepMs(ms) {
  spawnSync("sleep", [String(ms / 1000)], { encoding: "utf8" });
}

function startManagedPg() {
  spawnSync("docker", ["rm", "-f", CONTAINER], { encoding: "utf8" });
  const out = spawnSync(
    "docker",
    [
      "run",
      "--rm",
      "-d",
      "--name",
      CONTAINER,
      "-e",
      "POSTGRES_PASSWORD=probe",
      "-e",
      "POSTGRES_DB=engine_probe",
      "-p",
      `${MANAGED_PORT}:5432`,
      "postgres:16",
    ],
    { encoding: "utf8" },
  );
  if (out.status !== 0) {
    die(`docker run failed:\n${out.stdout}\n${out.stderr}`);
  }
  for (let i = 0; i < 40; i++) {
    const ready = spawnSync(
      "docker",
      ["exec", CONTAINER, "pg_isready", "-U", "postgres", "-d", "engine_probe"],
      { encoding: "utf8" },
    );
    if (ready.status === 0) return;
    sleepMs(500);
  }
  die("managed postgres never became ready");
}

function stopManagedPg() {
  spawnSync("docker", ["rm", "-f", CONTAINER], { encoding: "utf8" });
}

async function countTable(client, table) {
  const res = await client.query(`SELECT count(*)::int AS n FROM "${table}"`);
  return res.rows[0].n;
}

async function runAuthenticatedBffProbe({ baseUrl, cookie }) {
  /** Optional T R.6 path: HttpEngineDb/BFF under a real auth cookie. */
  const headers = {
    "content-type": "application/json",
    cookie,
  };

  async function api(method, path, body) {
    const res = await fetch(`${baseUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    const text = await res.text();
    let json = null;
    if (text) {
      try {
        json = JSON.parse(text);
      } catch {
        json = text;
      }
    }
    return { status: res.status, json };
  }

  const open = await api("POST", "/api/engine/session/open", {
    subject: "act-english",
    mode: "adaptive",
    target_count: 30,
  });
  if (open.status !== 200 || !open.json?.id) {
    return {
      step: "f_authenticated_fullstack",
      ok: false,
      phase: "session/open",
      status: open.status,
      body: open.json,
    };
  }
  const sessionId = open.json.id;

  const next = await api(
    "GET",
    `/api/engine/next?session=${encodeURIComponent(sessionId)}`,
  );
  if (next.status !== 200 || next.json?.empty || !next.json?.question?.id) {
    return {
      step: "f_authenticated_fullstack",
      ok: false,
      phase: "next",
      status: next.status,
      body: next.json,
      session_id: sessionId,
    };
  }
  const questionId = next.json.question.id;

  const attempt = await api("POST", "/api/engine/attempt", {
    subject: "act-english",
    session_id: sessionId,
    question_id: questionId,
    chosen_letter: "A",
    correct: true,
    elapsed_ms: 100,
    used_hint: false,
    resolution: "first_try",
    idempotency_key: randomUUID(),
  });
  if (attempt.status !== 200 || !attempt.json?.id) {
    return {
      step: "f_authenticated_fullstack",
      ok: false,
      phase: "attempt",
      status: attempt.status,
      body: attempt.json,
      session_id: sessionId,
    };
  }

  const listed = await api("POST", "/api/engine/db/listSessionAttempts", {
    args: [sessionId],
  });
  if (
    listed.status !== 200 ||
    !Array.isArray(listed.json) ||
    listed.json.length < 1
  ) {
    return {
      step: "f_authenticated_fullstack",
      ok: false,
      phase: "listSessionAttempts",
      status: listed.status,
      body: listed.json,
      session_id: sessionId,
    };
  }

  const active = await api(
    "GET",
    "/api/engine/session/active?subject=act-english",
  );
  if (active.status !== 200 || active.json?.session?.id !== sessionId) {
    return {
      step: "f_authenticated_fullstack",
      ok: false,
      phase: "session/active",
      status: active.status,
      body: active.json,
      expected_session_id: sessionId,
    };
  }

  return {
    step: "f_authenticated_fullstack",
    ok: true,
    session_id: sessionId,
    attempt_id: attempt.json.id,
    question_id: questionId,
    listed_attempts: listed.json.length,
    via: "PROBE_BASE_URL+PROBE_COOKIE → BFF",
  };
}

async function main() {
  const provided = (process.env.DATABASE_URL ?? "").trim();
  const managed = !provided;
  const databaseUrl = provided || MANAGED_URL;
  const steps = [];

  if (managed) {
    console.log("starting managed postgres container…");
    startManagedPg();
    steps.push({ step: "a0_managed_pg", ok: true, url_host: `127.0.0.1:${MANAGED_PORT}` });
  } else {
    steps.push({ step: "a0_provided_url", ok: true });
  }

  try {
    // (a) full inventory migrate + seed
    console.log("running migrate_engine.mjs…");
    const migrateOut = run("node", [MIGRATE], {
      ...process.env,
      DATABASE_URL: databaseUrl,
    });
    let migrateJson;
    try {
      const line = migrateOut
        .trim()
        .split("\n")
        .reverse()
        .find((l) => l.startsWith("{"));
      migrateJson = JSON.parse(line);
    } catch {
      die(`migrate_engine did not emit JSON summary:\n${migrateOut}`);
    }
    steps.push({ step: "a_migrate", ok: true, migrate: migrateJson });

    const client = new pg.Client({ connectionString: databaseUrl });
    await client.connect();
    try {
      const ledger = await client.query(
        `SELECT filename FROM "_frontend_migrations" ORDER BY filename`,
      );
      const applied = ledger.rows.map((r) => r.filename);
      for (const name of REQUIRED_MIGRATIONS) {
        if (!applied.includes(name)) {
          die(`ledger missing ${name}; applied=${JSON.stringify(applied)}`);
        }
      }
      steps.push({ step: "a_ledger", ok: true, applied });

      // (b) per-table seed counts
      const counts = {};
      for (const [table, expected] of Object.entries(EXPECTED_COUNTS)) {
        counts[table] = await countTable(client, table);
        if (counts[table] !== expected) {
          die(
            `FR-G1 count mismatch ${table}: got ${counts[table]} want ${expected}`,
          );
        }
      }
      steps.push({ step: "b_seed_counts", ok: true, counts });

      // Pick a real seeded item for mutation / attempt tests.
      const itemRes = await client.query(
        `SELECT id, stem_md FROM "test_item" WHERE reviewed = true ORDER BY id LIMIT 1`,
      );
      if (itemRes.rowCount === 0) die("no reviewed test_item after seed");
      const probeItem = itemRes.rows[0];
      const originalStem = probeItem.stem_md;

      // (c) CHANGED row → UPDATE on re-seed
      await client.query(
        `UPDATE "test_item" SET stem_md = $1 WHERE id = $2`,
        ["PROBE_MUTATED_STEM", probeItem.id],
      );
      run("node", [MIGRATE], { ...process.env, DATABASE_URL: databaseUrl });
      const afterChange = await client.query(
        `SELECT stem_md FROM "test_item" WHERE id = $1`,
        [probeItem.id],
      );
      if (afterChange.rows[0].stem_md === "PROBE_MUTATED_STEM") {
        die("FR-G2: re-seed did not UPDATE mutated stem_md");
      }
      if (afterChange.rows[0].stem_md !== originalStem) {
        die(
          `FR-G2: re-seed restored unexpected stem (got ${JSON.stringify(afterChange.rows[0].stem_md)})`,
        );
      }
      steps.push({
        step: "c_changed_row_updated",
        ok: true,
        item_id: probeItem.id,
      });

      // (c) DROPPED row → soft-retire; attempt history intact
      const orphanId = `ti-probe-orphan-${randomUUID().slice(0, 8)}`;
      await client.query(
        `INSERT INTO "test_item" (
           "id", "subject", "skill_id", "difficulty", "context_html", "stem_md",
           "choices", "answer_letter", "per_choice_rationale", "why_correct_md",
           "why_tempted_md", "rule_md", "item_type", "misconception",
           "reviewed", "generated_by"
         ) VALUES (
           $1, 'act-english', 's-punc', 2, '', 'orphan stem',
           '[]'::jsonb, 'A', '{}'::jsonb, '', '', '', 'underlined-span-mc',
           NULL, true, 'probe'
         )`,
        [orphanId],
      );
      const orphanLearner = `learner-probe-${randomUUID().slice(0, 8)}`;
      const orphanSession = `qs-probe-orphan-${randomUUID().slice(0, 8)}`;
      const orphanAttempt = `att-probe-orphan-${randomUUID().slice(0, 8)}`;
      await client.query(
        `INSERT INTO "quiz_session" (
           "id", "subject", "learner_id", "mode", "started_at", "target_count"
         ) VALUES ($1, 'act-english', $2, 'adaptive', now(), 30)`,
        [orphanSession, orphanLearner],
      );
      await client.query(
        `INSERT INTO "attempt" (
           "id", "subject", "session_id", "question_id", "chosen_letter",
           "correct", "elapsed_ms", "used_hint", "created_at", "resolution"
         ) VALUES (
           $1, 'act-english', $2, $3, 'A', false, 100, false, now(), 'first_try'
         )`,
        [orphanAttempt, orphanSession, orphanId],
      );

      run("node", [MIGRATE], { ...process.env, DATABASE_URL: databaseUrl });

      const retired = await client.query(
        `SELECT reviewed FROM "test_item" WHERE id = $1`,
        [orphanId],
      );
      if (retired.rowCount !== 1 || retired.rows[0].reviewed !== false) {
        die("FR-G2: dropped orphan was not soft-retired (reviewed=false)");
      }
      const hist = await client.query(
        `SELECT id FROM "attempt" WHERE id = $1`,
        [orphanAttempt],
      );
      if (hist.rowCount !== 1) {
        die("FR-G2: attempt history was destroyed on retire");
      }
      steps.push({
        step: "c_dropped_row_retired",
        ok: true,
        orphan_id: orphanId,
        attempt_preserved: orphanAttempt,
      });

      // (d/e) DB-schema smoke only — NOT authenticated FR-A5/FR-B4 (T R.6).
      // Authenticated submit + cross-context resume is owned by
      // e2e/full-stack/engine-persistence-probe.spec.ts.
      const learnerId = `learner-probe-${randomUUID().slice(0, 8)}`;
      const sessionId = `qs-probe-${randomUUID().slice(0, 8)}`;
      const attemptId = `att-probe-${randomUUID().slice(0, 8)}`;
      const idem = randomUUID();
      await client.query(
        `INSERT INTO "quiz_session" (
           "id", "subject", "learner_id", "mode", "started_at",
           "target_count", "current_question_id"
         ) VALUES ($1, 'act-english', $2, 'adaptive', now(), 30, $3)`,
        [sessionId, learnerId, probeItem.id],
      );
      await client.query(
        `INSERT INTO "attempt" (
           "id", "subject", "session_id", "question_id", "chosen_letter",
           "correct", "elapsed_ms", "used_hint", "created_at", "resolution",
           "idempotency_key"
         ) VALUES (
           $1, 'act-english', $2, $3, 'B', true, 250, false, now(),
           'first_try', $4::uuid
         )`,
        [attemptId, sessionId, probeItem.id, idem],
      );
      const attemptRow = await client.query(
        `SELECT id, question_id, correct, idempotency_key::text AS idem
           FROM "attempt" WHERE id = $1`,
        [attemptId],
      );
      if (attemptRow.rowCount !== 1) {
        die("DB-schema smoke: attempt row missing after insert");
      }
      steps.push({
        step: "d_db_schema_attempt_row",
        ok: true,
        note: "schema/idempotency_key smoke only — not FR-A5; see engine-persistence-probe.spec.ts",
        session_id: sessionId,
        attempt_id: attemptId,
        question_id: attemptRow.rows[0].question_id,
        idempotency_key: attemptRow.rows[0].idem,
      });

      const olderId = `qs-probe-older-${randomUUID().slice(0, 8)}`;
      await client.query(
        `INSERT INTO "quiz_session" (
           "id", "subject", "learner_id", "mode", "started_at", "target_count"
         ) VALUES ($1, 'act-english', $2, 'adaptive', now() - interval '1 hour', 30)`,
        [olderId, learnerId],
      );
      const newest = await client.query(
        `SELECT id, current_question_id, ended_at
           FROM "quiz_session"
          WHERE subject = 'act-english'
            AND learner_id = $1
            AND ended_at IS NULL
          ORDER BY started_at DESC, id DESC
          LIMIT 1`,
        [learnerId],
      );
      if (newest.rowCount !== 1 || newest.rows[0].id !== sessionId) {
        die(
          `DB-schema smoke: expected newest open=${sessionId}, got ${JSON.stringify(newest.rows)}`,
        );
      }
      if (newest.rows[0].current_question_id !== probeItem.id) {
        die("DB-schema smoke: served pointer not readable on resume candidate");
      }
      steps.push({
        step: "e_db_schema_newest_open",
        ok: true,
        note: "SQL newest-open smoke only — not FR-B4; see engine-persistence-probe.spec.ts",
        learner_id: learnerId,
        resumed_session_id: newest.rows[0].id,
        current_question_id: newest.rows[0].current_question_id,
        older_open_skipped: olderId,
      });

      // Optional authenticated BFF path (T R.6) when an operator points at a
      // running durable frontend with a session cookie.
      const probeBase = (process.env.PROBE_BASE_URL ?? "").replace(/\/$/, "");
      const probeCookie = (process.env.PROBE_COOKIE ?? "").trim();
      if (probeBase && probeCookie) {
        const authStep = await runAuthenticatedBffProbe({
          baseUrl: probeBase,
          cookie: probeCookie,
        });
        steps.push(authStep);
        if (!authStep.ok) {
          die(`authenticated BFF probe failed: ${JSON.stringify(authStep)}`);
        }
      } else {
        steps.push({
          step: "f_authenticated_fullstack",
          status: "deferred",
          owner: "engine-persistence-probe.spec.ts",
          note:
            "Set PROBE_BASE_URL+PROBE_COOKIE to exercise BFF here; otherwise run Playwright",
        });
      }

      const summary = {
        ok: true,
        managed_pg: managed,
        steps,
        expected_counts: EXPECTED_COUNTS,
        authenticated_fullstack: "engine-persistence-probe.spec.ts",
      };
      console.log(JSON.stringify(summary, null, 2));
    } finally {
      await client.end();
    }
  } finally {
    if (managed) {
      console.log("stopping managed postgres container…");
      stopManagedPg();
    }
  }
}

main().catch((err) => die(err?.stack || String(err)));
