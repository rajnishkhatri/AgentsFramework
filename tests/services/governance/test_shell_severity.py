"""L2 severity classifier — failure-mode matrix (Protocol B, contract-driven).

Tests the deterministic half of ``services/governance/shell_severity.py``: a
``classify_severity(command)`` that tiers a shell command LOW/MED/HIGH/CRIT and
maps each tier to a three-band policy (auto / ask / deny) — the objective,
FP-free table that runs on every commit with no LLM (Anti-Pattern 3/5).

Per ``research/tdd_agentic_systems_prompt.md`` Pattern 11, the matrix is
parametrized over ``(command → expected band/severity)`` with the **rejection
rows first** (every CRITICAL/deny vector), then the ask band, then the auto
band. We assert the *band/severity*, never the model, and we assert behaviour
via known vectors rather than re-deriving the table (TAP-1 anti-tautology).
"""

from __future__ import annotations

import pytest

from services.governance.guardrail_validator import Severity
from services.governance.shell_severity import (
    ApprovalBand,
    SeverityVerdict,
    classify_severity,
)

# ─────────────────────────────────────────────────────────────────────
# Rejection rows FIRST: CRITICAL / hard-deny, un-promptable (failure paths).
# ─────────────────────────────────────────────────────────────────────
CRITICAL_DENY = [
    "rm -rf /",
    "rm -rf /*",
    "rm -fr /",
    "sudo rm foo",
    "sudo apt-get install x",
    ":(){ :|:& };:",  # fork bomb
    "chmod 777 /etc/passwd",
    "rm -rf /usr",
    "rm -rf ~",
]

# ─────────────────────────────────────────────────────────────────────
# HIGH band — network / destructive-scoped, ask-with-ceiling.
# ─────────────────────────────────────────────────────────────────────
HIGH_ASK = [
    "rm foo.txt",
    "rm -f build/out",
    "curl https://example.com",
    "wget https://example.com/x",
    "nc -l 8080",
    "chmod +x script.sh",
    "chown me file",
]

# ─────────────────────────────────────────────────────────────────────
# MEDIUM band — create / modify, ask.
# ─────────────────────────────────────────────────────────────────────
MEDIUM_ASK = [
    "mkdir build",
    "cp a b",
    "mv a b",
    "touch newfile",
    "echo hello > out.txt",
    "echo hi >> log.txt",
]

# ─────────────────────────────────────────────────────────────────────
# LOW band — read-only, auto-run (expands today's allowlist).
# ─────────────────────────────────────────────────────────────────────
LOW_AUTO = [
    "ls -la",
    "cat file.txt",
    "head -n 5 file",
    "tail -f log",
    "grep foo file",
    "find . -name '*.py'",
    "wc -l file",
    "echo hello",
    "pwd",
    "python3 --version",
    "python -c 'print(1+1)'",
]


class TestSeverityMatrix:
    @pytest.mark.parametrize("command", CRITICAL_DENY)
    def test_critical_commands_are_deny_band(self, command: str) -> None:
        verdict = classify_severity(command)
        assert verdict.severity is Severity.CRITICAL, verdict
        assert verdict.band is ApprovalBand.DENY, verdict

    @pytest.mark.parametrize("command", HIGH_ASK)
    def test_high_commands_are_ask_band(self, command: str) -> None:
        verdict = classify_severity(command)
        assert verdict.severity is Severity.HIGH, verdict
        assert verdict.band is ApprovalBand.ASK, verdict

    @pytest.mark.parametrize("command", MEDIUM_ASK)
    def test_medium_commands_are_ask_band(self, command: str) -> None:
        verdict = classify_severity(command)
        assert verdict.severity is Severity.MEDIUM, verdict
        assert verdict.band is ApprovalBand.ASK, verdict

    @pytest.mark.parametrize("command", LOW_AUTO)
    def test_low_commands_are_auto_band(self, command: str) -> None:
        verdict = classify_severity(command)
        assert verdict.severity is Severity.LOW, verdict
        assert verdict.band is ApprovalBand.AUTO, verdict


