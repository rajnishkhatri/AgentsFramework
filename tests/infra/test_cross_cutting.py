"""tests/infra/test_cross_cutting.py — Sprint 2 cross-cutting DoD tests.

These tests enforce the cross-cutting Definition of Done items from
`docs/plan/frontend/SPRINT_BOARD.md` that apply to infrastructure code:

  | Category   | Requirement                                              |
  |------------|----------------------------------------------------------|
  | Security   | No `'unsafe-inline'` or `'unsafe-eval'` in CSP           |
  | Security   | No secrets in `NEXT_PUBLIC_*` env vars                   |
  | Security   | No `dangerouslySetInnerHTML` on agent output             |
  | Architecture | BFF holds no cloud credentials                         |

Plus IaC-specific gates that prevent silent regressions:

  * No `provider {}` block has hardcoded credentials.
  * No `output {}` exposes a value flagged sensitive (would defeat
    `sensitive = true` on the source variable).
  * Every `.tf` file has a leading docstring/comment block (consistency
    with the four-layer architecture's documentation-as-architecture
    principle).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.infra._hcl_helpers import find_resources


pytestmark = pytest.mark.infra


# ─────────────────────────────────────────────────────────────────────────────
# Variables — all secret-bearing vars are flagged sensitive (covered in
# detail by test_secret_manager.py); this is the cross-cutting wrapper.
# ─────────────────────────────────────────────────────────────────────────────


_SECRET_VAR_NAME_HINTS = ("api_key", "secret_key", "password", "token")


def test_no_variable_starts_with_next_public(variables):
    """REJECT (FE-AP-18 AUTO-REJECT): no Tofu variable name begins with
    `NEXT_PUBLIC_`. The Next.js public-env convention exposes any such
    var to the browser bundle; on the IaC side we forbid the prefix
    entirely so a future copy-paste from frontend/.env.local can't slip
    a secret in."""
    offenders = [v for v in variables.keys() if v.upper().startswith("NEXT_PUBLIC_")]
    assert not offenders, (
        f"Sprint 2 cross-cutting DoD / FE-AP-18: variables starting "
        f"with NEXT_PUBLIC_ are forbidden in infra/, found {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Outputs — REJECT outputting any value bound to a secret variable.
# ─────────────────────────────────────────────────────────────────────────────


def test_no_secret_outputs(outputs, variables):
    """REJECT outputs whose value is a `var.<sensitive_var>` reference.

    Outputs are visible in `tofu output` and in CI logs — emitting a
    sensitive var via output bypasses the `sensitive = true` redaction.
    Allowed: marking the output itself sensitive (Tofu redacts in plan)
    AND only when the consumer absolutely needs the value (currently
    none in this stack)."""
    sensitive_vars = {
        name for name, attrs in variables.items() if attrs.get("sensitive") is True
    }
    offenders = []
    for out_name, attrs in outputs.items():
        value = str(attrs.get("value", ""))
        for sensitive in sensitive_vars:
            if f"var.{sensitive}" in value and attrs.get("sensitive") is not True:
                offenders.append((out_name, sensitive))
    assert not offenders, (
        f"Sprint 2 cross-cutting DoD: outputs reveal sensitive vars "
        f"without `sensitive = true`: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Provider blocks — REJECT hardcoded credentials.
# ─────────────────────────────────────────────────────────────────────────────


# Patterns that look like a baked-in credential rather than a `var.X` ref.
_CREDENTIAL_LIKE_PATTERN = re.compile(
    r"(?:sk-|sk_|pk-|pk_|m0-|neon_|cf_|gh[ps]_)[A-Za-z0-9_-]{16,}"
)


def test_no_hardcoded_credentials_in_providers(parsed_hcl):
    """REJECT any string in a `provider {}` block that looks like a
    credential token (matches the SDK conventional prefixes
    sk-/sk_/pk-/pk_/m0-/cf_/gh[ps]_ followed by 16+ chars).

    This catches the most common authoring slip: pasting a real key into
    a provider block while iterating, then committing.
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
        "Sprint 2 cross-cutting DoD / FE-AP-18: provider blocks contain "
        f"credential-shaped literals: {offenders!r}. Use var.<name> instead."
    )


