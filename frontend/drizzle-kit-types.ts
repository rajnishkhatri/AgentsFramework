/**
 * drizzle-kit-types.ts — structural type fallback for drizzle-kit's
 * `Config` shape.
 *
 * `drizzle-kit` is the migration CLI for `drizzle-orm`. It is intentionally
 * NOT in `frontend/package.json` today (Sprint 2 only needs the runtime
 * `drizzle-orm` to satisfy the IR-NEON-5 invariant; migrations land later
 * with the Neon DB ACL story). When the CLI is eventually added to
 * devDependencies, this file should be removed and `drizzle.config.ts`
 * should switch to `import { defineConfig, type Config } from "drizzle-kit"`.
 *
 * Until then, this structural type lets `tsc --noEmit` validate the
 * config object without needing the package on disk. The fields below
 * mirror the public surface documented at
 * https://orm.drizzle.team/kit-docs/config-reference (only the fields we
 * actually use are typed; unknown fields are tolerated via index signature).
 */

export type DrizzleDialect =
  | "postgresql"
  | "mysql"
  | "sqlite"
  | "turso"
  | "singlestore"
  | "gel";

/**
 * Structural mirror of `drizzle-kit`'s `Config` type. Only the fields
 * the in-repo `drizzle.config.ts` actually sets are typed; anything else
 * is permitted via the index signature so future drizzle-kit versions
 * that add fields remain compatible.
 */
export interface Config {
  dialect: DrizzleDialect;
  schema: string | string[];
  out: string;
  /**
   * Inclusive whitelist OR negation list of database tables that
   * drizzle-kit may introspect / generate migrations for. Per IR-NEON-5
   * the LangGraph checkpoint tables (`checkpoints`, `checkpoint_writes`,
   * `checkpoint_blobs`, `checkpoint_migrations`) MUST be excluded so
   * drizzle-kit cannot regenerate them.
   */
  tablesFilter?: string | string[];
  schemaFilter?: string | string[];
  dbCredentials?: {
    url: string;
  };
  migrations?: {
    table?: string;
    schema?: string;
  };
  verbose?: boolean;
  strict?: boolean;
  [key: string]: unknown;
}
