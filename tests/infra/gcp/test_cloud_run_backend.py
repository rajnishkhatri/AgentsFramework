"""tests/infra/gcp/test_cloud_run_backend.py — Recipe 4 backend Cloud Run tests.

Verifies the acceptance criteria for infra/gcp/cloud-run-backend.tf:

  * google_cloud_run_v2_service.backend_combined named agent-backend-combined
  * min_instance_count = 0, max_instance_count = 10, timeout = 3600s
  * cpu_idle = true, startup_cpu_boost = true
  * Cloud SQL connector volume wired to Recipe 2 instance
  * GCS bucket env vars wired from Recipe 2 buckets
  * GCP_EXECUTION_ENV=cloudrun and AGENT_OFFLOAD_DIR set
  * /healthz startup + liveness probes
  * Dedicated backend_runtime SA (not default Compute SA)
  * allUsers public invoker binding (Tier A dev)
  * Every required secret referenced via secret_key_ref
  * backend_url output exists

Failure paths first (TAP-4 / AGENTS.md §Testing Anti-Patterns).
"""

from __future__ import annotations

import pytest

from tests.infra._hcl_helpers import find_resources, get_one, unwrap_block, unwrap_blocks
from tests.infra.gcp.test_secret_manager import FRONTEND_ONLY_SECRET_IDS, REQUIRED_SECRET_IDS


BACKEND_REQUIRED_SECRET_IDS = REQUIRED_SECRET_IDS - FRONTEND_ONLY_SECRET_IDS


pytestmark = pytest.mark.infra_gcp


def _backend_service(resources):
    return get_one(
        find_resources(
            resources,
            resource_type="google_cloud_run_v2_service",
            name="backend_combined",
        ),
        "Recipe 4 expects exactly one backend_combined Cloud Run service",
    )


def _template(cr):
    template = unwrap_block(cr["attrs"].get("template"))
    assert template is not None, "Recipe 4: Cloud Run service missing template block"
    return template


def _container(template):
    container = unwrap_block(template.get("containers"))
    assert container is not None, "Recipe 4: template.containers block required"
    return container


def _resources_block(container):
    res = unwrap_block(container.get("resources"))
    assert res is not None, "Recipe 4: container.resources block required"
    return res


def _env_map(container) -> dict[str, dict]:
    env_blocks = container.get("env") or []
    if isinstance(env_blocks, dict):
        env_blocks = [env_blocks]
    return {str(entry.get("name", "")): entry for entry in env_blocks}


# ─────────────────────────────────────────────────────────────────────────────
# Existence — REJECT failures first
# ─────────────────────────────────────────────────────────────────────────────


def test_no_cloud_run_backend_service_is_a_failure(resources):
    """REJECT: without a Cloud Run service, Recipe 4 has nothing to deploy."""
    services = find_resources(resources, resource_type="google_cloud_run_v2_service")
    assert services, (
        "Recipe 4: no google_cloud_run_v2_service found in infra/gcp/. "
        "cloud-run-backend.tf must declare the combined backend service."
    )


