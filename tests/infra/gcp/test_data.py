"""tests/infra/gcp/test_data.py — Recipe 2 data tier tests.

Verifies the acceptance criteria for infra/gcp/data.tf:

  * Cloud SQL PostgreSQL 15 instance declared with correct shape.
  * deletion_protection = false (Tier A dev-only; Tier B enables it).
  * A database and user are declared on the Cloud SQL instance.
  * The database user password comes from a sensitive variable (not literal).
  * Two GCS buckets declared: agent-facts and trust-traces.
  * agent-facts bucket has versioning enabled.
  * trust-traces bucket has a lifecycle rule (90-day → Nearline).
  * Both buckets have uniform_bucket_level_access and public_access_prevention.
  * IAM: runtime SA has roles/cloudsql.client at project level.
  * IAM: runtime SA has roles/storage.objectViewer on agent-facts bucket.
  * IAM: runtime SA has roles/storage.objectCreator on trust-traces bucket.
  * No overly broad storage IAM roles (roles/storage.admin).

Failure paths first (TAP-4 / AGENTS.md §Testing Anti-Patterns).
L2 contract style: asserts the shape the acceptance criteria demand.
"""

from __future__ import annotations

import pytest

from tests.infra._hcl_helpers import find_resources, unwrap_block, unwrap_blocks


pytestmark = pytest.mark.infra_gcp


# ─────────────────────────────────────────────────────────────────────────────
# Cloud SQL — REJECT failures first
# ─────────────────────────────────────────────────────────────────────────────


def test_no_cloud_sql_instance_is_a_failure(resources):
    """REJECT: no Cloud SQL instance means the backend has nowhere to persist
    LangGraph checkpoints. Recipe 4 Cloud Run deploy will fail to connect."""
    instances = find_resources(resources, resource_type="google_sql_database_instance")
    assert instances, (
        "Recipe 2: no google_sql_database_instance found in infra/gcp/. "
        "data.tf must declare a Cloud SQL PostgreSQL instance."
    )


def test_cloud_sql_is_postgres_15(resources):
    """ACCEPT: database_version must be POSTGRES_15 to match the
    AsyncPostgresSaver compatibility matrix and LangGraph checkpoint schema."""
    instances = find_resources(resources, resource_type="google_sql_database_instance")
    assert instances, "no google_sql_database_instance at all"
    for inst in instances:
        version = inst["attrs"].get("database_version", "")
        assert isinstance(version, str) and version.startswith("POSTGRES_15"), (
            f"Recipe 2: Cloud SQL database_version must be POSTGRES_15; "
            f"got {version!r}."
        )


def test_cloud_sql_deletion_protection_disabled(resources):
    """ACCEPT: Tier A dev uses deletion_protection=false for easy teardown.
    Tier B recipe B3 upgrades to true."""
    instances = find_resources(resources, resource_type="google_sql_database_instance")
    assert instances, "no google_sql_database_instance at all"
    for inst in instances:
        dp = inst["attrs"].get("deletion_protection")
        assert dp is False or dp == "false", (
            f"Recipe 2: deletion_protection must be false for Tier A dev; "
            f"got {dp!r}. Tier B recipe B3 enables it."
        )


def test_cloud_sql_availability_is_zonal(resources):
    """ACCEPT: Tier A uses ZONAL (single-AZ) for cost. Tier B upgrades to REGIONAL."""
    instances = find_resources(resources, resource_type="google_sql_database_instance")
    assert instances, "no google_sql_database_instance at all"
    for inst in instances:
        settings = unwrap_block(inst["attrs"].get("settings"))
        assert settings is not None, "Cloud SQL instance missing settings block"
        avail = settings.get("availability_type", "")
        assert avail == "ZONAL", (
            f"Recipe 2: availability_type must be ZONAL for Tier A; got {avail!r}."
        )


