"""Tombstone — dev-tier Cloud Run IaC tests removed (ADR-0031).

These tests asserted the shape of the `agent-middleware` Cloud Run service and
its runtime SA in the abandoned `infra/dev-tier/` (Neon) OpenTofu stack. That
stack — and the `agent-middleware` service it declared — was retired and
deleted (see docs/adr/0031-retire-dev-tier-neon-stack.md), so the resource each
test asserted no longer exists. The live IaC is `infra/gcp/`, audited by
`tests/infra/gcp/` (`-m infra_gcp`).

This file is intentionally left as a stub, not fully deleted, so the G8
test-mass-rewrite gate (`tests/architecture/test_no_test_weakening.py`) can see
a per-test waiver for each removed function. It defines no test and is excluded
from collection.

Removed tests (each deleted because the dev-tier resource it asserted is gone):
# G8-OK: test_cloud_run_service_exists — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_cloud_run_service_named_agent_middleware — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_cloud_run_min_instance_count_is_zero — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_cloud_run_cpu_is_1000m — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_cloud_run_memory_is_2gi — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_cloud_run_request_timeout_is_3600s — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_cloud_run_startup_cpu_boost_enabled — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_cloud_run_startup_probe_hits_healthz — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_cloud_run_uses_dedicated_service_account — dev-tier stack deleted (ADR-0031); asserted resource gone.
# G8-OK: test_dedicated_runtime_service_account_exists — dev-tier stack deleted (ADR-0031); asserted resource gone.
"""
