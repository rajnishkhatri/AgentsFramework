"""tests/infra/gcp/test_foundations.py — Recipe 1 GCP foundations tests.

Verifies the acceptance criteria for infra/gcp/foundations.tf:

  * All 11 required GCP APIs are enabled via google_project_service.
  * disable_on_destroy = false on every API resource (non-destructive teardown).
  * A Docker Artifact Registry repository is declared.
  * A backend runtime service account is declared with the right account_id.
  * The runtime SA has AR reader, log writer, and metric writer IAM bindings.
  * No overly broad project-level roles are granted to the runtime SA.

Failure paths first (TAP-4 / AGENTS.md §Testing Anti-Patterns).
L2 contract style: asserts the shape the acceptance criteria demand, not
which exact variable references are used.
"""

from __future__ import annotations

import pytest

from tests.infra._hcl_helpers import find_resources, get_one

pytestmark = pytest.mark.infra_gcp


REQUIRED_APIS = {
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbilling.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudscheduler.googleapis.com",
}

# Roles allowed at the project level for the runtime SA (least-privilege baseline).
ALLOWED_PROJECT_ROLES = {
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudsql.client",  # Recipe 2: Cloud Run built-in Cloud SQL connector
}

# Roles forbidden at the project level.
FORBIDDEN_PROJECT_ROLES = {
    "roles/editor",
    "roles/owner",
    "roles/iam.securityAdmin",
    "roles/storage.admin",
    "roles/secretmanager.admin",
}


# ─────────────────────────────────────────────────────────────────────────────
# API enablement — REJECTION failures first.
# ─────────────────────────────────────────────────────────────────────────────


def test_no_api_resources_declared_is_a_failure(resources):
    """REJECT: if no google_project_service resources exist the Tofu apply
    will silently succeed with no APIs enabled and all downstream resources
    will fail at apply-time. Catch it here in fast feedback land.

    This is the red-state entry point for TDD on foundations.tf.
    """
    api_resources = find_resources(resources, resource_type="google_project_service")
    assert api_resources, (
        "Recipe 1: no google_project_service resources found in infra/gcp/. "
        "foundations.tf must enable all required APIs."
    )


def test_all_required_apis_are_enabled(resources):
    """ACCEPT: every required API has a google_project_service resource.

    Missing an API here causes silent downstream failures at apply-time
    (e.g. omitting sqladmin.googleapis.com makes Cloud SQL provisioning
    fail with a cryptic 403 rather than a clear 'API not enabled' error).
    """
    api_resources = find_resources(resources, resource_type="google_project_service")
    declared = set()
    for r in api_resources:
        service = r["attrs"].get("service")
        if isinstance(service, str):
            declared.add(service)
        # Also accept for_each locals pattern (service may be a reference)
        for_each = r["attrs"].get("for_each")
        if isinstance(for_each, str) and "required_apis" in for_each:
            # The for_each pattern covers all required_apis via locals
            declared = REQUIRED_APIS  # trust the locals block
            break

    missing = REQUIRED_APIS - declared
    assert not missing, (
        f"Recipe 1: required APIs missing from google_project_service: "
        f"{sorted(missing)!r}. Add them to the `required_apis` local in "
        "foundations.tf."
    )


def test_no_api_has_disable_on_destroy_true(resources):
    """REJECT disable_on_destroy = true on any API resource.

    Disabling APIs on `tofu destroy` is highly disruptive and non-reversible
    at speed — it takes ~30s per API and may break other resources in the
    project that share the same API (e.g. Cloud Console UI, other stacks).
    """
    api_resources = find_resources(resources, resource_type="google_project_service")
    offenders = [
        r["name"]
        for r in api_resources
        if r["attrs"].get("disable_on_destroy") is True
    ]
    assert not offenders, (
        "Recipe 1: google_project_service resources have disable_on_destroy=true "
        f"which risks disruptive teardowns: {offenders!r}. Set to false."
    )


