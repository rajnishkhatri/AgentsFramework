"""tests/infra/gcp/test_cross_cutting.py — GCP Tier A cross-cutting DoD tests.

Adapted from tests/infra/test_cross_cutting.py for infra/gcp/.

Cross-cutting requirements enforced:

  | Category     | Requirement                                              |
  |--------------|----------------------------------------------------------|
  | Security     | No secrets in NEXT_PUBLIC_* env vars (FE-AP-18)          |
  | Security     | No secret values escaped via outputs                     |
  | Security     | No provider {} blocks with hardcoded credentials         |
  | Security     | No Cloud Run env vars with literal secret-shaped values  |
  | Architecture | trace_id is never generated or transformed in HCL        |
  | Hygiene      | Every .tf file has a leading # comment block             |
  | Hygiene      | Resource local names use snake_case                      |
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.infra._hcl_helpers import find_resources


pytestmark = pytest.mark.infra_gcp


# ─────────────────────────────────────────────────────────────────────────────
# Variables — no NEXT_PUBLIC_* names for any variable
# ─────────────────────────────────────────────────────────────────────────────


def test_no_variable_starts_with_next_public(variables):
    """REJECT (FE-AP-18 AUTO-REJECT): no Tofu variable name begins with
    NEXT_PUBLIC_. The Next.js public-env convention exposes any such var to
    the browser bundle; forbidding the prefix in IaC prevents copy-paste leaks.
    """
    offenders = [v for v in variables if v.upper().startswith("NEXT_PUBLIC_")]
    assert not offenders, (
        "Recipe 1 cross-cutting DoD / FE-AP-18: variables starting with "
        f"NEXT_PUBLIC_ are forbidden in infra/, found {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Outputs — REJECT outputting any sensitive variable's value
# ─────────────────────────────────────────────────────────────────────────────


def test_no_secret_outputs(outputs, variables):
    """REJECT outputs whose value is a `var.<sensitive_var>` reference without
    the output itself being marked sensitive.

    Outputs are visible in `tofu output` and in CI logs — emitting a sensitive
    var via output bypasses the `sensitive = true` redaction.
    """
    sensitive_vars = {
        name for name, attrs in variables.items() if attrs.get("sensitive") is True
    }
    offenders = []
    for out_name, attrs in outputs.items():
        value = str(attrs.get("value", ""))
        for sv in sensitive_vars:
            if f"var.{sv}" in value and attrs.get("sensitive") is not True:
                offenders.append((out_name, sv))
    assert not offenders, (
        "Recipe 1 cross-cutting DoD: outputs reveal sensitive vars without "
        f"`sensitive = true`: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Provider blocks — REJECT hardcoded credentials
# ─────────────────────────────────────────────────────────────────────────────


_CREDENTIAL_LIKE_PATTERN = re.compile(
    r"(?:sk-|sk_|pk-|pk_|m0-|AIza|ya29\.|gcp_)[A-Za-z0-9_-]{16,}"
)


def test_no_hardcoded_credentials_in_providers(parsed_hcl):
    """REJECT any string in a `provider {}` block that looks like a credential
    token. Catches the most common authoring slip: pasting a real key into a
    provider block while iterating, then committing.
    """
    provider_entries = parsed_hcl.get("provider", [])
    offenders = []
    for entry in provider_entries:
        if not isinstance(entry, dict):
            continue
        for prov_name, attrs in entry.items():
            if not isinstance(attrs, dict):
                continue
            for k, v in attrs.items():
                if isinstance(v, str) and _CREDENTIAL_LIKE_PATTERN.search(v):
                    offenders.append((prov_name, k, v[:20] + "..."))
    assert not offenders, (
        "Recipe 1 cross-cutting DoD / FE-AP-18: provider blocks contain "
        f"credential-shaped literals: {offenders!r}. Use var.<name> instead."
    )


# ─────────────────────────────────────────────────────────────────────────────
# trace_id forwarding parity (F-R7) — IaC must not touch trace_id
# ─────────────────────────────────────────────────────────────────────────────


def test_no_trace_id_generation_in_hcl(tf_files):
    """ACCEPT: no .tf file mentions trace_id.

    Cross-cutting DoD (F-R7): trace_id originates in the Python middleware
    adapter and flows verbatim. Any trace_id reference in HCL would mean
    someone is trying to bake a header rewrite or tag at the edge.
    """
    offenders = []
    for tf in tf_files:
        text = tf.read_text(encoding="utf-8")
        if re.search(r"\btrace_id\b", text, re.IGNORECASE):
            offenders.append(tf.name)
    assert not offenders, (
        "Recipe 1 cross-cutting DoD (F-R7): IaC must not reference trace_id. "
        f"Files: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Documentation discipline — every .tf file must have a leading # comment
# ─────────────────────────────────────────────────────────────────────────────


def test_every_tf_file_has_leading_docstring(tf_files):
    """ACCEPT: every .tf file's first non-empty line is a `#` comment that
    names the file and its scope.

    Mirrors the docstring discipline from AGENTS.md §Development Conventions
    and the same test in tests/infra/test_cross_cutting.py.
    """
    offenders = []
    for tf in tf_files:
        first_line = next(
            (line.strip() for line in tf.read_text(encoding="utf-8").splitlines() if line.strip()),
            "",
        )
        if not first_line.startswith("#"):
            offenders.append(tf.name)
    assert not offenders, (
        "Recipe 1 documentation hygiene: every .tf file must start with a "
        f"`#` comment block. Files lacking it: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Resource-name discipline — Tofu local names use snake_case
# ─────────────────────────────────────────────────────────────────────────────


def test_resource_local_names_are_snake_case(resources):
    """ACCEPT: every `resource "type" "<local_name>"` uses snake_case.

    Mixing kebab- and snake-case breaks for_each iteration patterns and
    confuses CI scripts. The cross-cutting style rule extends to IaC.
    """
    snake_re = re.compile(r"^[a-z][a-z0-9_]*$")
    offenders = [
        f"{r['type']}.{r['name']}"
        for r in resources
        if not snake_re.match(r["name"])
    ]
    assert not offenders, (
        "Recipe 1 naming discipline: resource local names must be snake_case. "
        f"Offenders: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cloud Run env vars — REJECT literal secret values (forward compatibility)
# ─────────────────────────────────────────────────────────────────────────────


def test_no_cloud_run_env_var_has_literal_secret(resources):
    """REJECT a Cloud Run `env { name = "*KEY*", value = "literal" }`.

    Recipe 1 has no Cloud Run resources yet — this test is a forward-compat
    gate so Recipe 4 additions don't accidentally introduce literal secrets.
    It passes trivially now and enforces the constraint when Cloud Run TF is added.
    """
    cloud_run_services = find_resources(resources, resource_type="google_cloud_run_v2_service")
    offenders = []
    for svc in cloud_run_services:
        template = svc["attrs"].get("template")
        template_dict = template[0] if isinstance(template, list) else template
        if not isinstance(template_dict, dict):
            continue
        containers = template_dict.get("containers", [])
        if isinstance(containers, dict):
            containers = [containers]
        for container in containers:
            envs = container.get("env", [])
            if isinstance(envs, dict):
                envs = [envs]
            for env in envs:
                name = str(env.get("name", ""))
                value = env.get("value")
                if not isinstance(value, str) or value == "":
                    continue
                if any(suffix in name.upper() for suffix in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
                    offenders.append((svc["name"], name, value[:20]))
    assert not offenders, (
        "Recipe 1 / FE-AP-18 AUTO-REJECT: Cloud Run env var with secret-shaped "
        "name has a literal value (use value_source.secret_key_ref): "
        f"{offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# OpenTofu validate — syntactic correctness (optional, skip if tofu absent)
# ─────────────────────────────────────────────────────────────────────────────


def test_tofu_validate_passes(tofu_validate_result):
    """ACCEPT: `tofu validate` exits 0 with no errors.

    This catches syntax errors and reference mistakes that python-hcl2 parsing
    cannot catch (e.g. referencing a resource that doesn't exist, wrong
    attribute names for the provider version).

    Skipped automatically if OpenTofu is not installed locally.
    """
    result = tofu_validate_result
    if result.get("stage") == "init" and result.get("returncode") != 0:
        pytest.skip(f"tofu init failed: {result.get('stderr', '')[:200]}")

    validate_json = result.get("json", {})
    assert validate_json.get("valid") is True, (
        "Recipe 1: `tofu validate` reports errors. "
        f"Diagnostics: {validate_json.get('diagnostics', [])!r}. "
        f"stderr: {result.get('stderr', '')[:500]}"
    )
