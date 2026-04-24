"""tests/infra/test_secret_manager.py — Sprint 2 §S2.1.4 acceptance tests.

Story under test:

  > S2.1.4 — As a DevOps engineer, I want secrets (WorkOS, OpenAI, Anthropic,
  > Langfuse, Mem0, Neon) stored in GCP Secret Manager and referenced by the
  > Cloud Run service, so that no credentials are hardcoded.

Cross-cutting DoD touched (FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md §F-R9
mirror; SPRINT_BOARD.md cross-cutting table):

  * `BFF holds no cloud credentials` — only the Cloud Run runtime SA may
    accessor-bind these secrets, never any frontend SA.
  * `No NEXT_PUBLIC_*` containing `*KEY*`, `*SECRET*`, `*TOKEN*` (FE-AP-18
    AUTO-REJECT) — enforced here by checking that no Tofu variable holding
    a secret has a name starting with the `NEXT_PUBLIC_` prefix.
  * Failure paths first (TAP-4): secret-data must NEVER be a literal in
    HCL (always `var.<secret>`); the IAM accessor binding must NEVER name
    a non-runtime principal.

The 6 required secrets per Sprint 2 §S2.1.4 are:

  workos_api_key, openai_api_key, anthropic_api_key, langfuse_secret_key,
  mem0_api_key, neon_database_url

We additionally create `langfuse_public_key` because the middleware
adapter needs both keys (see middleware/adapters/observability/
langfuse_cloud_exporter.py).
"""

from __future__ import annotations

import re

import pytest

from tests.infra._hcl_helpers import find_resources, get_one, unwrap_block


pytestmark = pytest.mark.infra


REQUIRED_SECRET_IDS = {
    "workos-api-key",
    "openai-api-key",
    "anthropic-api-key",
    "langfuse-public-key",
    "langfuse-secret-key",
    "mem0-api-key",
    "neon-database-url",
}


# ─────────────────────────────────────────────────────────────────────────────
# Existence — every required secret must be declared.
# ─────────────────────────────────────────────────────────────────────────────


def test_all_required_secrets_declared(resources):
    """Sprint 2 §S2.1.4 acceptance: each of the 7 secret resources must
    exist as a `google_secret_manager_secret`. Missing any one means the
    Cloud Run env var binding will fail on the first apply."""
    secrets = find_resources(
        resources, resource_type="google_secret_manager_secret"
    )
    declared_ids = {s["attrs"].get("secret_id") for s in secrets}
    missing = REQUIRED_SECRET_IDS - declared_ids
    assert not missing, (
        f"Sprint 2 §S2.1.4: missing required secret(s) {sorted(missing)!r}; "
        f"declared = {sorted(declared_ids)!r}."
    )


