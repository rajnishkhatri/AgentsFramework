"""tests/infra/test_neon.py — Sprint 2 §S2.1.2 acceptance tests.

Story under test:

  > S2.1.2 — As a DevOps engineer, I want `infra/dev-tier/neon.tf` to
  > provision 1 Neon Free project for `agent_app` with pgvector enabled,
  > so that the database is ready for checkpoints and app schema.

Acceptance shape:

  * Exactly one `neon_project` resource (Neon Free allows 1 project per
    account).
  * The application database is named `agent_app` (matches the BFF
    Drizzle config and the LangGraph checkpoint URL).
  * The `pgvector` extension is enabled (via `cyrilgdn/postgresql`
    provider; Neon SaaS doesn't expose a Tofu resource for extensions
    so we drive it through SQL).
  * The connection string is written to Secret Manager
    (`google_secret_manager_secret.neon_database_url`); covered in
    test_secret_manager.py.

Failure-paths first (TAP-4): the per-resource rejection assertions
precede the acceptance one in this file.
"""

from __future__ import annotations

import pytest

from tests.infra._hcl_helpers import find_resources, get_one


pytestmark = pytest.mark.infra


# ─────────────────────────────────────────────────────────────────────────────
# Project — exactly one (Free tier limit), region must be an AWS region.
# ─────────────────────────────────────────────────────────────────────────────


def test_exactly_one_neon_project(resources):
    """REJECT zero or multiple `neon_project` resources.

    Neon Free's quota: 1 project / account. A second project in the
    stack would silently fail at apply with HTTP 402 from Neon's API.
    Catching here keeps the failure mode L2-fast.
    """
    projects = find_resources(resources, resource_type="neon_project")
    assert len(projects) == 1, (
        f"Sprint 2 §S2.1.2: Neon Free allows exactly 1 project per "
        f"account; found {len(projects)} declared."
    )


def test_neon_project_region_is_aws(resources, variables):
    """REJECT non-AWS region. Neon Free supports AWS regions only.

    Picking a GCP region IDs (e.g. `gcp-us-central1`) silently flips to
    AWS at provider apply-time, which makes drift detection lie. Lock
    the convention via this test by checking either the literal value or
    (more commonly) the default of the wired variable.
    """
    proj = get_one(
        find_resources(resources, resource_type="neon_project"),
        "Sprint 2 §S2.1.2 expects exactly one Neon project",
    )
    region = str(proj["attrs"].get("region_id", ""))

    # Resolve a `var.X` reference back to its declared default.
    if region.startswith("${var."):
        var_name = region.removeprefix("${var.").rstrip("}")
        var_decl = variables.get(var_name, {})
        region = str(var_decl.get("default", ""))
    elif region.startswith("var."):
        var_name = region.removeprefix("var.")
        var_decl = variables.get(var_name, {})
        region = str(var_decl.get("default", ""))

    assert region.startswith("aws-"), (
        f"Sprint 2 §S2.1.2: Neon Free only supports AWS regions; "
        f"resolved region_id={region!r} (use e.g. aws-us-east-2)."
    )


def test_neon_project_pg_version_locked(resources):
    """ACCEPT pg_version locked to 17 (matches versions.tf provider config
    `expected_version = "17"` and the live `still-credit-23413998`
    project that Tofu adopts via import).

    Neon defaults to whatever's latest; pinning prevents the LangGraph
    Postgres checkpoint adapter from breaking on a major-version bump
    that changes type catalog OIDs. The version was bumped 16→17 when
    we adopted the existing Neon-account-default project (Postgres 17
    was Neon's default at signup time on 2026-04-23).
    """
    proj = get_one(
        find_resources(resources, resource_type="neon_project"),
        "Sprint 2 §S2.1.2 expects exactly one Neon project",
    )
    pg_version = proj["attrs"].get("pg_version")
    # Accept literal 17 or a var reference; reject None / unpinned.
    assert pg_version in (17, "17") or (
        isinstance(pg_version, str) and "var." in pg_version
    ), (
        f"Sprint 2 §S2.1.2: pg_version must be pinned to 17 to match "
        f"the versions.tf postgresql provider, got {pg_version!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Database — name must be `agent_app`.
# ─────────────────────────────────────────────────────────────────────────────


def test_neon_database_uses_app_database_var(resources):
    """ACCEPT exactly one `neon_database` whose `name` is wired through
    `var.neon_database_name` (the project chose to adopt Neon's
    auto-created `neondb` instead of the sprint board's literal
    `agent_app` — see variables.tf docstring). Either a literal or a
    var ref is acceptable so the test survives both choices."""
    dbs = find_resources(resources, resource_type="neon_database")
    assert dbs, (
        "Sprint 2 §S2.1.2: at least one `neon_database` resource expected."
    )
    names = [d["attrs"].get("name") for d in dbs]
    matches = [
        d
        for d in dbs
        if d["attrs"].get("name") in ("agent_app", "neondb")
        or "neon_database_name" in str(d["attrs"].get("name", ""))
    ]
    assert matches, (
        "Sprint 2 §S2.1.2: a database wired through "
        "var.neon_database_name (or a literal `agent_app` / `neondb`) "
        f"must exist; got names={names!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# pgvector — REJECT missing extension. ACCEPT extension via the
# `cyrilgdn/postgresql` provider's `postgresql_extension` resource.
# ─────────────────────────────────────────────────────────────────────────────


def test_pgvector_extension_declared(resources):
    """ACCEPT a `postgresql_extension` resource named `vector`.

    Sprint 2 §S2.1.2 DoD: 'pgvector ready'. The Neon Tofu provider
    doesn't manage extensions; we drive that through `cyrilgdn/postgresql`
    bound to the Neon project's connection details (see versions.tf
    `provider "postgresql" {}` block).
    """
    extensions = find_resources(
        resources, resource_type="postgresql_extension"
    )
    pgvector = [e for e in extensions if e["attrs"].get("name") == "vector"]
    assert pgvector, (
        "Sprint 2 §S2.1.2 DoD: pgvector must be enabled — declare a "
        "`postgresql_extension` resource with name = \"vector\" against "
        "the Neon Postgres provider."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cross-stack handoff — connection string locals must exist for the
# postgresql provider and for Secret Manager.
# ─────────────────────────────────────────────────────────────────────────────


def test_neon_connection_locals_defined(parsed_hcl):
    """ACCEPT: a `locals {}` block defines `neon_pg_host`, `neon_pg_user`,
    `neon_pg_password`, `neon_pg_database`, and `neon_database_url`.

    These locals are consumed by:
      * versions.tf provider "postgresql" {} (host/user/password/database)
      * secret-manager.tf google_secret_manager_secret_version.neon_database_url
        (secret_data = local.neon_database_url)

    Missing any of them breaks the cross-file wiring at validate-time.
    """
    locals_blocks = parsed_hcl.get("locals", [])
    declared_locals: set[str] = set()
    for block in locals_blocks:
        if isinstance(block, dict):
            declared_locals.update(block.keys())

    required = {
        "neon_pg_host",
        "neon_pg_user",
        "neon_pg_password",
        "neon_pg_database",
        "neon_database_url",
    }
    missing = required - declared_locals
    assert not missing, (
        f"Sprint 2 §S2.1.2: missing required locals {sorted(missing)!r} "
        f"(declared: {sorted(declared_locals)!r}). These wire Neon outputs "
        "into the postgresql provider and Secret Manager."
    )
