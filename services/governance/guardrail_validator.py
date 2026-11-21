"""Deterministic guardrail validator: regex-based PII / API-key / length checks.

NO langgraph or langchain imports allowed. Uses only ``pydantic``, ``re``, stdlib.

Defines the :class:`GuardRail` configuration model, the :class:`ValidationResult`
shape and the :class:`GuardRailValidator` runner. Built-in regex factories
(``pii_rules``, ``api_key_rules``, ``length_rule``) return ready-to-use
``GuardRail`` instances with canonical severity and fail action settings.

Pattern: Services layer (Layer 2) — provides a deterministic safety primitive
that the OutputGuardrail (Workstream D) composes.
"""

from __future__ import annotations

import logging
import re
from collections import deque
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger("services.governance.guardrail_validator")

# A validator is built once per graph and reused across requests, so its
# per-check trace keeps only the most recent entries instead of growing forever.
MAX_TRACE_ENTRIES = 1000


class FailAction(str, Enum):
    BLOCK = "block"
    WARN = "warn"
    REDACT = "redact"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GuardRail(BaseModel):
    """Declarative validator configuration.

    A guardrail's ``pattern`` is compiled once. ``match_redaction`` is the
    replacement string used when ``fail_action == REDACT``.
    """

    name: str
    description: str
    pattern: str
    fail_action: FailAction = FailAction.BLOCK
    severity: Severity = Severity.HIGH
    flags: int = 0
    match_redaction: str = "[REDACTED]"
    max_length: int | None = None
    # When True, a regex match only counts if its digits pass the Luhn
    # checksum — keeps timestamps and order ids from reading as card numbers.
    luhn_check: bool = False


def luhn_valid(candidate: str) -> bool:
    """Whether the digits in ``candidate`` satisfy the Luhn checksum."""
    digits = [int(ch) for ch in candidate if ch.isdigit()]
    if not digits:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


class ValidationResult(BaseModel):
    guardrail_name: str
    passed: bool
    details: str
    severity: Severity
    fail_action: FailAction
    matches: list[str] = Field(default_factory=list)


class GuardRailValidator:
    """Runs a list of :class:`GuardRail` rules against content strings.

    Maintains a bounded ``trace`` of the most recent checks for explainability.
    Call :meth:`validate` to get per-rule results and :meth:`redact` to
    apply any ``REDACT``-type guardrails that produced matches.
    """

    def __init__(self, rules: list[GuardRail]) -> None:
        self._rules = rules
        self._compiled: list[tuple[GuardRail, re.Pattern[str]]] = [
            (rule, re.compile(rule.pattern, rule.flags)) for rule in rules
        ]
        self._trace: deque[dict] = deque(maxlen=MAX_TRACE_ENTRIES)

    @property
    def rules(self) -> list[GuardRail]:
        return list(self._rules)

    def validate(self, content: str) -> list[ValidationResult]:
        """Run every rule against ``content`` and return per-rule results."""
        results: list[ValidationResult] = []
        for rule, regex in self._compiled:
            matches = regex.findall(content) if content else []
            if rule.luhn_check:
                matches = [m for m in matches if luhn_valid(str(m))]

            length_violation = (
                rule.max_length is not None and len(content or "") > rule.max_length
            )
            failed = bool(matches) or length_violation

            if length_violation and not matches:
                details = f"Content length {len(content)} exceeds max_length {rule.max_length}"
            elif matches:
                details = f"{len(matches)} match(es) for rule '{rule.name}'"
            else:
                details = "No matches."

            result = ValidationResult(
                guardrail_name=rule.name,
                passed=not failed,
                details=details,
                severity=rule.severity,
                fail_action=rule.fail_action,
                matches=[str(m) for m in matches],
            )
            results.append(result)

            self._trace.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "rule_name": rule.name,
                    "passed": not failed,
                    "severity": rule.severity.value,
                    "fail_action": rule.fail_action.value,
                    "match_count": len(matches),
                    "length_violation": length_violation,
                }
            )

            if failed:
                logger.info(
                    "Guardrail '%s' failed: %s",
                    rule.name,
                    details,
                    extra={
                        "rule": rule.name,
                        "severity": rule.severity.value,
                        "fail_action": rule.fail_action.value,
                    },
                )

        return results

    def redact(self, content: str) -> str:
        """Apply any REDACT-type rules to ``content``.

        Rules with ``fail_action=REDACT`` replace every match with their
        ``match_redaction`` string. Other actions leave content unchanged here
        (the caller decides whether to block based on :meth:`validate`).
        """
        redacted = content
        for rule, regex in self._compiled:
            if rule.fail_action == FailAction.REDACT:
                redacted = regex.sub(rule.match_redaction, redacted)
        return redacted

    def get_validation_trace(self) -> list[dict]:
        """Return a copy of the most recent ``MAX_TRACE_ENTRIES`` checks."""
        return list(self._trace)

    def reset_trace(self) -> None:
        self._trace.clear()