def test_backend_service_named_agent_backend_combined(resources):
    """ACCEPT: service name must be agent-backend-combined for operator clarity."""
    cr = _backend_service(resources)
    assert cr["attrs"].get("name") == "agent-backend-combined", (
        f"Recipe 4: service name must be 'agent-backend-combined', "
        f"got {cr['attrs'].get('name')!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scale-to-zero + SSE timeout
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_min_instance_count_is_zero(resources):
    """REJECT min_instance_count > 0 — Tier A cost constraint."""
    template = _template(_backend_service(resources))
    scaling = unwrap_block(template.get("scaling"))
    assert scaling is not None, "Recipe 4: template.scaling block required"
    min_count = scaling.get("min_instance_count")
    assert min_count == 0 or (
        isinstance(min_count, str) and "backend_min_instances" in min_count
    ), (
        "Recipe 4: scaling.min_instance_count must be 0 (or wire through "
        f"var.backend_min_instances), got {min_count!r}."
    )


def test_backend_max_instance_count_is_ten(resources):
    """ACCEPT: max_instance_count capped at 10 for predictable cost."""
    template = _template(_backend_service(resources))
    scaling = unwrap_block(template.get("scaling"))
    assert scaling is not None
    max_count = scaling.get("max_instance_count")
    assert max_count == 10 or (
        isinstance(max_count, str) and "backend_max_instances" in max_count
    ), f"Recipe 4: max_instance_count should be 10, got {max_count!r}."


def test_backend_request_timeout_is_3600s(resources):
    """REJECT timeout != 3600s — SSE + long ReAct runs need 1 hour."""
    template = _template(_backend_service(resources))
    timeout = template.get("timeout")
    assert timeout in ("3600s", "3600.0s") or (
        isinstance(timeout, str) and "backend_request_timeout_seconds" in timeout
    ), (
        f"Recipe 4: template.timeout must be 3600s, got {timeout!r}."
    )


def test_backend_startup_cpu_boost_enabled(resources):
    """ACCEPT: startup_cpu_boost=true for cold-start latency."""
    container = _container(_template(_backend_service(resources)))
    res = _resources_block(container)
    assert res.get("startup_cpu_boost") is True, (
        "Recipe 4: container.resources.startup_cpu_boost must be true."
    )


def test_backend_cpu_idle_enabled(resources):
    """ACCEPT: cpu_idle=true required for free-tier billing on min=0 services."""
    container = _container(_template(_backend_service(resources)))
    res = _resources_block(container)
    assert res.get("cpu_idle") is True, (
        "Recipe 4: container.resources.cpu_idle must be true for scale-to-zero."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cloud SQL connector
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_cloud_sql_volume_wired(resources):
    """ACCEPT: Cloud SQL built-in connector volume references Recipe 2 instance."""
    template = _template(_backend_service(resources))
    volumes = unwrap_blocks(template.get("volumes"))
    assert volumes, "Recipe 4: template.volumes block required for Cloud SQL connector"
    cloudsql_volumes = [
        v for v in volumes
        if unwrap_block(v.get("cloud_sql_instance")) is not None
    ]
    assert cloudsql_volumes, (
        "Recipe 4: no cloud_sql_instance volume found. Cloud Run cannot "
        "connect to Cloud SQL without the built-in connector."
    )
    csi = unwrap_block(cloudsql_volumes[0].get("cloud_sql_instance"))
    instances = csi.get("instances") or []
    assert instances, "Recipe 4: cloud_sql_instance.instances must be non-empty"
    assert any(
        "google_sql_database_instance" in str(inst) for inst in instances
    ), (
        "Recipe 4: cloud_sql_instance must reference "
        "google_sql_database_instance.main.connection_name."
    )


def test_backend_cloud_sql_volume_mounted(resources):
    """ACCEPT: container mounts the Cloud SQL volume at /cloudsql."""
    container = _container(_template(_backend_service(resources)))
    mounts = unwrap_blocks(container.get("volume_mounts"))
    cloudsql_mounts = [m for m in mounts if m.get("name") == "cloudsql"]
    assert cloudsql_mounts, "Recipe 4: volume_mounts must include cloudsql"
    assert cloudsql_mounts[0].get("mount_path") == "/cloudsql", (
        "Recipe 4: Cloud SQL socket directory must mount at /cloudsql."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Env wiring — GCP adapters + bucket names
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_gcp_execution_env_is_cloudrun(resources):
    """ACCEPT: GCP_EXECUTION_ENV=cloudrun triggers GCP adapter wiring."""
    envs = _env_map(_container(_template(_backend_service(resources))))
    assert envs.get("GCP_EXECUTION_ENV", {}).get("value") == "cloudrun", (
        "Recipe 4: GCP_EXECUTION_ENV must be 'cloudrun'."
    )


def test_backend_gcs_bucket_env_vars_wired(resources):
    """ACCEPT: GCS_FACTS_BUCKET and GCS_TRACES_BUCKET reference Recipe 2 buckets."""
    envs = _env_map(_container(_template(_backend_service(resources))))
    facts = str(envs.get("GCS_FACTS_BUCKET", {}).get("value", ""))
    traces = str(envs.get("GCS_TRACES_BUCKET", {}).get("value", ""))
    assert "agent_facts" in facts, (
        f"Recipe 4: GCS_FACTS_BUCKET must reference agent_facts bucket, got {facts!r}."
    )
    assert "trust_traces" in traces, (
        f"Recipe 4: GCS_TRACES_BUCKET must reference trust_traces bucket, got {traces!r}."
    )


def test_backend_offload_dir_set(resources):
    """ACCEPT: AGENT_OFFLOAD_DIR points at ephemeral container disk."""
    envs = _env_map(_container(_template(_backend_service(resources))))
    assert envs.get("AGENT_OFFLOAD_DIR", {}).get("value") == "/tmp/agent_offload", (
        "Recipe 4: AGENT_OFFLOAD_DIR must be /tmp/agent_offload (no Filestore at Tier A)."
    )


def test_backend_blackbox_relay_mode_in_process(resources):
    """ACCEPT: BLACKBOX_RELAY_MODE=in_process so the relay runs inside app_prod.

    Without this the production lifespan has no relay to start and BlackBox
    recordings never reach Langfuse (blackbox_langfuse_gcp_deploy.plan §Blocker 1).
    """
    envs = _env_map(_container(_template(_backend_service(resources))))
    assert envs.get("BLACKBOX_RELAY_MODE", {}).get("value") == "in_process", (
        "Recipe 4: BLACKBOX_RELAY_MODE must be 'in_process' for Tier A."
    )


def test_backend_blackbox_storage_dir_aligned_with_offload(resources):
    """REJECT a relay storage path that does not match where the recorder writes.

    BlackBoxRecorder writes to {AGENT_OFFLOAD_DIR}/black_box_recordings; the
    relay tails BLACKBOX_STORAGE_DIR. A mismatch means the relay polls an empty
    directory (blackbox_langfuse_gcp_deploy.plan §Blocker 2).
    """
    envs = _env_map(_container(_template(_backend_service(resources))))
    offload = str(envs.get("AGENT_OFFLOAD_DIR", {}).get("value", ""))
    storage = str(envs.get("BLACKBOX_STORAGE_DIR", {}).get("value", ""))
    assert storage == "/tmp/agent_offload/black_box_recordings", (
        f"Recipe 4: BLACKBOX_STORAGE_DIR must be "
        f"/tmp/agent_offload/black_box_recordings, got {storage!r}."
    )
    assert offload and storage.startswith(offload.rstrip("/") + "/"), (
        f"Recipe 4: BLACKBOX_STORAGE_DIR ({storage!r}) must be nested under "
        f"AGENT_OFFLOAD_DIR ({offload!r}) so relay and recorder agree."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Probes + service account
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_startup_probe_hits_healthz(resources):
    """ACCEPT: startup_probe.http_get.path = '/healthz' (pre-auth)."""
    container = _container(_template(_backend_service(resources)))
    probe = unwrap_block(container.get("startup_probe"))
    assert probe is not None, "Recipe 4: startup_probe required"
    http_get = unwrap_block(probe.get("http_get"))
    assert http_get is not None, "Recipe 4: startup_probe.http_get required"
    assert http_get.get("path") == "/healthz", (
        f"Recipe 4: startup_probe path must be /healthz, got {http_get.get('path')!r}."
    )


def test_backend_uses_dedicated_service_account(resources):
    """REJECT default Compute SA — least-privilege backend_runtime required."""
    template = _template(_backend_service(resources))
    sa = template.get("service_account")
    assert sa is not None, "Recipe 4: dedicated service_account required"
    assert isinstance(sa, str) and "google_service_account.backend_runtime" in sa, (
        "Recipe 4: service_account must reference google_service_account.backend_runtime."
    )


def test_backend_references_every_required_secret(resources):
    """ACCEPT: every Secret Manager shell is wired via secret_key_ref."""
    container = _container(_template(_backend_service(resources)))
    env_blocks = container.get("env") or []
    if isinstance(env_blocks, dict):
        env_blocks = [env_blocks]

    secret_refs: set[str] = set()
    for env_entry in env_blocks:
        vs = unwrap_block(env_entry.get("value_source"))
        if vs is None:
            continue
        sk = unwrap_block(vs.get("secret_key_ref"))
        if sk is None:
            continue
        ref = str(sk.get("secret", ""))
        for sec_id in BACKEND_REQUIRED_SECRET_IDS:
            local_name = sec_id.replace("-", "_")
            if local_name in ref:
                secret_refs.add(sec_id)

    missing = BACKEND_REQUIRED_SECRET_IDS - secret_refs
    assert not missing, (
        "Recipe 4: Cloud Run service missing secret_key_ref wiring for "
        f"{sorted(missing)!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# IAM — public invoker (Tier A dev)
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_public_invoker_binding_exists(resources):
    """ACCEPT: allUsers invoker binding for Tier A (auth at app layer)."""
    bindings = find_resources(
        resources, resource_type="google_cloud_run_v2_service_iam_binding"
    )
    backend_bindings = [b for b in bindings if b["name"] == "backend_public_invoker"]
    assert backend_bindings, (
        "Recipe 4: google_cloud_run_v2_service_iam_binding.backend_public_invoker "
        "must exist for Tier A public HTTPS access."
    )
    binding = backend_bindings[0]
    assert binding["attrs"].get("role") == "roles/run.invoker"
    members = binding["attrs"].get("members") or []
    if isinstance(members, str):
        members = [members]
    assert "allUsers" in members, (
        f"Recipe 4: backend invoker must include allUsers, got {members!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_url_output_exists(outputs):
    """ACCEPT: backend_url output for Recipe 5 MIDDLEWARE_URL wiring."""
    assert "backend_url" in outputs, (
        "Recipe 4: outputs.tf must declare backend_url for downstream recipes."
    )
