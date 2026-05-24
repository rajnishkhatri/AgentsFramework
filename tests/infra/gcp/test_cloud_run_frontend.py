"""tests/infra/gcp/test_cloud_run_frontend.py — Recipe 5 frontend Cloud Run tests.

Verifies the acceptance criteria for infra/gcp/cloud-run-frontend.tf:

  * google_cloud_run_v2_service.frontend named agent-frontend
  * min_instance_count = 0, max_instance_count = 10, timeout = 3600s
  * cpu_idle = true, startup_cpu_boost = true
  * MIDDLEWARE_URL wired to Recipe 4 backend URI
  * NEXT_PUBLIC_WORKOS_REDIRECT_URI wired to /api/auth/callback on this service
  * WORKOS_CLIENT_ID + ARCHITECTURE_PROFILE=v3 as plain env vars
  * Only WorkOS BFF secrets via secret_key_ref (no backend credentials)
  * Dedicated frontend_runtime SA (not default Compute SA)
  * allUsers public invoker binding (Tier A dev)
  * Probes target / on port 3000
  * frontend_url + frontend_workos_redirect_uri outputs exist

Failure paths first (TAP-4 / AGENTS.md §Testing Anti-Patterns).
"""

from __future__ import annotations

import pytest

from tests.infra._hcl_helpers import find_resources, get_one, unwrap_block, unwrap_blocks
from tests.infra.gcp.test_secret_manager import REQUIRED_SECRET_IDS


pytestmark = pytest.mark.infra_gcp

BACKEND_ONLY_SECRET_IDS = REQUIRED_SECRET_IDS - {"workos-api-key", "workos-cookie-password"}


def _frontend_service(resources):
    return get_one(
        find_resources(
            resources,
            resource_type="google_cloud_run_v2_service",
            name="frontend",
        ),
        "Recipe 5 expects exactly one frontend Cloud Run service",
    )


def _template(cr):
    template = unwrap_block(cr["attrs"].get("template"))
    assert template is not None, "Recipe 5: Cloud Run service missing template block"
    return template


def _container(template):
    container = unwrap_block(template.get("containers"))
    assert container is not None, "Recipe 5: template.containers block required"
    return container


def _resources_block(container):
    res = unwrap_block(container.get("resources"))
    assert res is not None, "Recipe 5: container.resources block required"
    return res


def _env_map(container) -> dict[str, dict]:
    env_blocks = container.get("env") or []
    if isinstance(env_blocks, dict):
        env_blocks = [env_blocks]
    return {str(entry.get("name", "")): entry for entry in env_blocks}


# ─────────────────────────────────────────────────────────────────────────────
# Existence — REJECT failures first
# ─────────────────────────────────────────────────────────────────────────────


def test_no_cloud_run_frontend_service_is_a_failure(resources):
    """REJECT: without a frontend Cloud Run service, Recipe 5 has nothing to deploy."""
    services = find_resources(resources, resource_type="google_cloud_run_v2_service")
    frontend = [s for s in services if s["name"] == "frontend"]
    assert frontend, (
        "Recipe 5: no google_cloud_run_v2_service.frontend found in infra/gcp/. "
        "cloud-run-frontend.tf must declare the Next.js frontend service."
    )


def test_frontend_service_named_agent_frontend(resources):
    """ACCEPT: service name must be agent-frontend for operator clarity."""
    cr = _frontend_service(resources)
    assert cr["attrs"].get("name") == "agent-frontend", (
        f"Recipe 5: service name must be 'agent-frontend', "
        f"got {cr['attrs'].get('name')!r}."
    )