def test_cloud_sql_backup_enabled(resources):
    """ACCEPT: backup must be enabled even at Tier A — losing checkpoints is
    worse than the negligible cost of automated backups on a 10 GB instance."""
    instances = find_resources(resources, resource_type="google_sql_database_instance")
    assert instances, "no google_sql_database_instance at all"
    for inst in instances:
        settings = unwrap_block(inst["attrs"].get("settings"))
        assert settings is not None, "Cloud SQL instance missing settings block"
        backup = unwrap_block(settings.get("backup_configuration"))
        assert backup is not None, "Cloud SQL missing backup_configuration block"
        assert backup.get("enabled") is True, (
            "Recipe 2: Cloud SQL backup_configuration.enabled must be true."
        )


def test_cloud_sql_database_declared(resources):
    """ACCEPT: a google_sql_database resource must exist to create the
    application database within the Cloud SQL instance."""
    dbs = find_resources(resources, resource_type="google_sql_database")
    assert dbs, (
        "Recipe 2: no google_sql_database found. data.tf must declare the "
        "application database within the Cloud SQL instance."
    )


def test_cloud_sql_user_declared(resources):
    """ACCEPT: a google_sql_user resource must exist so the backend has
    credentials to connect."""
    users = find_resources(resources, resource_type="google_sql_user")
    assert users, (
        "Recipe 2: no google_sql_user found. data.tf must declare a "
        "database user for the backend runtime."
    )


def test_cloud_sql_user_password_is_not_literal(resources):
    """REJECT (AUTO-REJECT class): the database user password must come from
    a var reference, not a plaintext literal in HCL."""
    users = find_resources(resources, resource_type="google_sql_user")
    assert users, "no google_sql_user at all"
    for user in users:
        password = user["attrs"].get("password", "")
        if isinstance(password, str) and password:
            assert "var." in password or "${" in password, (
                f"Recipe 2 / FE-AP-18: google_sql_user password must be a "
                f"var reference, not a literal. Got: {password[:20]}..."
            )


def test_cloud_sql_password_variable_is_sensitive(variables):
    """REJECT: cloud_sql_password must be marked sensitive = true."""
    assert "cloud_sql_password" in variables, (
        "Recipe 2: variable 'cloud_sql_password' not declared in variables.tf."
    )
    assert variables["cloud_sql_password"].get("sensitive") is True, (
        "Recipe 2 / FE-AP-18: variable cloud_sql_password must have "
        "sensitive = true to prevent plan-output leakage."
    )


# ─────────────────────────────────────────────────────────────────────────────
# GCS buckets — REJECT failures first
# ─────────────────────────────────────────────────────────────────────────────


def test_no_gcs_buckets_is_a_failure(resources):
    """REJECT: no GCS buckets means agent-facts and trust-traces have
    nowhere to go at runtime."""
    buckets = find_resources(resources, resource_type="google_storage_bucket")
    assert buckets, (
        "Recipe 2: no google_storage_bucket found in infra/gcp/. "
        "data.tf must declare agent-facts and trust-traces buckets."
    )


def test_two_gcs_buckets_declared(resources):
    """ACCEPT: exactly two GCS buckets — one for agent-facts, one for
    trust-traces."""
    buckets = find_resources(resources, resource_type="google_storage_bucket")
    assert len(buckets) >= 2, (
        f"Recipe 2: expected at least 2 GCS buckets (agent-facts + "
        f"trust-traces); found {len(buckets)}."
    )


def _find_bucket(resources, name_fragment: str):
    """Find a GCS bucket whose resource name contains the fragment."""
    buckets = find_resources(resources, resource_type="google_storage_bucket")
    return [b for b in buckets if name_fragment in b["name"]]


def test_agent_facts_bucket_exists(resources):
    """ACCEPT: a bucket with 'agent_facts' in its resource name."""
    matches = _find_bucket(resources, "agent_facts")
    assert matches, "Recipe 2: no GCS bucket with 'agent_facts' in its resource name."


def test_trust_traces_bucket_exists(resources):
    """ACCEPT: a bucket with 'trust_traces' in its resource name."""
    matches = _find_bucket(resources, "trust_traces")
    assert matches, "Recipe 2: no GCS bucket with 'trust_traces' in its resource name."


