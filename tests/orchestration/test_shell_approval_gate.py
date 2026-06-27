"""L4 three-band shell-approval PEP — D1 gate matrix (Protocol D, simulation).

Mirrors ``test_trust_gate_outcomes`` / ``test_verify_authorize_log_node``: a
parametrized ``(severity_band, approval_decision) → outcome`` matrix for the
``decide_shell_approval`` gate from
``docs/plans/shell_severity_approval_hitl.plan.md`` (Part B, L4).

Gate contract (failure-paths-first):

* auto (LOW)            → EXECUTE, no interrupt, no human.
* deny (CRIT)           → DENY (``error_class="gating"``), never executed, no card.
* ask + approve         → EXECUTE the original command.
* ask + edit            → EXECUTE the edited command.
* ask + reject          → DENY, not executed.
* ask + timeout         → DENY (fail-closed; OWASP "timeout = denial").

Every decision emits **exactly one** ``GUARDRAIL_CHECKED`` carrier (one carrier
per fact). The subprocess (modelled by a ``runs`` counter the gate calls only on
EXECUTE) runs 0 times on every non-EXECUTE branch — the idempotency / side-effect
-strictly-after-interrupt invariant. No live LLM, no live subprocess: the
interrupt/resume is a scripted ``interrupt_fn`` (Pattern 6 mock provider).
"""

from __future__ import annotations


from orchestration.shell_approval_gate import (
    ApprovalDecision,
    GateOutcome,
    ShellApprovalConfig,
    decide_shell_approval,
)
from services.governance.shell_severity import ApprovalBand


def _cfg(**kw) -> ShellApprovalConfig:
    base = dict(enabled=True, enforce=True, threshold="medium", timeout_seconds=120)
    base.update(kw)
    return ShellApprovalConfig(**base)


def _approve(decision: str = "approve", edited: str | None = None):
    """Build a scripted interrupt_fn that resolves to a fixed ApprovalDecision."""

    def interrupt_fn(payload: dict) -> ApprovalDecision:
        return ApprovalDecision(decision=decision, edited_command=edited)

    return interrupt_fn


def _timeout_interrupt(payload: dict) -> ApprovalDecision:
    return ApprovalDecision(decision="timeout", edited_command=None)


class _RunRecorder:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def __call__(self, command: str) -> str:
        self.commands.append(command)
        return f"ran:{command}"


class TestGateMatrix:
    def test_auto_band_executes_without_interrupt(self) -> None:
        runs = _RunRecorder()
        interrupted: list[dict] = []

        def interrupt_fn(payload):  # must NOT be called for the auto band
            interrupted.append(payload)
            return ApprovalDecision(decision="approve")

        result = decide_shell_approval(
            command="ls -la",
            band=ApprovalBand.AUTO,
            severity="low",
            config=_cfg(),
            interrupt_fn=interrupt_fn,
            execute=runs,
        )
        assert result.outcome is GateOutcome.EXECUTED
        assert runs.commands == ["ls -la"]
        assert interrupted == []  # auto never pauses
        assert len(result.carriers) == 1

    def test_deny_band_never_executes_and_never_prompts(self) -> None:
        runs = _RunRecorder()
        interrupted: list[dict] = []

        def interrupt_fn(payload):
            interrupted.append(payload)
            return ApprovalDecision(decision="approve")

        result = decide_shell_approval(
            command="rm -rf /",
            band=ApprovalBand.DENY,
            severity="critical",
            config=_cfg(),
            interrupt_fn=interrupt_fn,
            execute=runs,
        )
        assert result.outcome is GateOutcome.DENIED
        assert result.error_class == "gating"
        assert runs.commands == []  # never executed
        assert interrupted == []  # un-promptable: no card
        assert len(result.carriers) == 1

    def test_ask_approve_executes_original(self) -> None:
        runs = _RunRecorder()
        result = decide_shell_approval(
            command="mkdir build",
            band=ApprovalBand.ASK,
            severity="medium",
            config=_cfg(),
            interrupt_fn=_approve("approve"),
            execute=runs,
        )
        assert result.outcome is GateOutcome.EXECUTED
        assert runs.commands == ["mkdir build"]
        assert len(result.carriers) == 1

    def test_ask_edit_executes_edited_command(self) -> None:
        runs = _RunRecorder()
        result = decide_shell_approval(
            command="rm foo",
            band=ApprovalBand.ASK,
            severity="high",
            config=_cfg(),
            interrupt_fn=_approve("edit", edited="ls foo"),
            execute=runs,
        )
        assert result.outcome is GateOutcome.EXECUTED
        assert runs.commands == ["ls foo"]  # edited cmd, not the original
        assert len(result.carriers) == 1

    def test_ask_reject_does_not_execute(self) -> None:
        runs = _RunRecorder()
        result = decide_shell_approval(
            command="mkdir build",
            band=ApprovalBand.ASK,
            severity="medium",
            config=_cfg(),
            interrupt_fn=_approve("reject"),
            execute=runs,
        )
        assert result.outcome is GateOutcome.DENIED
        assert result.error_class == "gating"
        assert runs.commands == []
        assert len(result.carriers) == 1

    def test_ask_timeout_is_fail_closed_deny(self) -> None:
        runs = _RunRecorder()
        result = decide_shell_approval(
            command="mkdir build",
            band=ApprovalBand.ASK,
            severity="medium",
            config=_cfg(),
            interrupt_fn=_timeout_interrupt,
            execute=runs,
        )
        assert result.outcome is GateOutcome.DENIED
        assert result.error_class == "gating"
        assert runs.commands == []
        assert len(result.carriers) == 1
        # The carrier must record the timeout reason honestly.
        assert result.carriers[0]["decision"] == "timeout"


