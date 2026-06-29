"""Canonical v3 frontend finding mappers (shared deterministic layer).

WI-6 of ``docs/plan/unified_context_routed_reviewer.plan.md``. Extracted
from ``code_reviewer/frontend/runner.py`` so the unified
``meta/code_reviewer.py`` v3 path can run the TS deterministic predicates
(``applicable_tools`` + ``run_ts_script`` from ``code_reviewer/frontend/tools.py``)
and emit trust-schema :class:`ReviewFinding` objects without importing the
legacy runner's CLI/argparse/eval-capture baggage.

Layering: ``code_reviewer/`` sits outside the four-layer hierarchy (it is a
review tool package), so importing ``trust.review_schema`` here is a downward
dependency and does not violate any architecture invariant.

Legacy note: ``code_reviewer/frontend/runner.py`` keeps its own
``ToolFinding``-based mappers for its ``--rules-only`` report shape; that
runner is superseded by v3 and frozen. ``severity_for_rule`` is shared (the
runner imports it from here) so the severity table stays single-source.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from trust.review_schema import Certificate, ReviewFinding, Severity


def severity_for_rule(rule: str) -> str:
    """Map a tool-emitted rule id to a ReviewReport severity (single source)."""
    crit = {"CSP1", "CSP2", "SBX2"}
    if rule in crit:
        return "critical"
    if rule.startswith("U_") or rule.startswith("HARD"):
        return "warning"
    if rule == "SBX1":
        return "critical"
    if rule.startswith("name~") or rule.startswith("value~"):
        return "critical"  # FE-AP-18
    return "warning"


def _finding(
    *,
    rule_id: str,
    dimension: str,
    severity: str,
    file: str,
    line: int | None,
    description: str,
    fix_suggestion: str,
    tool: str,
) -> ReviewFinding:
    sev = (
        Severity(severity)
        if severity in {"critical", "warning", "info"}
        else Severity.WARNING
    )
    return ReviewFinding(
        rule_id=rule_id,
        dimension=dimension,
        severity=sev,
        file=file,
        line=line,
        description=description,
        fix_suggestion=fix_suggestion,
        confidence=1.0,
        certificate=Certificate(
            premises=[f"[P1] {tool} ({file}{':' + str(line) if line else ''})"],
            traces=[],
            conclusion=f"{rule_id} FAIL -- {description}",
        ),
    )


def _findings_from_check_csp_strict(
    file: str, raw: dict[str, Any]
) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for v in raw.get("violations", []):
        rule = v.get("rule", "CSP")
        out.append(
            _finding(
                rule_id=f"FD3.{rule}",
                dimension="FD3",
                severity=severity_for_rule(rule),
                file=file,
                line=None,
                description=v.get("description", ""),
                fix_suggestion=(
                    "Remove the offending CSP token; rely on the per-request nonce + "
                    "'strict-dynamic' chain documented in architecture_rules.j2."
                ),
                tool="check_csp_strict",
            )
        )
    return out


def _findings_from_check_iframe_sandbox(
    file: str, raw: dict[str, Any]
) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for iframe in raw.get("iframes", []):
        for msg in iframe.get("violations", []):
            rule = msg.split(":", 1)[0].strip()
            out.append(
                _finding(
                    rule_id=f"FD3.{rule}",
                    dimension="FD3",
                    severity="critical",
                    file=file,
                    line=iframe.get("line"),
                    description=msg,
                    fix_suggestion=(
                        "Restrict the iframe sandbox to `allow-scripts` only; remove "
                        "any allow-same-origin / allow-forms / allow-top-navigation tokens."
                    ),
                    tool="check_iframe_sandbox",
                )
            )
    return out


def _findings_from_check_composer_keyboard(
    file: str, raw: dict[str, Any]
) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for v in raw.get("violations", []):
        rule = v.get("rule", "U_KBD")
        out.append(
            _finding(
                rule_id=f"FD2.{rule}",
                dimension="FD2",
                severity="warning",
                file=file,
                line=v.get("line"),
                description=v.get("description", ""),
                fix_suggestion=(
                    "Update the composer to satisfy the U-family contract in "
                    "architecture_rules.j2 (S3.8.5)."
                ),
                tool="check_composer_keyboard",
            )
        )
    return out


def _findings_from_check_secrets(file: str, raw: dict[str, Any]) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for v in raw.get("violations", []):
        out.append(
            _finding(
                rule_id="FD3.SEC1",
                dimension="FD3",
                severity="critical",
                file=file,
                line=v.get("line"),
                description=(
                    f"NEXT_PUBLIC variable {v.get('var')} matches the secret pattern "
                    f"{v.get('matched_pattern')} (FE-AP-18 AUTO-REJECT)."
                ),
                fix_suggestion=(
                    "Move the value out of NEXT_PUBLIC_ and route the credential "
                    "through middleware/ instead (F-R9)."
                ),
                tool="check_secrets_in_public_env",
            )
        )
    return out


def _findings_from_check_jwt(file: str, raw: dict[str, Any]) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for v in raw.get("violations", []):
        out.append(
            _finding(
                rule_id="FD3.SEC2",
                dimension="FD3",
                severity="critical",
                file=file,
                line=v.get("line"),
                description=(
                    f"{v.get('api')} writes auth-shaped value `{v.get('key_or_value')}` "
                    "to browser storage."
                ),
                fix_suggestion=(
                    "Store the JWT in an HttpOnly + Secure + SameSite=Strict cookie set "
                    "by middleware; never localStorage/sessionStorage."
                ),
                tool="check_jwt_storage",
            )
        )
    return out


TOOL_TO_FINDINGS_FN: Mapping[
    str, Callable[[str, dict[str, Any]], list[ReviewFinding]]
] = {
    "check_csp_strict": _findings_from_check_csp_strict,
    "check_iframe_sandbox": _findings_from_check_iframe_sandbox,
    "check_composer_keyboard": _findings_from_check_composer_keyboard,
    "check_secrets_in_public_env": _findings_from_check_secrets,
    "check_jwt_storage": _findings_from_check_jwt,
}


def findings_from_tool(
    tool_name: str, file: str, raw: dict[str, Any]
) -> list[ReviewFinding]:
    """Map a TS tool's raw JSON output to trust-schema ReviewFindings.

    Returns ``[]`` when the tool has no v3 mapper (callers surface that as a
    validation_log / gaps entry, not an error).
    """
    fn = TOOL_TO_FINDINGS_FN.get(tool_name)
    if fn is None:
        return []
    return fn(file, raw)


__all__ = [
    "severity_for_rule",
    "findings_from_tool",
    "TOOL_TO_FINDINGS_FN",
]