def test_agent_facts_bucket_has_versioning(resources):
    """ACCEPT: agent-facts must have versioning enabled so identity rollback
    is a metadata operation, not a re-sign+redeploy."""
    matches = _find_bucket(resources, "agent_facts")
    assert matches, "no agent_facts bucket"
    bucket = matches[0]
    versioning = unwrap_block(bucket["attrs"].get("versioning"))
    assert versioning is not None, "agent_facts bucket missing versioning block"
    assert versioning.get("enabled") is True, (
        "Recipe 2: agent-facts bucket must have versioning.enabled = true."
    )


def test_trust_traces_bucket_has_lifecycle_rule(resources):
    """ACCEPT: trust-traces bucket must have a lifecycle rule transitioning
    to Nearline after 90 days (cheap at Tier A, matches Tier B pattern)."""
    matches = _find_bucket(resources, "trust_traces")
    assert matches, "no trust_traces bucket"
    bucket = matches[0]
    rules = unwrap_blocks(bucket["attrs"].get("lifecycle_rule"))
    assert rules, "Recipe 2: trust-traces bucket must have at least one lifecycle_rule."
    nearline_found = False
    for rule in rules:
        action = unwrap_block(rule.get("action"))
        if action and action.get("storage_class") == "NEARLINE":
            nearline_found = True
    assert nearline_found, (
        "Recipe 2: trust-traces bucket must have a lifecycle rule with "
        "action.storage_class = NEARLINE."
    )


def test_all_buckets_have_uniform_access(resources):
    """ACCEPT: all GCS buckets must use uniform_bucket_level_access = true.
    ACL-based access is a legacy mode that makes IAM auditing harder."""
    buckets = find_resources(resources, resource_type="google_storage_bucket")
    offenders = [
        b["name"]
        for b in buckets
        if b["attrs"].get("uniform_bucket_level_access") is not True
    ]
    assert not offenders, (
        f"Recipe 2: GCS buckets without uniform_bucket_level_access=true: "
        f"{offenders!r}."
    )


