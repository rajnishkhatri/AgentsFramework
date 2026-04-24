"""tests/infra/test_cloud_run.py — Sprint 2 §S2.1.1 acceptance tests.

Story under test (verbatim from `docs/plan/frontend/SPRINT_BOARD.md`):

  > S2.1.1 — As a DevOps engineer, I want `infra/dev-tier/cloud-run.tf` to
  > provision Cloud Run service `agent-middleware` with `min=0`, 1 vCPU /
  > 2 GB, timeout=3600s, startup CPU boost, so that the middleware runs on
  > GCP free tier.

Failure paths first (TAP-4): every assertion below was written as the
**negation** of the acceptance criterion, then once the failing test was
seen it was flipped to assert the positive shape. The ordering preserves
that structure — denial-style assertions (e.g. "min_instance_count is NOT
> 0") precede acceptance-style assertions in this file so a careless
author can't slip a regression past one without the other.
"""

from __future__ import annotations

import pytest

from tests.infra._hcl_helpers import (
    find_resources,
    get_one,
    unwrap_block,
    unwrap_blocks,
)


pytestmark = pytest.mark.infra


# ─────────────────────────────────────────────────────────────────────────────
# Existence — the resource MUST be declared somewhere in infra/dev-tier/.
# ─────────────────────────────────────────────────────────────────────────────


def test_cloud_run_service_exists(resources):
    """Sprint 2 §S2.1.1 acceptance: a Cloud Run v2 service named
    `agent-middleware` must be declared.

    Failure-path framing: this test fails 'red' when nobody has authored
    cloud-run.tf yet, which is the canonical TDD entry point.
    """
    services = find_resources(
        resources, resource_type="google_cloud_run_v2_service"
    )
    assert services, (
        "Sprint 2 §S2.1.1: no `google_cloud_run_v2_service` resource found "
        "in infra/dev-tier/. The middleware Cloud Run service must be "
        "declared (suggested filename: cloud-run.tf)."
    )


def test_cloud_run_service_named_agent_middleware(resources):
    """The acceptance criterion names the service `agent-middleware`
    explicitly. A Tofu rename here would silently break Cloud Run URL
    inputs to Cloudflare Pages (the BFF computes the upstream URL from
    this name)."""
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )
    assert cr["attrs"].get("name") == "agent-middleware", (
        f"Sprint 2 §S2.1.1: service name must be 'agent-middleware', "
        f"got {cr['attrs'].get('name')!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scale-to-zero — REJECTION: min_instance_count > 0 is forbidden.
# (Cost: violating this leaks billable CPU-seconds 24/7.)
# ─────────────────────────────────────────────────────────────────────────────


def test_cloud_run_min_instance_count_is_zero(resources):
    """REJECT min_instance_count > 0.

    Sprint 2 §S2.1.1: 'min=0' is a hard acceptance criterion (free-tier
    scale-to-zero). The variable `middleware_min_instances` carries a
    Tofu validation that enforces 0; this test enforces that the resource
    actually wires that variable through (or hardcodes the literal).

    Combined cost-blast-radius if missed: ~$5-30/month per always-on
    instance. The Stage A budget is the entire monthly cost — a single
    leaked instance doubles it.
    """
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )

    # template.scaling.min_instance_count — python-hcl2 returns blocks
    # as lists; we walk them defensively.
    template = cr["attrs"].get("template")
    assert template is not None, (
        "Sprint 2 §S2.1.1: Cloud Run v2 service must have a `template` "
        "block; CR v2 requires it."
    )
    template_dict = template[0] if isinstance(template, list) else template

    scaling = template_dict.get("scaling")
    assert scaling is not None, (
        "Sprint 2 §S2.1.1: `template.scaling` block must be present so "
        "min_instance_count can be set to 0."
    )
    scaling_dict = scaling[0] if isinstance(scaling, list) else scaling

    min_count = scaling_dict.get("min_instance_count")
    # Literal 0 OR a Tofu interpolation that resolves to var.middleware_min_instances
    # (which has its own validation enforcing 0). Both satisfy the contract.
    assert min_count == 0 or (
        isinstance(min_count, str) and "middleware_min_instances" in min_count
    ), (
        "Sprint 2 §S2.1.1: scaling.min_instance_count must be 0 (or wire "
        f"through var.middleware_min_instances), got {min_count!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sizing — 1 vCPU / 2 GB / 3600s timeout / startup CPU boost.
# ─────────────────────────────────────────────────────────────────────────────


def _container(cr_resource):
    template = unwrap_block(cr_resource["attrs"].get("template"))
    assert template is not None, (
        "Sprint 2 §S2.1.1: Cloud Run v2 service must have a `template` block."
    )
    container = unwrap_block(template.get("containers"))
    assert container is not None, "template.containers block required"
    return container


def _resources_block(container_dict):
    res = unwrap_block(container_dict.get("resources"))
    assert res is not None, (
        "Sprint 2 §S2.1.1: container.resources block required (cpu/memory limits)."
    )
    return res


def test_cloud_run_cpu_is_1000m(resources):
    """REJECT cpu != '1' / '1000m'. Sprint 2 §S2.1.1: 1 vCPU."""
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )
    res = _resources_block(_container(cr))
    limits = res.get("limits") or {}
    cpu = limits.get("cpu")
    assert cpu in ("1000m", "1") or (
        isinstance(cpu, str) and "middleware_cpu" in cpu
    ), f"Sprint 2 §S2.1.1: cpu must be 1 vCPU, got {cpu!r}."


