"""tests/infra/gcp/test_meta.py — Recipe 6 meta ring tests.

Verifies the acceptance criteria for infra/gcp/meta.tf:

  * enable_meta_ring defaults to false (Tier A skip-by-default).
  * When declared, google_cloud_run_v2_job.meta_eval named agent-meta-eval.
  * Job reuses backend_image and runs `python -m meta.run_eval`.
  * Job env: GCP_EXECUTION_ENV, GCS_TRACES_BUCKET, OPENAI_API_KEY only.
  * Job must NOT reference backend-only secrets (DATABASE_URL, agent-facts, etc.).
  * Dedicated meta_runtime + meta_scheduler service accounts.
  * meta_runtime gets objectViewer + objectCreator on trust-traces only.
  * google_cloud_scheduler_job with oauth_token invoker SA.
  * Scheduler IAM: roles/run.invoker on the job for scheduler SA.

Failure paths first (TAP-4 / AGENTS.md §Testing Anti-Patterns).
"""

from __future__ import annotations

import pytest

from tests.infra._hcl_helpers import find_resources, get_one, unwrap_block
from tests.infra.gcp.test_secret_manager import FRONTEND_ONLY_SECRET_IDS, REQUIRED_SECRET_IDS


pytestmark = pytest.mark.infra_gcp

META_JOB_NAME = "agent-meta-eval"
BACKEND_ONLY_SECRET_IDS = (REQUIRED_SECRET_IDS - FRONTEND_ONLY_SECRET_IDS) - {"openai-api-key"}


def _meta_jobs(resources):
    return find_resources(resources, resource_type="google_cloud_run_v2_job", name="meta_eval")


def _meta_job_template(resources):
    job = get_one(_meta_jobs(resources), "Recipe 6 expects exactly one meta_eval Cloud Run Job block")
    template = unwrap_block(job["attrs"].get("template"))
    assert template is not None, "Recipe 6: Cloud Run Job missing template block"
    inner = unwrap_block(template.get("template"))
    assert inner is not None, "Recipe 6: Cloud Run Job missing template.template block"
    return inner


def _meta_container(resources):
    template = _meta_job_template(resources)
    container = unwrap_block(template.get("containers"))
    assert container is not None, "Recipe 6: Job template.containers block required"
    return container


def _meta_env_map(container) -> dict[str, dict]:
    env_blocks = container.get("env") or []
    if isinstance(env_blocks, dict):
        env_blocks = [env_blocks]
    return {str(entry.get("name", "")): entry for entry in env_blocks}


# ─────────────────────────────────────────────────────────────────────────────
# Opt-in gate — REJECT failures first
# ─────────────────────────────────────────────────────────────────────────────


def test_enable_meta_ring_defaults_false(variables):
    """REJECT: meta ring enabled by default would add scheduler charges and
    nightly LLM judge spend to every Tier A deploy."""
    attrs = variables.get("enable_meta_ring", {})
    assert attrs.get("default") is False, (
        "Recipe 6 Tier A: enable_meta_ring must default to false."
    )


def test_meta_job_has_no_database_url_secret(resources):
    """REJECT: meta job must not receive DATABASE_URL — offline eval reads GCS,
    not Postgres checkpoints."""
    jobs = _meta_jobs(resources)
    if not jobs:
        pytest.skip("meta ring disabled in HCL (count=0 pattern still parses block)")
    container = _meta_container(resources)
    env_map = _meta_env_map(container)
    for forbidden in ("DATABASE_URL", "AGENT_FACTS_SECRET", "WORKOS_API_KEY"):
        assert forbidden not in env_map, (
            f"Recipe 6: meta job must not inject {forbidden}; "
            "meta ring is read-only on GCS plus judge LLM key."
        )


def test_meta_job_secret_refs_are_openai_only(resources):
    """REJECT: meta job secret_key_ref must be limited to openai-api-key."""
    jobs = _meta_jobs(resources)
    if not jobs:
        pytest.skip("meta ring job block absent")
    container = _meta_container(resources)
    env_map = _meta_env_map(container)
    for env_name, env in env_map.items():
        value_source = env.get("value_source")
        if not value_source:
            continue
        secret_ref = unwrap_block(value_source).get("secret_key_ref")
        if not secret_ref:
            continue
        secret_id = str(unwrap_block(secret_ref).get("secret", ""))
        assert "openai_api_key" in secret_id or secret_id == "openai-api-key", (
            f"Recipe 6: meta job env {env_name!r} references unexpected secret {secret_id!r}."
        )


def test_meta_runtime_not_granted_agent_facts_bucket(resources):
    """REJECT: meta SA must not receive IAM on agent-facts bucket."""
    meta_members = {
        iam["attrs"].get("member")
        for iam in find_resources(resources, resource_type="google_storage_bucket_iam_member")
        if "meta" in iam["name"]
    }
    for iam in find_resources(resources, resource_type="google_storage_bucket_iam_member"):
        if "meta" not in iam["name"]:
            continue
        bucket = str(iam["attrs"].get("bucket", ""))
        assert "agent-facts" not in bucket, (
            f"Recipe 6: meta IAM binding {iam['name']} must not target agent-facts bucket."
        )
    assert meta_members, "Recipe 6: expected meta_storage bucket IAM bindings."


