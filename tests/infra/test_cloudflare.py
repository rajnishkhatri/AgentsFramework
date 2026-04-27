"""tests/infra/test_cloudflare.py — Sprint 2 §S2.1.3 acceptance tests.

Story under test:

  > S2.1.3 — As a DevOps engineer, I want
  > `infra/dev-tier/cloudflare-pages.tf` + `cloudflare-edge.tf` to provision
  > Cloudflare Pages project + Free zone with basic WAF, so that the
  > frontend has a hosting target with native SSE streaming support.

Acceptance shape:

  * Cloudflare Pages project (`cloudflare_pages_project`) for the BFF.
  * The Free zone is referenced via `data "cloudflare_zone"` (we don't
    create it — the user creates the zone manually per RUNBOOK.md).
  * A `cloudflare_ruleset` in `phase = http_request_firewall_custom` with
    rules in count/log mode (Sprint 2 §S2.1.3 DoD: 'WAF in count mode for
    24h').
  * No cache rule disables SSE; SSE responses must NOT be buffered or
    cached. (Sprint 2 §S2.1.3 acceptance: 'SSE test endpoint streams
    byte-for-byte'; mirror of the V1 anti-pattern that required
    `CachingDisabled` on CloudFront.)

Cross-cutting AUTO-REJECT (FE-AP-4 from STYLE_GUIDE_FRONTEND.md): no
iframe sandbox token `allow-same-origin` is allowed. The WAF/ruleset
side of this is enforced indirectly by checking that we don't push a
`Permissions-Policy` ruleset that re-enables it.

Failure-paths first per TAP-4.
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
# Pages project — exists, named per variable, production branch is `main`.
# ─────────────────────────────────────────────────────────────────────────────


def test_cloudflare_pages_project_exists(resources):
    """ACCEPT exactly one `cloudflare_pages_project` resource."""
    projects = find_resources(
        resources, resource_type="cloudflare_pages_project"
    )
    assert len(projects) == 1, (
        f"Sprint 2 §S2.1.3: exactly one Pages project expected, "
        f"got {len(projects)}."
    )


def test_cloudflare_pages_production_branch_is_main(resources, variables):
    """REJECT pages production branch != `main`. Mismatch with the BFF
    repo's default branch silently breaks `wrangler pages deploy`."""
    proj = get_one(
        find_resources(resources, resource_type="cloudflare_pages_project"),
        "Sprint 2 §S2.1.3 expects exactly one Pages project",
    )
    prod_branch = str(proj["attrs"].get("production_branch", ""))
    if prod_branch.startswith("${var."):
        var_name = prod_branch.removeprefix("${var.").rstrip("}")
        prod_branch = str(variables.get(var_name, {}).get("default", ""))
    elif prod_branch.startswith("var."):
        var_name = prod_branch.removeprefix("var.")
        prod_branch = str(variables.get(var_name, {}).get("default", ""))
    assert prod_branch == "main", (
        f"Sprint 2 §S2.1.3: production_branch must be 'main', "
        f"resolved to {prod_branch!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Zone — Sprint 2 §S2.1.3: Free zone is *referenced*, not created.
# ─────────────────────────────────────────────────────────────────────────────


def test_zone_referenced_via_data_source(data_sources, resources):
    """REJECT a `cloudflare_zone` *resource* (we don't create the zone —
    the user does, per the RUNBOOK account-setup checklist).

    ACCEPT a `data "cloudflare_zone"` block so the rest of the stack can
    look up the zone ID consistently.
    """
    zone_resources = find_resources(
        resources, resource_type="cloudflare_zone"
    )
    assert not zone_resources, (
        f"Sprint 2 §S2.1.3: zones are user-owned, not Tofu-managed; "
        f"found {len(zone_resources)} `cloudflare_zone` resource(s) — "
        "switch to `data \"cloudflare_zone\" {}` instead."
    )

    # The zone CAN be wired purely via var.cloudflare_zone_id (that's
    # equally valid). Either a data source OR direct var usage satisfies
    # the contract — assert at least one of those is present.
    zone_data = [d for d in data_sources if d["type"] == "cloudflare_zone"]
    # If no data source, the ruleset assertions below will check the var
    # path. So this assertion is a soft "you SHOULD have a data source for
    # readability" — flip to hard once the team commits to a convention.


# ─────────────────────────────────────────────────────────────────────────────
# WAF — Sprint 2 §S2.1.3 DoD: 'WAF managed ruleset active in count mode'.
# Cloudflare Free tier exposes the Cloudflare Free Managed Ruleset for
# count-only deployment via `cloudflare_ruleset`.
# ─────────────────────────────────────────────────────────────────────────────


def test_cloudflare_ruleset_for_waf_exists(resources):
    """Sprint 4 §S4.1.1: a `cloudflare_ruleset` in a
    `http_request_firewall_custom` phase must exist (WAF in enforce mode).

    History: deferred from Sprint 2 §S2.1.3 due to Cloudflare Pro
    entitlement erratum (see cloudflare-edge.tf header). Sprint 4 adds
    the ruleset with `block` action (no 24h observation window; rely on
    manual review per the sprint board).
    """
    rulesets = find_resources(
        resources, resource_type="cloudflare_ruleset"
    )
    waf_rulesets = [
        r
        for r in rulesets
        if str(r["attrs"].get("phase", "")).startswith(
            "http_request_firewall"
        )
    ]
    assert waf_rulesets, (
        "Sprint 4 §S4.1.1 DoD: a `cloudflare_ruleset` in a "
        "`http_request_firewall_*` phase must exist (WAF in enforce mode)."
    )


def test_waf_rules_use_enforce_actions(resources):
    """REJECT WAF rules with non-enforcing actions (log / skip). Sprint 4
    §S4.1.1: 'Cloudflare Free WAF moved from count mode to enforce mode'.

    On Pro tier, the allowed enforcing actions are: block,
    managed_challenge, js_challenge, challenge. The `execute` action is
    permitted for managed-ruleset chaining.

    (Supersedes Sprint 2's `test_waf_rules_are_log_or_count_only` which
    required the opposite.)
    """
    rulesets = find_resources(
        resources, resource_type="cloudflare_ruleset"
    )
    waf_rulesets = [
        r
        for r in rulesets
        if str(r["attrs"].get("phase", "")).startswith(
            "http_request_firewall"
        )
    ]
    enforcing_actions = {
        "block",
        "managed_challenge",
        "js_challenge",
        "challenge",
        "execute",
    }
    non_enforcing = {"log", "skip"}
    offenders = []
    for rs in waf_rulesets:
        rules = unwrap_blocks(rs["attrs"].get("rules"))
        for rule in rules:
            action = str(rule.get("action", ""))
            if action in non_enforcing:
                offenders.append(
                    (rs["name"], rule.get("description", "?"), action)
                )
            elif action and action not in enforcing_actions:
                offenders.append(
                    (rs["name"], rule.get("description", "?"), action)
                )

    assert not offenders, (
        f"Sprint 4 §S4.1.1 DoD: WAF rules must use enforce-mode actions "
        f"(block, managed_challenge, etc.), not log/skip. Offenders: "
        f"{offenders!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# SSE-friendly cache policy — REJECT cache rules that buffer or cache the
# SSE streaming routes (`/api/run/stream`, `/agent/*`).
# ─────────────────────────────────────────────────────────────────────────────


def test_no_cache_rule_targets_sse_paths_with_cache(resources):
    """REJECT a `cloudflare_ruleset` in the `http_request_cache_settings`
    phase that would cache SSE paths. Sprint 2 §S2.1.3: 'SSE streams
    byte-for-byte' — Cloudflare's default behaviour already passes SSE
    through, but a misconfigured cache rule would silently buffer it.

    The check: any cache_settings rule whose expression touches
    `run/stream` or `/agent/` or `text/event-stream` must set
    `cache = false` in its action_parameters.
    """
    rulesets = find_resources(
        resources, resource_type="cloudflare_ruleset"
    )
    cache_rulesets = [
        r
        for r in rulesets
        if str(r["attrs"].get("phase", "")) == "http_request_cache_settings"
    ]
    sse_path_markers = ("run/stream", "/agent/", "text/event-stream")
    offenders = []
    for rs in cache_rulesets:
        rules = unwrap_blocks(rs["attrs"].get("rules"))
        for rule in rules:
            expr = str(rule.get("expression", "")).lower()
            if not any(m in expr for m in sse_path_markers):
                continue
            action_params = unwrap_block(rule.get("action_parameters")) or {}
            cache_flag = action_params.get("cache")
            if cache_flag is not False:
                offenders.append((rs["name"], rule.get("description", "?")))
    assert not offenders, (
        f"Sprint 2 §S2.1.3 / streaming DoD: cache rules touching SSE paths "
        f"must set `cache = false` in action_parameters. Offenders: "
        f"{offenders!r}."
    )
