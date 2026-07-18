"""Tombstone — dev-tier Neon IaC tests removed (ADR-0031).

These tests asserted the shape of the Neon Postgres project declared in the
abandoned `infra/dev-tier/neon.tf`. That stack was retired and deleted (see
docs/adr/0031-retire-dev-tier-neon-stack.md); the live backend's database is
Cloud SQL (`database-url`), never Neon, so there is no Neon project to assert.

Left as a stub (not fully deleted) so the G8 gate
(`tests/architecture/test_no_test_weakening.py`) can see a per-test waiver.
Defines no test; excluded from collection.

Removed tests:
# G8-OK: test_exactly_one_neon_project — dev-tier Neon stack deleted (ADR-0031); no Neon project remains.
# G8-OK: test_neon_project_region_is_aws — dev-tier Neon stack deleted (ADR-0031); no Neon project remains.
# G8-OK: test_neon_project_pg_version_locked — dev-tier Neon stack deleted (ADR-0031); no Neon project remains.
# G8-OK: test_neon_database_uses_app_database_var — dev-tier Neon stack deleted (ADR-0031); no Neon project remains.
# G8-OK: test_pgvector_extension_declared — dev-tier Neon stack deleted (ADR-0031); no Neon project remains.
# G8-OK: test_neon_connection_locals_defined — dev-tier Neon stack deleted (ADR-0031); no Neon project remains.
"""
