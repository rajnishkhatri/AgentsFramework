/**
 * Default ACT-English test-form blueprint (ADR-0015).
 *
 * T R.8 / FR-G1: shared with ``scripts/emit_engine_seed_sql.py`` via
 * ``seed_sources/blueprints.json`` — the Postgres seed and any browser
 * hydrate must not diverge.
 *
 * WHY THE `_` PREFIX. Fixture/seed module — skipped by adapter-conformance.
 */

import type { TestBlueprint } from "../../wire/engine_entities";
import blueprintsJson from "./seed_sources/blueprints.json";

export const DEFAULT_TEST_BLUEPRINTS: readonly TestBlueprint[] =
  blueprintsJson as readonly TestBlueprint[];