# ─────────────────────────────────────────────────────────────────────────────
# Existence + shape — ACCEPT
# ─────────────────────────────────────────────────────────────────────────────


def test_meta_cloud_run_job_declared(resources):
    """ACCEPT: Recipe 6 declares a Cloud Run Job for meta/run_eval.py."""
    jobs = _meta_jobs(resources)
    assert jobs, (
        "Recipe 6: google_cloud_run_v2_job.meta_eval must be declared in meta.tf."
    )


def test_meta_job_name(resources):
    """ACCEPT: job Cloud Run name is agent-meta-eval."""
    job = get_one(_meta_jobs(resources), "missing meta_eval job")
    assert job["attrs"].get("name") == META_JOB_NAME


def test_meta_job_uses_backend_image(resources):
    """ACCEPT: job reuses the Recipe 3/4 backend image (no separate Dockerfile)."""
    container = _meta_container(resources)
    image = str(container.get("image", ""))
    assert "backend_image" in image or "var.backend_image" in image, (
        f"Recipe 6: meta job must use var.backend_image; got {image!r}."
    )


def test_meta_job_command_and_args(resources):
    """ACCEPT: job runs python -m meta.run_eval with golden-set and output URIs."""
    container = _meta_container(resources)
    command = container.get("command") or []
    if isinstance(command, str):
        command = [command]
    assert command == ["python", "-m", "meta.run_eval"], (
        f"Recipe 6: job command must invoke meta.run_eval module; got {command!r}."
    )
    args = container.get("args") or []
    if isinstance(args, str):
        args = [args]
    flattened = " ".join(str(a) for a in args)
    assert "--golden-set" in flattened and "--output" in flattened, (
        f"Recipe 6: job args must include --golden-set and --output; got {args!r}."
    )
    assert "gs://" in flattened or "trust_traces" in flattened or "meta_golden_set_uri" in flattened, (
        "Recipe 6: golden-set and output args must reference the trust-traces bucket."
    )


def test_meta_job_dedicated_service_account(resources):
    """ACCEPT: job uses dedicated meta_runtime SA, not backend_runtime."""
    template = _meta_job_template(resources)
    sa = str(template.get("service_account", ""))
    assert "meta_runtime" in sa, (
        f"Recipe 6: job must use google_service_account.meta_runtime; got {sa!r}."
    )
    assert "backend_runtime" not in sa


def test_meta_job_required_env_vars(resources):
    """ACCEPT: job sets GCP_EXECUTION_ENV and GCS_TRACES_BUCKET."""
    env_map = _meta_env_map(_meta_container(resources))
    assert env_map.get("GCP_EXECUTION_ENV", {}).get("value") == "cloudrun"
    traces_val = str(env_map.get("GCS_TRACES_BUCKET", {}).get("value", ""))
    assert "trust_traces" in traces_val, (
        "Recipe 6: GCS_TRACES_BUCKET must reference google_storage_bucket.trust_traces."
    )


def test_meta_scheduler_job_declared(resources):
    """ACCEPT: Cloud Scheduler job triggers the meta Cloud Run Job."""
    schedulers = find_resources(
        resources,
        resource_type="google_cloud_scheduler_job",
        name="meta_eval",
    )
    assert schedulers, "Recipe 6: google_cloud_scheduler_job.meta_eval required."


def test_meta_scheduler_uses_oauth_token(resources):
    """ACCEPT: scheduler POST uses oauth_token with meta_scheduler SA."""
    scheduler = get_one(
        find_resources(resources, resource_type="google_cloud_scheduler_job", name="meta_eval"),
        "missing scheduler",
    )
    target = unwrap_block(scheduler["attrs"].get("http_target"))
    assert target is not None
    oauth = unwrap_block(target.get("oauth_token"))
    assert oauth is not None, "Recipe 6: scheduler http_target.oauth_token required."
    sa = str(oauth.get("service_account_email", ""))
    assert "meta_scheduler" in sa


def test_meta_scheduler_invoker_iam(resources):
    """ACCEPT: scheduler SA has roles/run.invoker on the Cloud Run Job."""
    bindings = find_resources(
        resources,
        resource_type="google_cloud_run_v2_job_iam_member",
        name="meta_scheduler_invoker",
    )
    assert bindings, "Recipe 6: google_cloud_run_v2_job_iam_member.meta_scheduler_invoker required."
    binding = bindings[0]["attrs"]
    assert binding.get("role") == "roles/run.invoker"
    assert "meta_scheduler" in str(binding.get("member", ""))


def test_meta_runtime_trust_traces_iam(resources):
    """ACCEPT: meta_runtime gets objectViewer + objectCreator on trust-traces."""
    meta_iam = [
        iam for iam in find_resources(resources, resource_type="google_storage_bucket_iam_member")
        if "meta" in iam["name"] and "trust_traces" in iam["name"]
    ]
    roles = {iam["attrs"].get("role") for iam in meta_iam}
    assert "roles/storage.objectViewer" in roles
    assert "roles/storage.objectCreator" in roles


def test_meta_outputs_declared(outputs):
    """ACCEPT: outputs expose meta_ring_enabled and URIs for operator smoke checks."""
    for name in ("meta_ring_enabled", "meta_job_name", "meta_golden_set_uri", "meta_report_uri"):
        assert name in outputs, f"Recipe 6: output {name!r} must be declared in outputs.tf."