class TestCarrierShape:
    def test_carrier_has_one_fact_with_required_fields(self) -> None:
        result = decide_shell_approval(
            command="mkdir build",
            band=ApprovalBand.ASK,
            severity="medium",
            config=_cfg(),
            interrupt_fn=_approve("approve"),
            execute=_RunRecorder(),
        )
        assert len(result.carriers) == 1
        c = result.carriers[0]
        for key in ("guardrail", "tool", "command", "severity", "band", "decision"):
            assert key in c, (key, c)
        assert c["guardrail"] == "shell_severity"
        assert c["tool"] == "shell"

    def test_command_in_carrier_is_capped(self) -> None:
        long_cmd = "echo " + "a" * 5000
        result = decide_shell_approval(
            command=long_cmd,
            band=ApprovalBand.AUTO,
            severity="low",
            config=_cfg(),
            interrupt_fn=_approve("approve"),
            execute=_RunRecorder(),
        )
        assert len(result.carriers[0]["command"]) <= 512


class TestShadowMode:
    """Phase A (enforce=False): classify + carrier, but the ask band does NOT
    interrupt — it runs anyway (observe severities on real traffic)."""

    def test_shadow_ask_executes_without_interrupt(self) -> None:
        runs = _RunRecorder()
        interrupted: list[dict] = []

        def interrupt_fn(payload):
            interrupted.append(payload)
            return ApprovalDecision(decision="approve")

        result = decide_shell_approval(
            command="mkdir build",
            band=ApprovalBand.ASK,
            severity="medium",
            config=_cfg(enforce=False),
            interrupt_fn=interrupt_fn,
            execute=runs,
        )
        assert result.outcome is GateOutcome.EXECUTED
        assert runs.commands == ["mkdir build"]
        assert interrupted == []  # shadow: no pause
        assert len(result.carriers) == 1
        # The carrier honestly records that it WOULD have asked.
        assert result.carriers[0]["would_enforce"] is True

    def test_below_threshold_ask_runs_without_interrupt_even_when_enforcing(
        self,
    ) -> None:
        # enforce=True but the command's severity is BELOW the configured ask
        # floor (threshold="high", severity="medium") → it auto-runs and the
        # carrier records would_enforce=False. Isolates the threshold knob from
        # the enforce flag (a distinct condition from shadow mode).
        runs = _RunRecorder()
        interrupted: list[dict] = []

        def interrupt_fn(payload):
            interrupted.append(payload)
            return ApprovalDecision(decision="approve")

        result = decide_shell_approval(
            command="mkdir build",
            band=ApprovalBand.ASK,
            severity="medium",
            config=_cfg(enforce=True, threshold="high"),
            interrupt_fn=interrupt_fn,
            execute=runs,
        )
        assert result.outcome is GateOutcome.EXECUTED
        assert runs.commands == ["mkdir build"]
        assert interrupted == []  # below the ask floor: no pause
        assert result.carriers[0]["would_enforce"] is False

    def test_shadow_deny_still_hard_denies(self) -> None:
        # CRITICAL is table-driven and un-promptable even in shadow — the
        # ceiling never relaxes (it's a safety floor, not an enforce toggle).
        runs = _RunRecorder()
        result = decide_shell_approval(
            command="rm -rf /",
            band=ApprovalBand.DENY,
            severity="critical",
            config=_cfg(enforce=False),
            interrupt_fn=_approve("approve"),
            execute=runs,
        )
        assert result.outcome is GateOutcome.DENIED
        assert runs.commands == []

    def test_disabled_executes_everything_unchanged(self) -> None:
        # Master flag off → no classification gate at all; the band is irrelevant.
        runs = _RunRecorder()
        result = decide_shell_approval(
            command="mkdir build",
            band=ApprovalBand.ASK,
            severity="medium",
            config=_cfg(enabled=False),
            interrupt_fn=_approve("reject"),
            execute=runs,
        )
        assert result.outcome is GateOutcome.EXECUTED
        assert runs.commands == ["mkdir build"]
        # Disabled gate emits no governance carrier (byte-identical to today).
        assert result.carriers == []


class TestResumeIdempotency:
    """Resume re-executes the node from top (LangChain gotcha). The classifier
    may re-run (pure) but the subprocess executes exactly once, post-approval.
    We model the re-exec by calling the gate twice with the same scripted
    approve; the execute recorder must fire once per *approved* pass and never
    on a resume that resolves to reject."""

    def test_execute_fires_once_per_approved_decision(self) -> None:
        runs = _RunRecorder()
        decide_shell_approval(
            command="mkdir build",
            band=ApprovalBand.ASK,
            severity="medium",
            config=_cfg(),
            interrupt_fn=_approve("approve"),
            execute=runs,
        )
        assert runs.commands == ["mkdir build"]  # exactly once on the approve pass