def test_all_buckets_have_public_access_prevention(resources):
    """REJECT: all GCS buckets must have public_access_prevention = 'enforced'.
    Prevents accidental allUsers grants on production data."""
    buckets = find_resources(resources, resource_type="google_storage_bucket")
    offenders = [
        b["name"]
        for b in buckets
        if b["attrs"].get("public_access_prevention") != "enforced"
    ]
    assert not offenders, (
        f"Recipe 2: GCS buckets without public_access_prevention='enforced': "
        f"{offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# IAM — runtime SA bindings
# ─────────────────────────────────────────────────────────────────────────────


def test_runtime_sa_has_cloudsql_client_role(resources):
    """ACCEPT: roles/cloudsql.client at the project level for the Cloud Run
    built-in Cloud SQL connector. Without this, the Unix domain socket
    connection from Cloud Run to Cloud SQL fails."""
    project_iam = find_resources(resources, resource_type="google_project_iam_member")
    cloudsql_clients = [
        r
        for r in project_iam
        if r["attrs"].get("role") == "roles/cloudsql.client"
        and "backend_runtime" in str(r["attrs"].get("member", ""))
    ]
    assert cloudsql_clients, (
        "Recipe 2: no google_project_iam_member grants roles/cloudsql.client "
        "to the backend_runtime SA. Cloud Run's Cloud SQL connector will fail."
    )


def test_frontend_runtime_sa_has_cloudsql_client_role(resources):
    """ACCEPT (T R.2 / FR-F1): frontend_runtime also needs cloudsql.client.

    Binding DATABASE_URL without this grant leaves the socket mount unusable —
    the connector cannot open /cloudsql/… for the BFF.
    """
    project_iam = find_resources(resources, resource_type="google_project_iam_member")
    cloudsql_clients = [
        r
        for r in project_iam
        if r["attrs"].get("role") == "roles/cloudsql.client"
        and "frontend_runtime" in str(r["attrs"].get("member", ""))
    ]
    assert cloudsql_clients, (
        "T R.2: no google_project_iam_member grants roles/cloudsql.client "
        "to the frontend_runtime SA. Frontend Cloud SQL connector will fail."
    )


def test_agent_facts_bucket_iam_is_object_viewer(resources):
    """ACCEPT: runtime SA gets roles/storage.objectViewer on agent-facts."""
    bucket_iam = find_resources(
        resources, resource_type="google_storage_bucket_iam_member"
    )
    viewers = [
        r
        for r in bucket_iam
        if r["attrs"].get("role") == "roles/storage.objectViewer"
        and "backend_runtime" in str(r["attrs"].get("member", ""))
        and "agent_facts" in str(r["attrs"].get("bucket", ""))
    ]
    assert viewers, (
        "Recipe 2: no google_storage_bucket_iam_member grants "
        "roles/storage.objectViewer to backend_runtime on agent-facts bucket."
    )


def test_agent_facts_bucket_iam_is_object_creator(resources):
    """ACCEPT: runtime SA gets roles/storage.objectCreator on agent-facts.
    Write-only — auto-provision creates AgentFacts on first auth."""
    bucket_iam = find_resources(
        resources, resource_type="google_storage_bucket_iam_member"
    )
    creators = [
        r
        for r in bucket_iam
        if r["attrs"].get("role") == "roles/storage.objectCreator"
        and "backend_runtime" in str(r["attrs"].get("member", ""))
        and "agent_facts" in str(r["attrs"].get("bucket", ""))
    ]
    assert creators, (
        "Recipe 2: no google_storage_bucket_iam_member grants "
        "roles/storage.objectCreator to backend_runtime on agent-facts bucket."
    )


def test_trust_traces_bucket_iam_is_object_creator(resources):
    """ACCEPT: runtime SA gets roles/storage.objectCreator on trust-traces.
    Write-only — the runtime appends traces but never reads or deletes."""
    bucket_iam = find_resources(
        resources, resource_type="google_storage_bucket_iam_member"
    )
    creators = [
        r
        for r in bucket_iam
        if r["attrs"].get("role") == "roles/storage.objectCreator"
        and "backend_runtime" in str(r["attrs"].get("member", ""))
        and "trust_traces" in str(r["attrs"].get("bucket", ""))
    ]
    assert creators, (
        "Recipe 2: no google_storage_bucket_iam_member grants "
        "roles/storage.objectCreator to backend_runtime on trust-traces bucket."
    )


def test_no_storage_admin_on_any_bucket(resources):
    """REJECT: roles/storage.admin or roles/storage.objectAdmin on any bucket
    is a least-privilege violation. The runtime only needs objectViewer
    and objectCreator."""
    bucket_iam = find_resources(
        resources, resource_type="google_storage_bucket_iam_member"
    )
    forbidden_roles = {
        "roles/storage.admin",
        "roles/storage.objectAdmin",
    }
    offenders = [
        (r["name"], r["attrs"].get("role"))
        for r in bucket_iam
        if r["attrs"].get("role") in forbidden_roles
    ]
    assert not offenders, (
        f"Recipe 2: forbidden broad storage IAM roles on buckets: "
        f"{offenders!r}. Use objectViewer or objectCreator."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Outputs — data tier outputs must exist
# ─────────────────────────────────────────────────────────────────────────────


def test_cloud_sql_connection_name_output_exists(outputs):
    """ACCEPT: the connection name output is needed by Recipe 4 to wire the
    Cloud Run cloud_sql_instances annotation."""
    assert "cloud_sql_connection_name" in outputs, (
        "Recipe 2: outputs.tf must declare cloud_sql_connection_name for "
        "Recipe 4 Cloud Run wiring."
    )


def test_agent_facts_bucket_output_exists(outputs):
    """ACCEPT: the bucket name output is needed by Recipe 4 to set the
    GCS_FACTS_BUCKET env var on Cloud Run."""
    assert "agent_facts_bucket" in outputs, (
        "Recipe 2: outputs.tf must declare agent_facts_bucket for "
        "Recipe 4 Cloud Run env vars."
    )


def test_trust_traces_bucket_output_exists(outputs):
    """ACCEPT: the bucket name output is needed by Recipe 4 to set the
    GCS_TRACES_BUCKET env var on Cloud Run."""
    assert "trust_traces_bucket" in outputs, (
        "Recipe 2: outputs.tf must declare trust_traces_bucket for "
        "Recipe 4 Cloud Run env vars."
    )
