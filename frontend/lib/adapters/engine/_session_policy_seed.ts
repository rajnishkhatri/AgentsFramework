/**
 * Per-mode session target policy (`content_string` rows).
 *
 * T R.8 / FR-G1: shared with ``scripts/emit_engine_seed_sql.py`` via
 * ``seed_sources/content_strings.json`` — the Postgres seed and any browser
 * hydrate must not diverge.
 *
 * WHY THE `_` PREFIX. Fixture/seed module — skipped by adapter-conformance.
 */

import contentStringsJson from "./seed_sources/content_strings.json";

export type SessionTargetContentString = {
  readonly subject: string;
  readonly key: string;
  readonly locale: string;
  readonly value: string;
};

export const SESSION_TARGET_CONTENT_STRINGS: readonly SessionTargetContentString[] =
  contentStringsJson as readonly SessionTargetContentString[];
