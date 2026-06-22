"""tests/infra/gcp/test_secret_manager.py — Recipe 1 Secret Manager tests.

Adapted from tests/infra/test_secret_manager.py for the GCP Tier A stack.

Key differences from dev-tier:
  * 8 required secrets (added: database-url, agent-facts-secret; removed:
    neon-database-url which is replaced by database-url).
  * Runtime SA is `backend_runtime` (not `middleware_runtime`).
  * The `local.backend_runtime_member` local is the IAM member reference.

Failure paths first (TAP-4). Every rejection test precedes its paired
acceptance test so a reviewer can't ship a gate that accepts everything.
"""

from __future__ import annotations

import re

import pytest

from tests.infra._hcl_helpers import find_resources, get_one, unwrap_block


pytestmark = pytest.mark.infra_gcp


REQUIRED_SECRET_IDS = {
    "workos-api-key",
    "openai-api-key",
    "anthropic-api-key",
    "langfuse-public-key",
    "langfuse-secret-key",
    "mem0-api-key",
    "database-url",
    "agent-facts-secret",
    "workos-cookie-password",
}

# Frontend-only secrets — backend runtime SA must NOT receive accessor grants.
FRONTEND_ONLY_SECRET_IDS = {
    "workos-cookie-password",
}

# Retired secrets — still provisioned in Secret Manager for the Phase 5
# 24h-rollback window after the mem0 → pgvector cutover, but no longer
# wired into the backend Cloud Run service as a ``secret_key_ref`` env.
# Deleted entirely in Phase 5 S6; this set goes empty (or is removed) then.
# See ``docs/plans/replace_mem0_pgvector.phase5_s6.deletion_checklist.md``.
RETIRED_SECRET_IDS = {
    "mem0-api-key",
}

_REF_PATTERN = re.compile(
    r"\$\{[^}]+\}|(?:^|\s)(?:var|local|data|module)\.[\w.]+"
)


# ─────────────────────────────────────────────────────────────────────────────
# Existence
# ─────────────────────────────────────────────────────────────────────────────


def test_at_least_one_secret_declared(resources):
    """REJECT: if no secrets exist at all, every downstream test becomes a
    false-pass (empty iteration). Catch the degenerate case explicitly.
    """
    secrets = find_resources(resources, resource_type="google_secret_manager_secret")
    assert secrets, (
        "Recipe 1: no google_secret_manager_secret resources found in infra/gcp/. "
        "secret-manager.tf must declare all 8 required secrets."
    )


def test_all_required_secrets_declared(resources):
    """ACCEPT: each of the 8 secret resources must be declared."""
    secrets = find_resources(resources, resource_type="google_secret_manager_secret")
    declared_ids = {s["attrs"].get("secret_id") for s in secrets}
    missing = REQUIRED_SECRET_IDS - declared_ids
    assert not missing, (
        f"Recipe 1: missing required secret(s) {sorted(missing)!r}; "
        f"declared = {sorted(declared_ids)!r}."
    )


def test_no_extra_unexpected_secrets(resources):
    """ACCEPT: every declared secret is in the known set (no orphaned shells
    that would incur unnecessary Secret Manager charges or confuse operators).

    This is an informational gate — new secrets must be explicitly added to
    REQUIRED_SECRET_IDS and reviewed.
    """
    secrets = find_resources(resources, resource_type="google_secret_manager_secret")
    declared_ids = {s["attrs"].get("secret_id") for s in secrets}
    unexpected = declared_ids - REQUIRED_SECRET_IDS
    assert not unexpected, (
        f"Recipe 1: unexpected secrets found: {sorted(unexpected)!r}. "
        "Add them to REQUIRED_SECRET_IDS in this test if intentional."
    )