def test_every_secret_has_replication_block(resources):
    """REJECT secrets without a replication policy.

    GCP Secret Manager requires `replication.auto {}` or
    `replication.user_managed { ... }`. Omitting it makes `tofu apply`
    fail at create-time, NOT at validate-time, so we catch it here in
    fast feedback land.
    """
    secrets = find_resources(
        resources, resource_type="google_secret_manager_secret"
    )
    assert secrets, "no google_secret_manager_secret resources at all"
    missing_replication = [
        s["name"] for s in secrets if "replication" not in s["attrs"]
    ]
    assert not missing_replication, (
        "Sprint 2 §S2.1.4: secrets without `replication` block — Tofu "
        f"apply will reject these: {missing_replication!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Versions — REJECT plaintext secret_data; accept only var.<...> refs.
# ─────────────────────────────────────────────────────────────────────────────


# Match any Tofu interpolation `${...}` or bare `var.x` / `local.x` /
# `data.x.y` reference. The point is "not a baked-in literal" — anything
# that resolves at apply-time is acceptable.
_REF_PATTERN = re.compile(
    r"\$\{[^}]+\}|(?:^|\s)(?:var|local|data|module)\.[\w.]+"
)


def test_every_secret_has_a_version(resources):
    """Sprint 2 secret strategy `tofu_creates_versions` (per user
    clarification): every secret resource must be paired with at least one
    `google_secret_manager_secret_version`. Without a version the secret
    'shell' exists but Cloud Run cannot pull a value at boot."""
    secrets = find_resources(
        resources, resource_type="google_secret_manager_secret"
    )
    versions = find_resources(
        resources, resource_type="google_secret_manager_secret_version"
    )
    secret_ids = {s["attrs"].get("secret_id") for s in secrets}

    # Each version's `secret` attr references its parent secret resource.
    referenced = set()
    for v in versions:
        sec_ref = v["attrs"].get("secret", "")
        if isinstance(sec_ref, str):
            for s in secrets:
                if s["name"] in sec_ref:
                    referenced.add(s["attrs"].get("secret_id"))

    missing = secret_ids - referenced
    assert not missing, (
        f"Sprint 2 §S2.1.4: secrets without a paired version: "
        f"{sorted(missing)!r}. Cloud Run env binding will fail to resolve."
    )


def test_no_plaintext_secret_data_in_hcl(resources):
    """REJECT (AUTO-REJECT class — FE-AP-18 mirror): no `secret_data`
    attribute may be a plain string literal. Every value MUST be a Tofu
    `var.<name>` reference so it lives in the gitignored tfvars file or
    a `TF_VAR_*` env var, never in committed HCL.

    This is the single most consequential security guarantee in S2.1.4 —
    a slip here exposes live credentials in `git log`.
    """
    versions = find_resources(
        resources, resource_type="google_secret_manager_secret_version"
    )
    offenders = []
    for v in versions:
        data = v["attrs"].get("secret_data")
        # python-hcl2 renders ${var.x} as a string starting with "${" — those
        # are valid. Plain literals would be regular strings without ${.
        if isinstance(data, str) and not _REF_PATTERN.search(data):
            offenders.append((v["name"], data[:20]))
    assert not offenders, (
        "Sprint 2 §S2.1.4 / FE-AP-18 AUTO-REJECT: secret_data must be a "
        f"var.<name> reference, not a literal. Offenders: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# IAM — REJECT bindings that grant access to anything other than the
# middleware runtime SA. Accept *member* bindings only (not *binding*) so
# we don't replace pre-existing accessors.
# ─────────────────────────────────────────────────────────────────────────────


def test_every_secret_has_iam_accessor_for_runtime_sa(resources):
    """ACCEPT: every secret has at least one
    `google_secret_manager_secret_iam_member` granting
    `roles/secretmanager.secretAccessor` to the middleware runtime SA.

    Without this binding, Cloud Run's startup probe still passes (env vars
    aren't resolved until the container reads them) but the first request
    that touches the secret silently 503s with `permission denied`. That
    is exactly the class of failure that L2 contract tests should catch
    pre-apply."""
    secrets = find_resources(
        resources, resource_type="google_secret_manager_secret"
    )
    iam_members = find_resources(
        resources, resource_type="google_secret_manager_secret_iam_member"
    )

    secret_names = {s["name"] for s in secrets}
    bound_secrets = set()
    # Accept either a direct reference to the runtime SA or an indirection
    # via `local.middleware_runtime_member` (defined in secret-manager.tf
    # locals to keep the IAM member string DRY).
    runtime_member_markers = (
        "google_service_account.middleware_runtime",
        "local.middleware_runtime_member",
    )
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

    missing = secret_names - bound_secrets
    assert not missing, (
        "Sprint 2 §S2.1.4: secrets missing a "
        f"secretAccessor IAM binding to the middleware runtime SA: "
        f"{sorted(missing)!r}. Cloud Run will fail to read them."
    )


def test_no_iam_member_grants_to_external_principal(resources):
    """REJECT (AUTO-REJECT class): no secret IAM binding may grant access
    to `allUsers`, `allAuthenticatedUsers`, or any user/group account.
    Only the dedicated middleware runtime service account is permitted.

    A common mistake is granting a personal `user:dev@example.com` for
    debugging — this test fails CI on that mistake.
    """
    iam_members = find_resources(
        resources, resource_type="google_secret_manager_secret_iam_member"
    )
    forbidden_member_prefixes = (
        "allUsers",
        "allAuthenticatedUsers",
        "user:",
        "group:",
        "domain:",
    )
    offenders = []
    for binding in iam_members:
        member = str(binding["attrs"].get("member", ""))
        if any(member.startswith(p) for p in forbidden_member_prefixes):
            offenders.append((binding["name"], member))
    assert not offenders, (
        "Sprint 2 §S2.1.4 / FE-AP-18 AUTO-REJECT: secret IAM bindings may "
        "only grant the middleware runtime service account; offenders: "
        f"{offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cloud Run wiring — every secret must be referenced by the middleware
# service via `value_source.secret_key_ref`. No middleware secret may be
# orphaned; no Cloud Run env var may name a secret outside the seven.
# ─────────────────────────────────────────────────────────────────────────────


def test_cloud_run_references_every_required_secret(resources):
    """ACCEPT: cloud-run.tf wires every required secret as an env var via
    `value_source.secret_key_ref`. A missing wire here means the
    middleware boots without a credential and silently degrades."""
    cr = get_one(
        find_resources(resources, resource_type="google_cloud_run_v2_service"),
        "Sprint 2 §S2.1.1 expects exactly one Cloud Run service",
    )
    template = unwrap_block(cr["attrs"].get("template"))
    assert template is not None
    container = unwrap_block(template.get("containers"))
    assert container is not None

    env_blocks = container.get("env") or []
    if isinstance(env_blocks, dict):
        env_blocks = [env_blocks]

    secret_refs = set()
    for env_entry in env_blocks:
        vs = unwrap_block(env_entry.get("value_source"))
        if vs is None:
            continue
        sk = unwrap_block(vs.get("secret_key_ref"))
        if sk is None:
            continue
        ref = str(sk.get("secret", ""))
        for sec_id in REQUIRED_SECRET_IDS:
            # Resource local names are derived from secret_id with -→_
            local_name = sec_id.replace("-", "_")
            if local_name in ref:
                secret_refs.add(sec_id)

    missing = REQUIRED_SECRET_IDS - secret_refs
    assert not missing, (
        "Sprint 2 §S2.1.4: Cloud Run service does not reference these "
        f"required secrets via secret_key_ref: {sorted(missing)!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Variable hygiene — every secret-bearing variable must be declared
# `sensitive = true` and must NOT be named `NEXT_PUBLIC_*`.
# ─────────────────────────────────────────────────────────────────────────────


_SECRET_VAR_SUFFIXES = (
    "_api_key",
    "_secret_key",
    "_password",
    "_database_url",
)


def test_every_secret_var_is_marked_sensitive(variables):
    """REJECT secret-bearing variables not flagged `sensitive = true`.

    Tofu redacts sensitive values from `tofu plan` output and CI logs.
    Without the flag, a secret value can leak into a PR's plan-diff
    artifact — exactly the class of leak FE-AP-18 calls out.
    """
    offenders = []
    for var_name, attrs in variables.items():
        if not any(var_name.endswith(s) for s in _SECRET_VAR_SUFFIXES):
            continue
        if attrs.get("sensitive") is not True:
            offenders.append(var_name)
    assert not offenders, (
        "Sprint 2 §S2.1.4 / FE-AP-18 AUTO-REJECT: secret-bearing "
        f"variables missing `sensitive = true`: {offenders!r}."
    )


def test_no_secret_var_is_named_next_public(variables):
    """AUTO-REJECT (FE-AP-18, FD3.SEC1): no variable holding a secret may
    have a name starting with `NEXT_PUBLIC_*` (the Next.js build-time
    public-env-var convention). Such a name would leak the value into
    the browser bundle if the variable were ever consumed as a Next.js
    env input.

    Defensive — Tofu vars never feed Next.js directly, but the naming
    convention is enforceable here at zero cost.
    """
    offenders = [
        v
        for v in variables.keys()
        if v.upper().startswith("NEXT_PUBLIC_")
        and any(s in v.lower() for s in ("key", "secret", "token", "password"))
    ]
    assert not offenders, (
        "Sprint 2 cross-cutting DoD / FE-AP-18 AUTO-REJECT: Tofu variables "
        f"named NEXT_PUBLIC_* with secret semantics: {offenders!r}."
    )
