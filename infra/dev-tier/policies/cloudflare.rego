# infra/dev-tier/policies/cloudflare.rego
#
# Conftest/OPA policy for Sprint 2 §S2.1.3 — Cloudflare WAF + cache.

package cloudflare

import future.keywords.contains
import future.keywords.if
import future.keywords.in

ruleset_attrs contains attrs if {
    some name
    attrs := input.resource.cloudflare_ruleset[name][_]
}

# ── WAF: log/count mode only (Sprint 2; Sprint 4 §S4.1.1 flips to block) ──

forbidden_actions := {"block", "managed_challenge", "js_challenge", "challenge"}

deny contains msg if {
    some attrs in ruleset_attrs
    startswith(attrs.phase, "http_request_firewall")
    some rule in attrs.rules
    rule.action in forbidden_actions
    msg := sprintf(
        "Sprint 2 §S2.1.3: WAF rule action %v is forbidden in count-mode sprint (rule: %v).",
        [rule.action, rule.description],
    )
}

# ── Cache: SSE paths must NOT be cached ──────────────────────────────────

sse_markers := ["run/stream", "/agent/", "text/event-stream"]

deny contains msg if {
    some attrs in ruleset_attrs
    attrs.phase == "http_request_cache_settings"
    some rule in attrs.rules
    expr := lower(rule.expression)
    some m in sse_markers
    contains(expr, m)
    some ap in rule.action_parameters
    ap.cache != false
    msg := sprintf(
        "Sprint 2 §S2.1.3: cache rule on SSE path must set cache=false (rule: %v).",
        [rule.description],
    )
}
