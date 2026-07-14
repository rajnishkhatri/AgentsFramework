"""Tombstone — dev-tier Secret Manager IaC tests removed (ADR-0031).

These tests asserted the shape of the Secret Manager secrets + IAM bindings in
the abandoned `infra/dev-tier/secret-manager.tf` (e.g. `neon-database-url`
scoped to the `agent-middleware-runtime` SA). That stack was retired and
deleted (see docs/adr/0031-retire-dev-tier-neon-stack.md). The live GCP Tier A
secrets are covered by `tests/infra/gcp/test_secret_manager.py` (`-m infra_gcp`).

Left as a stub (not fully deleted) so the G8 gate
(`tests/architecture/test_no_test_weakening.py`) can see a per-test waiver.
Defines no test; excluded from collection.

Removed tests:
# G8-OK: test_all_required_secrets_declared — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
# G8-OK: test_every_secret_has_replication_block — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
# G8-OK: test_every_secret_has_a_version — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
# G8-OK: test_no_plaintext_secret_data_in_hcl — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
# G8-OK: test_every_secret_has_iam_accessor_for_runtime_sa — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
# G8-OK: test_no_iam_member_grants_to_external_principal — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
# G8-OK: test_cloud_run_references_every_required_secret — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
# G8-OK: test_every_secret_var_is_marked_sensitive — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
# G8-OK: test_no_secret_var_is_named_next_public — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_secret_manager.py.
"""