def test_required_apis_local_covers_all_required(parsed_hcl):
    """ACCEPT: if the stack uses a `for_each = local.required_apis` pattern,
    verify that the `required_apis` local set contains all required values.

    This test is the complement of test_all_required_apis_are_enabled for
    stacks that use a for_each pattern instead of per-API resource blocks.
    Skips gracefully if no `required_apis` local is declared.
    """
    locals_entries = parsed_hcl.get("locals", [])
    required_apis_local: set[str] | None = None
    for entry in locals_entries:
        if isinstance(entry, dict) and "required_apis" in entry:
            value = entry["required_apis"]
            if isinstance(value, (list, set)):
                required_apis_local = set(value)
            break

    if required_apis_local is None:
        pytest.skip("No required_apis local declared; skipping for_each pattern check.")

    missing = REQUIRED_APIS - required_apis_local
    assert not missing, (
        f"Recipe 1: local.required_apis is missing these required APIs: "
        f"{sorted(missing)!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Artifact Registry
# ─────────────────────────────────────────────────────────────────────────────


def test_artifact_registry_repo_exists(resources):
    """REJECT: no AR repo means Recipe 3 docker push and Recipe 4 Cloud Run
    deploy will fail. Catch early.
    """
    repos = find_resources(resources, resource_type="google_artifact_registry_repository")
    assert repos, (
        "Recipe 1: no google_artifact_registry_repository found in infra/gcp/. "
        "foundations.tf must declare a Docker AR repository."
    )


def test_artifact_registry_repo_format_is_docker(resources):
    """REJECT non-Docker format. Cloud Run pulls Docker images; a MAVEN or NPM
    repo would silently exist but be unusable for Recipe 3 image pushes.
    """
    repos = find_resources(resources, resource_type="google_artifact_registry_repository")
    assert repos, "no google_artifact_registry_repository at all"
    for repo in repos:
        fmt = repo["attrs"].get("format", "")
        assert isinstance(fmt, str) and fmt.upper() == "DOCKER", (
            f"Recipe 1: AR repository '{repo['name']}' format must be DOCKER, "
            f"got {fmt!r}."
        )


def test_artifact_registry_repo_id_is_sensible(resources):
    """ACCEPT: the repository_id is either a var reference or the default
    'agent-backend'. A wildly different name would break the convention that
    Recipe 4 uses to construct the full image URI.
    """
    repos = find_resources(resources, resource_type="google_artifact_registry_repository")
    assert repos, "no google_artifact_registry_repository at all"
    repo = repos[0]
    repo_id = repo["attrs"].get("repository_id", "")
    assert (
        repo_id == "agent-backend"
        or (isinstance(repo_id, str) and "artifact_registry_repo_id" in repo_id)
    ), (
        f"Recipe 1: repository_id should be 'agent-backend' or reference "
        f"var.artifact_registry_repo_id; got {repo_id!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Runtime service account
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_runtime_sa_exists(resources):
    """REJECT: no runtime SA means Cloud Run will run as the default Compute
    Engine SA (roles/editor) — a critical least-privilege violation.
    """
    sa_resources = find_resources(resources, resource_type="google_service_account")
    assert sa_resources, (
        "Recipe 1: no google_service_account found. foundations.tf must declare "
        "a dedicated backend runtime SA for Cloud Run."
    )


def test_backend_runtime_sa_account_id_contains_runtime(resources):
    """ACCEPT: the SA account_id includes 'runtime' so it's distinguishable
    from deployer or admin SAs in `gcloud iam service-accounts list`.
    """
    sa_resources = find_resources(resources, resource_type="google_service_account")
    runtime_sas = [
        r for r in sa_resources
        if "runtime" in r["name"] or (
            isinstance(r["attrs"].get("account_id"), str)
            and "runtime" in r["attrs"]["account_id"]
        )
    ]
    assert runtime_sas, (
        "Recipe 1: no service account with 'runtime' in its name or account_id. "
        f"Found SAs: {[r['name'] for r in sa_resources]!r}."
    )


def test_backend_runtime_sa_account_id_matches_convention(resources):
    """ACCEPT: the canonical account_id is 'agent-backend-runtime', matching
    the pattern documented in docs/recipes/gcp/01_foundations.md and
    mirroring 'agent-middleware-runtime' from infra/dev-tier/.
    """
    sa_resources = find_resources(resources, resource_type="google_service_account")
    matching = [
        r for r in sa_resources
        if r["attrs"].get("account_id") == "agent-backend-runtime"
        or (
            isinstance(r["attrs"].get("account_id"), str)
            and "backend" in r["attrs"]["account_id"]
            and "runtime" in r["attrs"]["account_id"]
        )
    ]
    assert matching, (
        "Recipe 1: expected a google_service_account with account_id "
        "'agent-backend-runtime' (or containing 'backend' and 'runtime'). "
        f"Declared account_ids: {[r['attrs'].get('account_id') for r in sa_resources]!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# IAM bindings for the runtime SA
# ─────────────────────────────────────────────────────────────────────────────


def _project_iam_members_for_sa(resources, sa_name_fragment: str) -> list[dict]:
    """Find google_project_iam_member resources whose member references the SA."""
    return [
        r for r in find_resources(resources, resource_type="google_project_iam_member")
        if sa_name_fragment in str(r["attrs"].get("member", ""))
    ]


def test_runtime_sa_has_log_writer_binding(resources):
    """ACCEPT: the runtime SA must be granted roles/logging.logWriter so Cloud
    Run structured logs appear in Cloud Logging with the correct JSON payload.

    Without this, logs appear under the default Compute Engine sink in text
    format only — the observability stack cannot parse them.
    """
    log_writers = [
        r for r in find_resources(resources, resource_type="google_project_iam_member")
        if r["attrs"].get("role") == "roles/logging.logWriter"
        and "backend_runtime" in str(r["attrs"].get("member", ""))
    ]
    assert log_writers, (
        "Recipe 1: no google_project_iam_member grants roles/logging.logWriter "
        "to the backend_runtime SA. Cloud Run structured logging will fail."
    )


def test_runtime_sa_has_metric_writer_binding(resources):
    """ACCEPT: roles/monitoring.metricWriter lets the runtime SA emit custom
    Cloud Monitoring metrics. Required by Recipe 7 alerting policies.
    """
    metric_writers = [
        r for r in find_resources(resources, resource_type="google_project_iam_member")
        if r["attrs"].get("role") == "roles/monitoring.metricWriter"
        and "backend_runtime" in str(r["attrs"].get("member", ""))
    ]
    assert metric_writers, (
        "Recipe 1: no google_project_iam_member grants roles/monitoring.metricWriter "
        "to the backend_runtime SA. Recipe 7 metric alerts will fail."
    )


def test_runtime_sa_ar_reader_binding_exists(resources):
    """ACCEPT: the runtime SA must have AR reader access so Cloud Run can pull
    the backend image from the Artifact Registry repo.

    Without this binding, Cloud Run deploy succeeds but container startup fails
    with `IMAGE_NOT_FOUND` (403 Forbidden from AR).
    """
    ar_readers = find_resources(
        resources, resource_type="google_artifact_registry_repository_iam_member"
    )
    runtime_readers = [
        r for r in ar_readers
        if r["attrs"].get("role") == "roles/artifactregistry.reader"
        and "backend_runtime" in str(r["attrs"].get("member", ""))
    ]
    assert runtime_readers, (
        "Recipe 1: no google_artifact_registry_repository_iam_member grants "
        "roles/artifactregistry.reader to the backend_runtime SA. Cloud Run "
        "will fail to pull images at Recipe 4 deploy."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Least-privilege enforcement — REJECT overly broad project roles.
# ─────────────────────────────────────────────────────────────────────────────


def test_no_forbidden_project_iam_roles_granted(resources):
    """REJECT roles/editor, roles/owner, and other broad project roles.

    The runtime SA needs only secretAccessor (per-secret, in secret-manager.tf),
    AR reader (per-repo, above), logWriter, and metricWriter. Any broader
    project-level role is a least-privilege violation that test_cross_cutting.py
    would also catch — we duplicate here for targeted diagnostics.
    """
    project_iam = find_resources(resources, resource_type="google_project_iam_member")
    offenders = [
        (r["name"], r["attrs"].get("role"))
        for r in project_iam
        if r["attrs"].get("role") in FORBIDDEN_PROJECT_ROLES
    ]
    assert not offenders, (
        "Recipe 1: forbidden project-level IAM roles detected. Tier A uses "
        "per-resource bindings for least privilege. Offenders: "
        f"{offenders!r}."
    )


def test_all_project_iam_roles_are_in_allowlist(resources):
    """ACCEPT: every google_project_iam_member role is in the least-privilege
    allowlist. A new role added outside the allowlist triggers this failure
    and requires an explicit review before merging.
    """
    project_iam = find_resources(resources, resource_type="google_project_iam_member")
    offenders = [
        (r["name"], r["attrs"].get("role"))
        for r in project_iam
        if r["attrs"].get("role") not in ALLOWED_PROJECT_ROLES
    ]
    assert not offenders, (
        "Recipe 1: google_project_iam_member roles outside the Tier A "
        f"least-privilege allowlist {sorted(ALLOWED_PROJECT_ROLES)!r}: "
        f"{offenders!r}. Add a justification comment and update the allowlist "
        "if the new role is intentional."
    )
