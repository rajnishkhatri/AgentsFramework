# infra/dev-tier/features/cloudflare_security.feature
#
# Sprint 2 §S2.1.3 — terraform-compliance BDD scenarios for Cloudflare.
#
# Scope changed 2026-04-23 after first live `tofu apply`: the WAF + Cache
# Rules scenarios were dropped because:
#
#   * WAF custom-rule `log` action is Cloudflare Enterprise-only (not Pro,
#     contrary to the original sprint board assumption).
#   * Cache Rules `set_cache_settings` works on Pro but needs the
#     `Zone:Cache Rules:Edit` API-token scope which wasn't in the
#     original token-creation checklist.
#
# See infra/dev-tier/cloudflare-edge.tf header for the full diagnosis +
# revival path. Sprint 4 §S4.1.1 will re-add WAF as a `block`-action
# ruleset; cache pass-through works correctly under Cloudflare Pro
# defaults today (text/event-stream Content-Type bypasses cache).

Feature: Cloudflare configuration satisfies Sprint 2 §S2.1.3

    Scenario: Pages production branch is main
        Given I have cloudflare_pages_project defined
        Then it must contain production_branch
        And its value must be "main"

    Scenario: Pages project is in the right account
        Given I have cloudflare_pages_project defined
        Then it must contain account_id
