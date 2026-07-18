"""Tombstone — dev-tier cross-cutting IaC tests removed (ADR-0031).

These tests asserted cross-cutting HCL hygiene (no `next_public_*` vars, no
secret outputs, snake_case local names, leading docstrings, …) over the
abandoned `infra/dev-tier/*.tf`. That stack was retired and deleted (see
docs/adr/0031-retire-dev-tier-neon-stack.md). The equivalent hygiene over the
live GCP stack is covered by `tests/infra/gcp/test_cross_cutting.py`
(`-m infra_gcp`).

Left as a stub (not fully deleted) so the G8 gate
(`tests/architecture/test_no_test_weakening.py`) can see a per-test waiver.
Defines no test; excluded from collection.

Removed tests:
# G8-OK: test_no_variable_starts_with_next_public — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_cross_cutting.py.
# G8-OK: test_no_secret_outputs — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_cross_cutting.py.
# G8-OK: test_no_hardcoded_credentials_in_providers — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_cross_cutting.py.
# G8-OK: test_no_trace_id_generation_in_hcl — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_cross_cutting.py.
# G8-OK: test_every_tf_file_has_leading_docstring — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_cross_cutting.py.
# G8-OK: test_resource_local_names_are_snake_case — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_cross_cutting.py.
# G8-OK: test_no_cloud_run_env_var_has_literal_secret — dev-tier stack deleted (ADR-0031); covered live by tests/infra/gcp/test_cross_cutting.py.
"""
