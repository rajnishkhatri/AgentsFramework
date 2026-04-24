/**
 * drizzle.config.ts — drizzle-kit migration configuration for the
 * Sprint 2 / S2.1.2 Neon Postgres tier (IR-NEON-5).
 *
 * Authoritative invariant: `tablesFilter` MUST exclude the four LangGraph
 * checkpoint tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`,
 * `checkpoint_migrations`). LangGraph's runtime owns those tables; if
 * drizzle-kit ever regenerates them we lose checkpoint history and break
 * resumability. We use the SAFER inclusive-whitelist form (only the
 * application tables `threads` + `thread_messages`) so that a future
 * checkpoint-table-name change in LangGraph still cannot leak into the
 * migration set.
 *
 * References:
 *   - prompts/codeReviewer/frontend/architecture_rules.j2
 *     §"Sprint Story Acceptance Map" → S2.1.2
 *     §"Infra Dev-Tier Rules" → IR-NEON-5
 *   - frontend/lib/ports/thread_store.ts (P-rule docstring)
 *   - frontend/lib/adapters/thread_store/neon_free_thread_store.ts
 *
 * ## SDK pin / packaging note
 *
 * `drizzle-kit` (the migration CLI) is not yet in `frontend/package.json`
 * — only the runtime `drizzle-orm` is. When it lands as a devDependency
 * this file should switch to:
 *
 *   import { defineConfig, type Config } from "drizzle-kit";
 *   export default defineConfig({ … });
 *
 * Until then we rely on the structural `Config` type from
 * `./drizzle-kit-types.ts` so `tsc --noEmit` stays clean. drizzle-kit
 * only inspects the default-exported value; the type alias has no
 * runtime impact (per the architecture_rules.j2 deviation policy:
 * deviations are documented in the file that introduces them).
 *
 * ## Schema file
 *
 * The Drizzle schema lives at `./lib/db/schema.ts`. That file is also
 * not yet committed (the in-repo `NeonFreeThreadStore` consumes a
 * narrow `ThreadRepo` interface and is unit-tested with an in-memory
 * fake; the production schema lands with the Neon DB ACL story).
 * drizzle-kit only opens the schema file at `migrate` / `generate`
 * time, so its absence does not break config-load or `tsc --noEmit`.
 *
 * ## Credentials
 *
 * `dbCredentials.url` reads `process.env.DATABASE_URL` lazily — this is
 * a CLI-time config, not a runtime artifact. Per Frontend Style Guide
 * Rule C-* (composition / config), reading env at this layer is
 * permitted because drizzle-kit is a build/CLI tool, not part of the
 * client bundle. The runtime `NeonFreeThreadStore` adapter receives
 * its credentials via constructor injection (Rule A4 / F-R8).
 */

import type { Config } from "./drizzle-kit-types";

/**
 * Inclusive whitelist of application tables drizzle-kit may manage.
 * LangGraph checkpoint tables are intentionally absent so drizzle-kit
 * cannot regenerate them (IR-NEON-5).
 */
const APPLICATION_TABLES: readonly string[] = ["threads", "thread_messages"];

const config: Config = {
  dialect: "postgresql",
  schema: "./lib/db/schema.ts",
  out: "./lib/db/migrations",
  tablesFilter: [...APPLICATION_TABLES],
  dbCredentials: {
    url: process.env["DATABASE_URL"] ?? "",
  },
  strict: true,
  verbose: false,
};

export default config;