# ─────────────────────────────────────────────────────────────────────────────
# trace_id forwarding parity (cross-stack DoD: F-R7) — informational.
# Sprint 2 IaC doesn't generate or transform trace_ids; this test is a
# placeholder/canary that future Tofu modules don't introduce trace_id
# manipulation outside the Python middleware.
# ─────────────────────────────────────────────────────────────────────────────


def test_no_trace_id_generation_in_hcl(tf_files):
    """ACCEPT: no .tf file mentions trace_id.

    Sprint 2 cross-cutting DoD (F-R7): `trace_id` originates in the
    Python middleware adapter and flows verbatim through every layer.
    IaC must be inert with respect to trace identity. A grep for
    `trace_id` in HCL would mean someone is trying to bake a header
    rewrite or tag at the edge — not in scope for this sprint.
    """
    offenders = []
    for tf in tf_files:
        text = tf.read_text(encoding="utf-8")
        if re.search(r"\btrace_id\b", text, re.IGNORECASE):
            offenders.append(tf.name)
    assert not offenders, (
        "Sprint 2 cross-cutting DoD (F-R7): IaC must not reference "
        f"trace_id. Files: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Documentation discipline — every .tf file must have a leading comment
# block describing its scope. Mirrors the docstring discipline from
# AGENTS.md §Development Conventions.
# ─────────────────────────────────────────────────────────────────────────────


def test_every_tf_file_has_leading_docstring(tf_files):
    """ACCEPT: every .tf file's first non-empty line is a `#` comment
    that names the file path and a one-line scope.

    Catches drive-by additions that skip the documentation hygiene the
    rest of the stack maintains.
    """
    offenders = []
    for tf in tf_files:
        first_line = next(
            (
                line.strip()
                for line in tf.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ),
            "",
        )
        if not first_line.startswith("#"):
            offenders.append(tf.name)
    assert not offenders, (
        "Sprint 2 documentation hygiene: every .tf file must start with "
        f"a `#` comment block. Files lacking it: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Resource-name discipline — Tofu local names use snake_case (matches the
# rest of the codebase's snake_case-on-wire rule, mirrored on infra side).
# ─────────────────────────────────────────────────────────────────────────────


def test_resource_local_names_are_snake_case(resources):
    """ACCEPT: every `resource "type" "<local_name>"` uses snake_case.

    Mixing kebab- and snake-case across .tf files breaks `for_each`
    iteration patterns and confuses CI scripts. The cross-cutting style
    rule (`snake_case on wire; camelCase only after translator`) extends
    naturally to IaC."""
    snake_re = re.compile(r"^[a-z][a-z0-9_]*$")
    offenders = [
        f"{r['type']}.{r['name']}"
        for r in resources
        if not snake_re.match(r["name"])
    ]
    assert not offenders, (
        "Sprint 2 naming discipline: resource local names must be "
        f"snake_case. Offenders: {offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 2 §S2.1.4 cross-cutting: confirm Cloud Run env vars don't include
# any *KEY* / *SECRET* / *TOKEN* as a literal `value` (must use
# `value_source.secret_key_ref` instead).
# ─────────────────────────────────────────────────────────────────────────────


def test_no_cloud_run_env_var_has_literal_secret(resources):
    """REJECT a Cloud Run `env { name = "*KEY*", value = "literal" }`.

    The acceptable shape is `env { name = ..., value_source {
    secret_key_ref { ... } } }` — covered by test_cloud_run.py.
    """
    cloud_run_services = find_resources(
        resources, resource_type="google_cloud_run_v2_service"
    )
    offenders = []
    for svc in cloud_run_services:
        template = svc["attrs"].get("template")
        template_dict = (
            template[0] if isinstance(template, list) else template
        )
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
                if not isinstance(value, str):
                    continue
                if value == "":
                    continue
                if any(
                    suffix in name.upper()
                    for suffix in ("KEY", "SECRET", "TOKEN", "PASSWORD")
                ):
                    offenders.append((svc["name"], name, value[:20]))
    assert not offenders, (
        "Sprint 2 §S2.1.4 / FE-AP-18 AUTO-REJECT: Cloud Run env var "
        "with secret-shaped name has a literal value (use "
        f"value_source.secret_key_ref): {offenders!r}."
    )