def test_frontend_has_no_cloud_sql_volume(resources):
    """REJECT Cloud SQL volume on frontend — BFF talks to backend over HTTPS."""
    template = _template(_frontend_service(resources))
    volumes = unwrap_blocks(template.get("volumes"))
    cloudsql_volumes = [
        v for v in volumes if unwrap_block(v.get("cloud_sql_instance")) is not None
    ]
    assert not cloudsql_volumes, (
        "Recipe 5: frontend must not mount Cloud SQL; DATABASE_URL belongs on backend only."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scale-to-zero + SSE timeout
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_min_instance_count_is_zero(resources):
    """REJECT min_instance_count > 0 — Tier A cost constraint."""
    template = _template(_frontend_service(resources))
    scaling = unwrap_block(template.get("scaling"))
    assert scaling is not None, "Recipe 5: template.scaling block required"
    min_count = scaling.get("min_instance_count")
    assert min_count == 0 or (
        isinstance(min_count, str) and "frontend_min_instances" in min_count
    ), (
        "Recipe 5: scaling.min_instance_count must be 0 (or wire through "
        f"var.frontend_min_instances), got {min_count!r}."
    )


def test_frontend_request_timeout_is_3600s(resources):
    """REJECT timeout != 3600s — BFF SSE proxy routes need 1 hour."""
    template = _template(_frontend_service(resources))
    timeout = template.get("timeout")
    assert timeout in ("3600s", "3600.0s") or (
        isinstance(timeout, str) and "frontend_request_timeout_seconds" in timeout
    ), f"Recipe 5: template.timeout must be 3600s, got {timeout!r}."


def test_frontend_cpu_idle_enabled(resources):
    """ACCEPT: cpu_idle=true required for free-tier billing on min=0 services."""
    container = _container(_template(_frontend_service(resources)))
    res = _resources_block(container)
    assert res.get("cpu_idle") is True, (
        "Recipe 5: container.resources.cpu_idle must be true for scale-to-zero."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Env wiring — MIDDLEWARE_URL + WorkOS public config
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_middleware_url_wired_to_backend(resources):
    """ACCEPT: MIDDLEWARE_URL references Recipe 4 backend_combined URI."""
    envs = _env_map(_container(_template(_frontend_service(resources))))
    middleware = str(envs.get("MIDDLEWARE_URL", {}).get("value", ""))
    assert "backend_combined" in middleware, (
        f"Recipe 5: MIDDLEWARE_URL must reference backend_combined.uri, got {middleware!r}."
    )


def test_frontend_workos_redirect_uri_wired(resources):
    """ACCEPT: NEXT_PUBLIC_WORKOS_REDIRECT_URI ends with /api/auth/callback."""
    envs = _env_map(_container(_template(_frontend_service(resources))))
    redirect = str(envs.get("NEXT_PUBLIC_WORKOS_REDIRECT_URI", {}).get("value", ""))
    assert redirect.endswith("/api/auth/callback"), (
        f"Recipe 5: NEXT_PUBLIC_WORKOS_REDIRECT_URI must end with /api/auth/callback, "
        f"got {redirect!r}."
    )
    assert "frontend" in redirect, (
        "Recipe 5: redirect URI must reference the frontend service URI."
    )


def test_frontend_architecture_profile_is_v3(resources):
    """ACCEPT: ARCHITECTURE_PROFILE=v3 selects V3 adapter wiring."""
    envs = _env_map(_container(_template(_frontend_service(resources))))
    assert envs.get("ARCHITECTURE_PROFILE", {}).get("value") == "v3", (
        "Recipe 5: ARCHITECTURE_PROFILE must be 'v3'."
    )


def test_frontend_workos_client_id_is_plain_env(resources):
    """ACCEPT: WORKOS_CLIENT_ID is a public plain env var (not secret_key_ref)."""
    envs = _env_map(_container(_template(_frontend_service(resources))))
    entry = envs.get("WORKOS_CLIENT_ID", {})
    assert entry.get("value") is not None or "workos_client_id" in str(entry.get("value", "")), (
        "Recipe 5: WORKOS_CLIENT_ID must be a plain env var."
    )
    assert unwrap_block(entry.get("value_source")) is None, (
        "Recipe 5: WORKOS_CLIENT_ID must not use secret_key_ref."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Secrets — BFF-only, no backend credentials (FE-AP-18)
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_has_no_backend_secret_refs(resources):
    """REJECT backend-only secrets on frontend (DATABASE_URL, LLM keys, etc.)."""
    container = _container(_template(_frontend_service(resources)))
    env_blocks = container.get("env") or []
    if isinstance(env_blocks, dict):
        env_blocks = [env_blocks]

    backend_refs: set[str] = set()
    for env_entry in env_blocks:
        vs = unwrap_block(env_entry.get("value_source"))
        if vs is None:
            continue
        sk = unwrap_block(vs.get("secret_key_ref"))
        if sk is None:
            continue
        ref = str(sk.get("secret", ""))
        for sec_id in BACKEND_ONLY_SECRET_IDS:
            local_name = sec_id.replace("-", "_")
            if local_name in ref:
                backend_refs.add(sec_id)

    assert not backend_refs, (
        "Recipe 5 / FE-AP-18: frontend must not reference backend-only secrets "
        f"{sorted(backend_refs)!r}."
    )


def test_frontend_workos_secrets_wired(resources):
    """ACCEPT: WorkOS BFF secrets injected via secret_key_ref."""
    container = _container(_template(_frontend_service(resources)))
    env_blocks = container.get("env") or []
    if isinstance(env_blocks, dict):
        env_blocks = [env_blocks]

    secret_env_names = {
        env_entry.get("name")
        for env_entry in env_blocks
        if unwrap_block(env_entry.get("value_source")) is not None
    }
    assert secret_env_names == {"WORKOS_API_KEY", "WORKOS_COOKIE_PASSWORD"}, (
        "Recipe 5: frontend secret env vars must be exactly WORKOS_API_KEY and "
        f"WORKOS_COOKIE_PASSWORD, got {sorted(secret_env_names)!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Probes + service account + port
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_startup_probe_hits_root(resources):
    """ACCEPT: startup_probe.http_get.path = '/' (Next.js standalone root)."""
    container = _container(_template(_frontend_service(resources)))
    probe = unwrap_block(container.get("startup_probe"))
    assert probe is not None, "Recipe 5: startup_probe required"
    http_get = unwrap_block(probe.get("http_get"))
    assert http_get is not None, "Recipe 5: startup_probe.http_get required"
    assert http_get.get("path") == "/", (
        f"Recipe 5: startup_probe path must be /, got {http_get.get('path')!r}."
    )
    assert http_get.get("port") == 3000, (
        f"Recipe 5: startup_probe port must be 3000, got {http_get.get('port')!r}."
    )


def test_frontend_uses_dedicated_service_account(resources):
    """REJECT default Compute SA — least-privilege frontend_runtime required."""
    template = _template(_frontend_service(resources))
    sa = template.get("service_account")
    assert sa is not None, "Recipe 5: dedicated service_account required"
    assert isinstance(sa, str) and "google_service_account.frontend_runtime" in sa, (
        "Recipe 5: service_account must reference google_service_account.frontend_runtime."
    )


# ─────────────────────────────────────────────────────────────────────────────
# IAM — public invoker (Tier A dev)
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_public_invoker_binding_exists(resources):
    """ACCEPT: allUsers invoker binding for Tier A (auth at app layer)."""
    bindings = find_resources(
        resources, resource_type="google_cloud_run_v2_service_iam_binding"
    )
    frontend_bindings = [b for b in bindings if b["name"] == "frontend_public_invoker"]
    assert frontend_bindings, (
        "Recipe 5: google_cloud_run_v2_service_iam_binding.frontend_public_invoker "
        "must exist for Tier A public HTTPS access."
    )
    binding = frontend_bindings[0]
    assert binding["attrs"].get("role") == "roles/run.invoker"
    members = binding["attrs"].get("members") or []
    if isinstance(members, str):
        members = [members]
    assert "allUsers" in members, (
        f"Recipe 5: frontend invoker must include allUsers, got {members!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_url_output_exists(outputs):
    """ACCEPT: frontend_url output for WorkOS redirect gate + smoke tests."""
    assert "frontend_url" in outputs, (
        "Recipe 5: outputs.tf must declare frontend_url."
    )


def test_frontend_workos_redirect_uri_output_exists(outputs):
    """ACCEPT: frontend_workos_redirect_uri output for HUMAN_SETUP WorkOS step."""
    assert "frontend_workos_redirect_uri" in outputs, (
        "Recipe 5: outputs.tf must declare frontend_workos_redirect_uri."
    )