# ─────────────────────────────────────────────────────────────────────
# Built-in rule factories
# ─────────────────────────────────────────────────────────────────────


def pii_rules() -> list[GuardRail]:
    """Return the canonical PII rule set (SSN, credit card, email, phone)."""
    return [
        GuardRail(
            name="pii.ssn",
            description="US Social Security Number (###-##-####)",
            pattern=r"\b\d{3}-\d{2}-\d{4}\b",
            severity=Severity.CRITICAL,
            fail_action=FailAction.BLOCK,
        ),
        GuardRail(
            name="pii.credit_card",
            description="Credit card number (13-19 digits, optional groups)",
            pattern=r"\b(?:\d[ -]*?){13,19}\b",
            severity=Severity.CRITICAL,
            fail_action=FailAction.BLOCK,
            luhn_check=True,
        ),
        GuardRail(
            name="pii.email",
            description="Email address",
            pattern=r"\b[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            severity=Severity.MEDIUM,
            fail_action=FailAction.REDACT,
        ),
        GuardRail(
            name="pii.phone",
            description="US phone (###) ###-#### or ###-###-####",
            pattern=r"(?:\(\d{3}\)\s?|\b\d{3}-)\d{3}-\d{4}\b",
            severity=Severity.MEDIUM,
            fail_action=FailAction.REDACT,
        ),
    ]


def api_key_rules() -> list[GuardRail]:
    """Return API-key leakage rules (OpenAI, AWS access key, GitHub PAT)."""
    return [
        GuardRail(
            name="api_key.openai",
            description="OpenAI-style secret key (sk-... / sk-proj-...)",
            # The optional ``proj-`` segment plus an 8-char floor catches
            # short project keys (e.g. sk-proj-abc123456789) that the old
            # {20,} quantifier silently let through — see walkthrough G1.2.
            # A key body either contains a digit or opens with an unbroken run
            # of 20+ characters, and the token must not be the tail of a longer
            # hyphenated word — so ``sk-learn-contrib`` and
            # ``task-sk-learn-pipeline`` are not withheld as leaked secrets.
            pattern=(
                r"(?<![\w-])sk-(?:proj-)?"
                r"(?:(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{8,}"
                r"|[A-Za-z0-9_]{20,}[A-Za-z0-9_-]*)\b"
            ),
            severity=Severity.CRITICAL,
            fail_action=FailAction.BLOCK,
        ),
        GuardRail(
            name="api_key.aws_access",
            description="AWS Access Key ID (AKIA...)",
            pattern=r"\bAKIA[0-9A-Z]{16}\b",
            severity=Severity.CRITICAL,
            fail_action=FailAction.BLOCK,
        ),
        GuardRail(
            name="api_key.github_pat",
            description="GitHub personal access token (ghp_...)",
            pattern=r"\bghp_[A-Za-z0-9]{36}\b",
            severity=Severity.CRITICAL,
            fail_action=FailAction.BLOCK,
        ),
    ]


def length_rule(max_length: int = 4000) -> GuardRail:
    return GuardRail(
        name="content.length",
        description=f"Content must be <= {max_length} characters",
        pattern=r"(?!x)x",  # never matches; gates on max_length
        severity=Severity.LOW,
        fail_action=FailAction.WARN,
        max_length=max_length,
    )


__all__ = [
    "FailAction",
    "Severity",
    "GuardRail",
    "ValidationResult",
    "GuardRailValidator",
    "MAX_TRACE_ENTRIES",
    "luhn_valid",
    "pii_rules",
    "api_key_rules",
    "length_rule",
]