class TestVerdictContract:
    def test_verdict_carries_a_reason(self) -> None:
        verdict = classify_severity("rm -rf /")
        assert isinstance(verdict, SeverityVerdict)
        assert verdict.reason  # non-empty provenance for the carrier

    def test_empty_command_is_fail_closed_deny(self) -> None:
        # An empty/garbage command can't be proven safe → never auto-run.
        verdict = classify_severity("")
        assert verdict.band is not ApprovalBand.AUTO, verdict

    def test_unparseable_command_is_fail_closed(self) -> None:
        # Unbalanced quotes make shlex.split raise → can't tokenise, can't prove
        # safe, so it must NOT auto-run (the conservative-default fail-closed
        # branch). A read head ('echo') must not rescue an unparseable body.
        verdict = classify_severity('echo "unterminated')
        assert verdict.band is not ApprovalBand.AUTO, verdict
        assert verdict.severity is not Severity.LOW, verdict

    def test_write_redirect_escalates_a_read_only_command_to_medium(self) -> None:
        # The redirect itself — not the leading command — is what escalates: a
        # read-only `cat` with a `>` writes a file, so it tiers MEDIUM/ask, not
        # LOW/auto. Isolates the redirect branch from the command-name branch.
        verdict = classify_severity("cat secret.txt > out.txt")
        assert verdict.severity is Severity.MEDIUM, verdict
        assert verdict.band is ApprovalBand.ASK, verdict


class TestFailClosedDegrade:
    """Judge-unavailable degrade: table-coverable commands still classify;
    table-ambiguous commands get a conservative default (HIGH/ask), never a
    silent LOW (fail-closed, dimension-space 'additive and optional')."""

    def test_table_covered_command_classifies_without_judge(self) -> None:
        # No judge passed → deterministic-only still returns the right band.
        verdict = classify_severity("ls -la", judge=None)
        assert verdict.severity is Severity.LOW
        assert verdict.band is ApprovalBand.AUTO
        assert verdict.stage == "table"

    def test_ambiguous_command_defaults_conservative_without_judge(self) -> None:
        # An unknown leading command the tables can't classify must NOT auto-run.
        verdict = classify_severity("frobnicate --wibble", judge=None)
        assert verdict.band in (ApprovalBand.ASK, ApprovalBand.DENY), verdict
        assert verdict.severity is not Severity.LOW, verdict

    def test_ambiguous_command_consults_judge_when_present(self) -> None:
        calls: list[str] = []

        def judge(command: str) -> Severity:
            calls.append(command)
            return Severity.MEDIUM

        verdict = classify_severity("frobnicate --wibble", judge=judge)
        assert calls == ["frobnicate --wibble"]
        assert verdict.stage == "judge"
        assert verdict.severity is Severity.MEDIUM
        assert verdict.band is ApprovalBand.ASK

    def test_judge_can_raise_but_never_lowers_a_table_critical(self) -> None:
        # The judge must not be a trigger-word shortcut that downgrades a table
        # CRITICAL verdict (dimension-space InjecGuard caveat).
        def lenient_judge(command: str) -> Severity:
            return Severity.LOW

        verdict = classify_severity("rm -rf /", judge=lenient_judge)
        assert verdict.severity is Severity.CRITICAL, verdict
        assert verdict.band is ApprovalBand.DENY, verdict
        # The judge should not even be consulted for a decided table verdict.
        assert verdict.stage == "table"

    def test_judge_failure_falls_back_to_conservative_default(self) -> None:
        def broken_judge(command: str) -> Severity:
            raise RuntimeError("judge offline")

        verdict = classify_severity("frobnicate --wibble", judge=broken_judge)
        assert verdict.band in (ApprovalBand.ASK, ApprovalBand.DENY), verdict
        assert verdict.severity is not Severity.LOW, verdict
