###############################################################################
# infra/dev-tier/cloudflare-edge.tf — Sprint 2 §S2.1.3 (edge half)
#
# Configures the Cloudflare zone: a `data "cloudflare_zone"` lookup so
# the rest of the stack and ops scripts can read zone metadata.
#
# IMPORTANT — Sprint board entitlement erratum (discovered 2026-04-23 during
# the first apply against the live Pro zone):
#
#   * Custom WAF rules with action `log` (the basis of the board's
#     "WAF in count mode for 24h" acceptance criterion) require Cloudflare
#     **Enterprise**, NOT Pro. The Pro plan unlocks custom WAF rules but
#     only with enforcing actions (`block`, `challenge`, `js_challenge`,
#     `managed_challenge`, `skip`). The first apply errored with
#     "not entitled to use the log action".
#
#   * Custom Cache Rules in the `http_request_cache_settings` phase work
#     on Pro+ but require an additional API-token scope
#     (`Zone:Cache Rules:Edit`) that wasn't in the original Sprint 0
#     token-creation checklist. Failed with "request is not authorized".
#
# Decision: defer both rulesets to a follow-up sprint. Cloudflare's
# auto-applied "Cloudflare Free Managed Ruleset" is still active on the
# Pro zone (provides DDoS + basic OWASP coverage), so the zone is NOT
# unprotected. SSE pass-through works correctly under Cloudflare's
# default behaviour: text/event-stream Content-Type is recognised and
# bypasses cache + buffering automatically — verified by the Cloudflare
# docs and reproduced via curl test in the apply runbook.
#
# Sprint 4 §S4.1.1 ("WAF moved from count mode to enforce mode") becomes:
#   1. Add `Zone:Cache Rules:Edit` scope to the API token (~30 sec).
#   2. Re-add a `cloudflare_ruleset` for cache_settings on SSE paths.
#   3. Re-add a `cloudflare_ruleset` for WAF with action = "block" on
#      the heuristic patterns (skip the 24h observation window since
#      Pro can't provide it; rely on the manual review that Sprint 4
#      already requires).
#
# The original ruleset HCL is preserved at git SHA <next commit>~1 for
# easy revival when the entitlement gap closes.
###############################################################################

# ── Zone lookup ────────────────────────────────────────────────────────────
#
# Used by ops scripts (`terraform output cloudflare_zone_name`) and to
# confirm at plan-time that the zone still exists / is on the expected
# plan tier. The actual ruleset/page-rule resources have been deferred
# (see header) but the data source is intentionally kept so the Sprint 4
# revival doesn't have to re-add it.

data "cloudflare_zone" "agent" {
  zone_id = var.cloudflare_zone_id
}

# ── WAF custom ruleset (Sprint 4 §S4.1.1) ────────────────────────────────
#
# Revived from Sprint 2's deferred WAF config. The original plan called
# for 24h in count/log mode before flipping to enforce, but Cloudflare
# Pro doesn't support the `log` action on custom WAF rules (requires
# Enterprise). Sprint 4 goes straight to `block` action. The auto-
# applied "Cloudflare Free Managed Ruleset" has been providing baseline
# DDoS + OWASP coverage since Sprint 2; these custom rules add
# heuristic patterns for the agent-specific attack surface.

resource "cloudflare_ruleset" "waf_custom" {
  zone_id = var.cloudflare_zone_id
  name    = "Agent WAF custom rules (Sprint 4)"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  # Rule 1: Block requests with anomalous User-Agent patterns commonly
  # seen in automated scanners targeting API endpoints.
  rules {
    action      = "block"
    expression  = "(http.user_agent contains \"sqlmap\") or (http.user_agent contains \"nikto\") or (http.user_agent contains \"nmap\")"
    description = "Block known scanner User-Agents"
    enabled     = true
  }

  # Rule 2: Block requests attempting path traversal on API routes.
  rules {
    action      = "block"
    expression  = "(http.request.uri.path contains \"..\" and starts_with(http.request.uri.path, \"/api/\"))"
    description = "Block path traversal on API routes"
    enabled     = true
  }

  # Rule 3: Rate-limit style block for oversized request bodies on
  # non-streaming routes. SSE streaming routes (/api/run/stream) are
  # excluded because they legitimately have long-lived connections.
  rules {
    action      = "block"
    expression  = "(http.request.body.size gt 1048576 and not starts_with(http.request.uri.path, \"/api/run/stream\"))"
    description = "Block oversized request bodies (>1MB, excludes SSE)"
    enabled     = true
  }
}
