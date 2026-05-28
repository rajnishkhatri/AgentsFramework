"""tests/infra/gcp/test_cleanup.py — Recipe 8 cleanup and teardown tests.

Verifies the acceptance criteria for safe Tier A teardown:

  * Data-tier GCS buckets (agent_facts, trust_traces) have force_destroy=true.
  * Cloud SQL deletion_protection=false (dev-only; Tier B enables it).
  * Secret versions use deletion_policy=ABANDON (shells survive partial destroy).
  * Project APIs use disable_on_destroy=false (non-disruptive teardown).
  * scripts/teardown_gcp.sh exists and references key destroy phases.

Failure paths first (TAP-4 / AGENTS.md §Testing Anti-Patterns).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.infra._hcl_helpers import find_resources
from tests.infra.gcp.conftest import REPO_ROOT


pytestmark = pytest.mark.infra_gcp

DATA_BUCKETS = {"agent_facts", "trust_traces"}
TEARDOWN_SCRIPT = REPO_ROOT / "scripts" / "teardown_gcp.sh"


def _data_buckets(resources):
    buckets = find_resources(resources, resource_type="google_storage_bucket")
    return [b for b in buckets if b["name"] in DATA_BUCKETS]


# ─────────────────────────────────────────────────────────────────────────────
# REJECT failures first
# ─────────────────────────────────────────────────────────────────────────────


def test_data_buckets_missing_force_destroy_is_a_failure(resources):
    """REJECT: buckets without force_destroy block tofu destroy when objects exist."""
    buckets = _data_buckets(resources)
    assert buckets, "Recipe 8: expected agent_facts and trust_traces buckets in data.tf"
    offenders = [
        b["name"]
        for b in buckets
        if b["attrs"].get("force_destroy") is not True
        and b["attrs"].get("force_destroy") != "true"
    ]
    assert not offenders, (
        f"Recipe 8: data-tier buckets must have force_destroy=true; "
        f"offenders: {offenders!r}"
    )


def test_cloud_sql_deletion_protection_enabled_is_a_failure(resources):
    """REJECT: deletion_protection=true blocks Recipe 8 full teardown."""
    instances = find_resources(resources, resource_type="google_sql_database_instance")
    assert instances, "no google_sql_database_instance at all"
    for inst in instances:
        dp = inst["attrs"].get("deletion_protection")
        assert dp is False or dp == "false", (
            f"Recipe 8: deletion_protection must be false at Tier A; got {dp!r}."
        )


def test_secret_version_without_abandon_policy_is_a_failure(resources):
    """REJECT: destroying secret versions on partial teardown loses operator keys."""
    versions = find_resources(
        resources, resource_type="google_secret_manager_secret_version"
    )
    assert versions, "Recipe 8: expected secret versions in secret-manager.tf"
    offenders = [
        v["name"]
        for v in versions
        if v["attrs"].get("deletion_policy") != "ABANDON"
    ]
    assert not offenders, (
        f"Recipe 8: secret versions must use deletion_policy=ABANDON; "
        f"offenders: {offenders!r}"
    )


def test_project_api_disable_on_destroy_is_a_failure(resources):
    """REJECT: disable_on_destroy=true risks turning off shared project APIs."""
    services = find_resources(resources, resource_type="google_project_service")
    assert services, "no google_project_service resources"
    offenders = [
        s["attrs"].get("service", s["name"])
        for s in services
        if s["attrs"].get("disable_on_destroy") is True
        or s["attrs"].get("disable_on_destroy") == "true"
    ]
    assert not offenders, (
        f"Recipe 8: google_project_service must have disable_on_destroy=false; "
        f"offenders: {offenders!r}"
    )


def test_teardown_script_missing_is_a_failure():
    """REJECT: Recipe 8 requires an operator-facing teardown script."""
    assert TEARDOWN_SCRIPT.is_file(), (
        f"Recipe 8: expected teardown script at {TEARDOWN_SCRIPT}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# ACCEPT paths
# ─────────────────────────────────────────────────────────────────────────────


def test_data_buckets_have_force_destroy(resources):
    """ACCEPT: both data-tier buckets declare force_destroy=true."""
    buckets = _data_buckets(resources)
    assert len(buckets) == 2, (
        f"Recipe 8: expected exactly 2 data-tier buckets; found {len(buckets)}."
    )
    for bucket in buckets:
        fd = bucket["attrs"].get("force_destroy")
        assert fd is True or fd == "true", (
            f"Recipe 8: bucket {bucket['name']!r} must have force_destroy=true."
        )


def test_teardown_script_covers_destroy_phases():
    """ACCEPT: teardown script documents partial and full modes with key targets."""
    text = TEARDOWN_SCRIPT.read_text(encoding="utf-8")
    for needle in (
        "MODE=partial",
        "MODE=full",
        "google_cloud_run_v2_service.frontend",
        "google_cloud_run_v2_service.backend_combined",
        "google_sql_database_instance.main",
        "google_storage_bucket.agent_facts",
    ):
        assert needle in text, (
            f"Recipe 8: teardown script missing expected reference: {needle!r}"
        )


def test_teardown_script_is_executable():
    """ACCEPT: teardown script has the executable bit for operator use."""
    assert TEARDOWN_SCRIPT.stat().st_mode & 0o111, (
        "Recipe 8: scripts/teardown_gcp.sh must be executable (chmod +x)."
    )