def test_cloud_run_memory_is_2gi(resources):
    """REJECT memory != '2Gi'. Sprint 2 §S2.1.1: 2 GB RAM."""
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )
    res = _resources_block(_container(cr))
    limits = res.get("limits") or {}
    mem = limits.get("memory")
    assert mem in ("2Gi", "2048Mi") or (
        isinstance(mem, str) and "middleware_memory" in mem
    ), f"Sprint 2 §S2.1.1: memory must be 2 GB, got {mem!r}."


def test_cloud_run_request_timeout_is_3600s(resources):
    """REJECT timeout != 3600s. Sprint 2 §S2.1.1: long ReAct runs need 1 hr."""
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )
    template = cr["attrs"]["template"]
    template_dict = template[0] if isinstance(template, list) else template
    timeout = template_dict.get("timeout")
    # GCP CR v2 expects a duration string like "3600s"; we accept the literal
    # or a var ref to the validated input.
    assert timeout in ("3600s", "3600.0s") or (
        isinstance(timeout, str)
        and "middleware_request_timeout" in timeout
    ), (
        f"Sprint 2 §S2.1.1: template.timeout must be 3600s for long ReAct "
        f"runs, got {timeout!r}."
    )


def test_cloud_run_startup_cpu_boost_enabled(resources):
    """ACCEPT startup_cpu_boost=true. Sprint 2 §S2.1.1 DoD: 'cold start
    <200ms with startup CPU boost'.

    A common mis-author is `cpu_idle = true` (which is *also* needed for
    free-tier billing on min=0 services) without `startup_cpu_boost`. We
    assert the latter explicitly because cold-start latency is the user-
    visible regression indicator.
    """
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )
    res = _resources_block(_container(cr))
    boost = res.get("startup_cpu_boost")
    assert boost is True, (
        "Sprint 2 §S2.1.1: container.resources.startup_cpu_boost must be "
        f"true so cold starts stay <200ms, got {boost!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# /healthz probe — Sprint 2 §S2.1.1 DoD: `/healthz returns 200`.
# ─────────────────────────────────────────────────────────────────────────────


def test_cloud_run_startup_probe_hits_healthz(resources):
    """ACCEPT startup_probe.http_get.path = '/healthz'.

    The middleware FastAPI app exposes /healthz pre-auth (see
    `middleware/server.py::healthz`). Routing the startup probe through
    a different path silently bypasses the readiness contract Cloud Run
    relies on for cold-start gating.
    """
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )
    container = _container(cr)
    probe = container.get("startup_probe")
    assert probe is not None, (
        "Sprint 2 §S2.1.1 DoD: startup_probe required (drives the "
        "<200ms cold-start guarantee)."
    )
    probe_dict = probe[0] if isinstance(probe, list) else probe
    http_get = probe_dict.get("http_get")
    assert http_get is not None, (
        "Sprint 2 §S2.1.1: startup_probe.http_get block required."
    )
    http_get_dict = http_get[0] if isinstance(http_get, list) else http_get
    assert http_get_dict.get("path") == "/healthz", (
        f"Sprint 2 §S2.1.1: startup_probe path must be '/healthz' "
        f"(matches middleware/server.py route), got "
        f"{http_get_dict.get('path')!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Service account — REJECT default Compute Engine SA.
# (Cross-cutting: Sprint 2 §S2.1.4 requires a least-privilege SA so Secret
# Manager IAM bindings are scoped — the default CE SA has roles/editor.)
# ─────────────────────────────────────────────────────────────────────────────


def test_cloud_run_uses_dedicated_service_account(resources):
    """REJECT missing/default service_account. Sprint 2 §S2.1.4 DoD: 'Cloud
    Run accesses [Secret Manager] via IAM role'. That requires a dedicated
    SA so `roles/secretmanager.secretAccessor` is granted to the right
    identity, not project-wide via the default Compute Engine SA.
    """
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )
    template = cr["attrs"]["template"]
    template_dict = template[0] if isinstance(template, list) else template
    sa = template_dict.get("service_account")
    assert sa is not None, (
        "Sprint 2 §S2.1.4 DoD: a dedicated service_account must be wired "
        "(default Compute Engine SA has too-broad roles/editor)."
    )
    # Should reference our own google_service_account resource, not a literal.
    assert isinstance(sa, str) and "google_service_account" in sa, (
        "Sprint 2 §S2.1.4: service_account should reference a "
        "google_service_account.<name>.email resource, got literal "
        f"{sa!r}."
    )


def test_dedicated_runtime_service_account_exists(resources):
    """The SA the Cloud Run wiring references must exist as a managed
    resource in this stack (not a data lookup of a pre-existing SA — that
    would scatter ownership)."""
    sa_resources = find_resources(
        resources, resource_type="google_service_account"
    )
    assert sa_resources, (
        "Sprint 2 §S2.1.4: at least one google_service_account resource "
        "(the Cloud Run runtime identity) must be declared."
    )
    runtime_sas = [
        r
        for r in sa_resources
        if "middleware" in r["name"] or "runtime" in r["name"]
    ]
    assert runtime_sas, (
        "Sprint 2 §S2.1.4: a service account named after the middleware "
        "runtime is expected (e.g. middleware_runtime); got "
        f"{[r['name'] for r in sa_resources]!r}."
    )