def test_every_secret_has_replication_block(resources):
    """REJECT secrets without a replication policy.

    GCP Secret Manager requires `replication { auto {} }` or user_managed.
    Omitting it makes `tofu apply` fail at create-time, NOT at validate-time.
    """
    secrets = find_resources(resources, resource_type="google_secret_manager_secret")
    assert secrets, "no secrets at all"
    missing_replication = [
        s["name"] for s in secrets if "replication" not in s["attrs"]
    ]
    assert not missing_replication, (
        "Recipe 1: secrets without a `replication` block — tofu apply will "
        f"reject these: {missing_replication!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Versions — REJECT plaintext secret_data
# ─────────────────────────────────────────────────────────────────────────────


def test_every_secret_has_a_version(resources):
    """ACCEPT: every secret shell must be paired with a version resource.

    Without a version, the secret shell exists but Cloud Run silently fails
    to resolve the env var at startup — a hard-to-debug 503.
    """
    secrets = find_resources(resources, resource_type="google_secret_manager_secret")
    versions = find_resources(resources, resource_type="google_secret_manager_secret_version")
    secret_names = {s["name"] for s in secrets}

    referenced = set()
    for v in versions:
        sec_ref = v["attrs"].get("secret", "")
        if isinstance(sec_ref, str):
            for s_name in secret_names:
                if s_name in sec_ref:
                    referenced.add(s_name)

    missing = secret_names - referenced
    assert not missing, (
        f"Recipe 1: secrets without a paired version: {sorted(missing)!r}. "
        "Cloud Run env binding will fail to resolve."
    )


def test_no_plaintext_secret_data_in_hcl(resources):
    """REJECT (AUTO-REJECT class — FE-AP-18 mirror): no `secret_data` may be
    a plain string literal. Every value MUST be a Tofu reference so it stays
    in the gitignored tfvars file or a TF_VAR_* env var, never committed HCL.

    This is the single most consequential security guarantee in Recipe 1 —
    a slip here exposes live credentials in `git log`.
    """
    versions = find_resources(resources, resource_type="google_secret_manager_secret_version")
    offenders = []
    for v in versions:
        data = v["attrs"].get("secret_data")
        if isinstance(data, str) and not _REF_PATTERN.search(data):
            offenders.append((v["name"], data[:20]))
    assert not offenders, (
        "Recipe 1 / FE-AP-18 AUTO-REJECT: secret_data must be a var.<name> "
        f"reference, not a literal. Offenders: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# IAM — REJECT bindings to anything other than the backend runtime SA
# ─────────────────────────────────────────────────────────────────────────────


def test_no_iam_member_grants_to_external_principal(resources):
    """REJECT (AUTO-REJECT class): no secret IAM binding may grant access to
    allUsers, allAuthenticatedUsers, or any user/group account.

    A common debugging mistake is `user:dev@example.com` — this test fails CI.
    """
    iam_members = find_resources(
        resources, resource_type="google_secret_manager_secret_iam_member"
    )
    forbidden_prefixes = (
        "allUsers",
        "allAuthenticatedUsers",
        "user:",
        "group:",
        "domain:",
    )
    offenders = [
        (r["name"], str(r["attrs"].get("member", "")))
        for r in iam_members
        if any(str(r["attrs"].get("member", "")).startswith(p) for p in forbidden_prefixes)
    ]
    assert not offenders, (
        "Recipe 1 / FE-AP-18 AUTO-REJECT: secret IAM bindings may only grant "
        "the backend runtime service account; offenders: "
        f"{offenders!r}."
    )


def test_every_secret_has_iam_accessor_for_runtime_sa(resources):
    """ACCEPT: every secret has at least one google_secret_manager_secret_iam_member
    granting roles/secretmanager.secretAccessor to the backend runtime SA.

    Without this, Cloud Run's startup probe passes (env vars are resolved lazily)
    but the first request that touches the secret silently 503s.
    """
    secrets = find_resources(resources, resource_type="google_secret_manager_secret")
    iam_members = find_resources(
        resources, resource_type="google_secret_manager_secret_iam_member"
    )
    secret_names = {s["name"] for s in secrets}
    backend_secret_names = {
        s["name"]
        for s in secrets
        if s["attrs"].get("secret_id") not in FRONTEND_ONLY_SECRET_IDS
    }

    runtime_member_markers = (
        "google_service_account.backend_runtime",
        "local.backend_runtime_member",
    )
    bound_secrets: set[str] = set()
    for binding in iam_members:
        attrs = binding["attrs"]
        if attrs.get("role") != "roles/secretmanager.secretAccessor":
            continue
        member = str(attrs.get("member", ""))
        if not any(m in member for m in runtime_member_markers):
            continue
        sec_ref = str(attrs.get("secret_id", ""))
        for s_name in secret_names:
            if s_name in sec_ref:
                bound_secrets.add(s_name)

    missing = backend_secret_names - bound_secrets
    assert not missing, (
        "Recipe 1: backend secrets missing a secretAccessor IAM binding to the "
        f"backend_runtime SA: {sorted(missing)!r}. "
        "Cloud Run will fail to read them at startup."
    )


def test_secret_iam_role_is_only_accessor(resources):
    """REJECT roles broader than secretmanager.secretAccessor on per-secret
    bindings. The runtime SA must never have secretmanager.admin or editor.
    """
    iam_members = find_resources(
        resources, resource_type="google_secret_manager_secret_iam_member"
    )
    offenders = [
        (r["name"], r["attrs"].get("role"))
        for r in iam_members
        if r["attrs"].get("role") != "roles/secretmanager.secretAccessor"
    ]
    assert not offenders, (
        "Recipe 1: secret-level IAM bindings must use "
        "roles/secretmanager.secretAccessor only. "
        f"Offenders: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Variable hygiene
# ─────────────────────────────────────────────────────────────────────────────


_SECRET_VAR_SUFFIXES = (
    "_api_key",
    "_secret_key",
    "_password",
    "_database_url",
    "_secret",  # agent_facts_secret
    "_url",     # database_url
)


def test_every_secret_var_is_marked_sensitive(variables):
    """REJECT secret-bearing variables not flagged `sensitive = true`.

    Tofu redacts sensitive values from `tofu plan` output and CI logs.
    Without the flag, a secret value can leak into a PR's plan-diff artifact.
    """
    offenders = []
    for var_name, attrs in variables.items():
        if not any(var_name.endswith(s) for s in _SECRET_VAR_SUFFIXES):
            continue
        if attrs.get("sensitive") is not True:
            offenders.append(var_name)
    assert not offenders, (
        "Recipe 1 / FE-AP-18 AUTO-REJECT: secret-bearing variables missing "
        f"`sensitive = true`: {offenders!r}."
    )


def test_no_secret_var_is_named_next_public(variables):
    """AUTO-REJECT (FE-AP-18): no variable holding a secret may have a name
    starting with NEXT_PUBLIC_*. Defensive — protects against copy-paste
    from frontend/.env.local accidentally leaking a secret via Tofu var.
    """
    offenders = [
        v for v in variables
        if v.upper().startswith("NEXT_PUBLIC_")
        and any(s in v.lower() for s in ("key", "secret", "token", "password", "url"))
    ]
    assert not offenders, (
        "Recipe 1 / FE-AP-18 AUTO-REJECT: Tofu variables named NEXT_PUBLIC_* "
        f"with secret semantics: {offenders!r}."
    )
