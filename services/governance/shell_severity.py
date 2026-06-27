"""Shell-command severity classifier (Layer 2 / Horizontal).

Peer to ``injection_classifier.py``: takes a command *string* and returns a
:class:`SeverityVerdict` — a LOW/MED/HIGH/CRIT tier and the three-band approval
policy (auto / ask / deny) the orchestration PEP gates on. It is the L2,
objective half of the hybrid classifier from
``docs/plans/shell_severity_approval_hitl.plan.md`` (Part A): deterministic tier
tables decide the clear cases; an optional LLM ``judge`` adjudicates *only* the
ambiguous middle the tables can't classify.

Design invariants (the failure-paths-first contract the tests pin):

* **Objective→code, subjective→LLM.** The tables are FP-free and run on every
  commit with no LLM. The judge is **additive and optional** — absent, the
  classifier still returns a band for table-coverable commands and a
  *conservative* default (HIGH/ask, never silent LOW) for the ambiguous band.
* **Fail-closed.** Empty/garbage, judge failure, or an unclassifiable token →
  never AUTO. A table CRITICAL verdict is un-promptable and the judge can NEVER
  lower it (it may only raise severity on the ambiguous band, never downgrade a
  decided table verdict — the dimension-space InjecGuard caveat).

Layer compliance (FOUR_LAYER + GUARDRAILS_DIMENSION_SPACE §C, invariant #4/#7):
imports only stdlib / Pydantic / the ``Severity`` trust type — NO langgraph /
langchain, no upward (``components`` / ``orchestration`` / ``meta``) imports.
"""

from __future__ import annotations

import logging
import shlex
from collections.abc import Callable
from enum import Enum

from pydantic import BaseModel

from services.governance.guardrail_validator import Severity

logger = logging.getLogger("services.governance.shell_severity")


class ApprovalBand(str, Enum):
    """Three-band policy each severity tier maps to (Part A 'three-band')."""

    AUTO = "auto"  # LOW  → run, no prompt
    ASK = "ask"  # MED/HIGH → pause for human approval card
    DENY = "deny"  # CRIT → hard-deny, never promptable


# Severity → band is a frozen, total mapping (one place the policy lives).
_SEVERITY_TO_BAND: dict[Severity, ApprovalBand] = {
    Severity.LOW: ApprovalBand.AUTO,
    Severity.MEDIUM: ApprovalBand.ASK,
    Severity.HIGH: ApprovalBand.ASK,
    Severity.CRITICAL: ApprovalBand.DENY,
}


def band_for(severity: Severity) -> ApprovalBand:
    """Pure severity→band lookup (the policy ceiling)."""
    return _SEVERITY_TO_BAND[severity]


# ─────────────────────────────────────────────────────────────────────
# Deterministic tier tables (the objective half — decidable from bytes).
# Extends services/tools/shell.py ALLOWED/BLOCKED sets into LOW/MED/HIGH/CRIT.
# ─────────────────────────────────────────────────────────────────────

# LOW: read-only / introspection. Auto-run (expands today's 8-cmd allowlist).
_LOW_COMMANDS = frozenset(
    {"ls", "cat", "head", "tail", "grep", "find", "wc", "echo", "pwd"}
)
# python/python3 are LOW *only* without a side-effecting redirect (handled below).
_PYTHON_COMMANDS = frozenset({"python", "python3"})

# MEDIUM: create / modify the filesystem. Ask.
_MEDIUM_COMMANDS = frozenset({"mkdir", "cp", "mv", "touch"})

# HIGH: network / destructive-scoped / privilege-bit. Ask-with-ceiling.
_HIGH_COMMANDS = frozenset({"rm", "curl", "wget", "nc", "chmod", "chown"})

# CRITICAL leading commands — un-approvable regardless of args.
_CRITICAL_COMMANDS = frozenset({"sudo"})

# Redirects that turn an otherwise-read-only command into a side-effecting one.
_WRITE_REDIRECTS = (">", ">>")

# Root / home path roots that escalate a destructive command to CRITICAL. A
# token counts as a root path if it IS one of these or sits under one (prefix),
# so ``/etc/passwd`` and ``/usr/bin`` escalate just like ``/etc`` and ``/usr``.
_ROOT_PATH_ROOTS = ("/etc", "/usr", "/bin", "/var", "/lib", "/sys", "/boot", "/root")
# Bare whole-filesystem / home targets (exact, plus the recursive-glob form).
_WHOLE_FS_TARGETS = ("/", "/*", "~", "~/")
# rm flags that signal a recursive/forced blast.
_RM_DESTRUCTIVE_FLAGS = frozenset({"-rf", "-fr", "-r", "-f"})

# Conservative default for the ambiguous band the tables can't classify and no
# judge resolves: HIGH/ask, never silent LOW (fail-closed).
_AMBIGUOUS_DEFAULT = Severity.HIGH


class SeverityVerdict(BaseModel):
    """Outcome of :func:`classify_severity`.

    ``stage`` records *who* owned the verdict — ``table`` (deterministic) or
    ``judge`` (LLM adjudicated the ambiguous band) — so the carrier can show
    which rail fired, mirroring the InputGuardrail ``decision_stage``.
    """

    command_preview: str
    severity: Severity
    band: ApprovalBand
    reason: str
    stage: str  # "table" | "judge" | "default"


def _is_fork_bomb(command: str) -> bool:
    """Detect the classic ``:(){ :|:& };:`` shell fork bomb (and near variants).

    Fork bombs are function-definition + recursive-call constructs that
    ``shlex`` won't tokenise into a recognisable argv, so we sniff the raw
    bytes for the signature characters before tokenising.
    """
    stripped = command.replace(" ", "")
    return ":(){" in stripped or ":|:&" in stripped


def _touches_root_path(tokens: list[str]) -> bool:
    for tok in tokens:
        if tok in _WHOLE_FS_TARGETS:
            return True
        if tok.startswith(_ROOT_PATH_ROOTS):
            return True
    return False


def _classify_table(command: str) -> SeverityVerdict | None:
    """Deterministic table verdict, or ``None`` if the tables can't decide.

    Returns ``None`` only for an unrecognised leading command (the ambiguous
    band) — every recognised command yields a decided verdict here.
    """
    if _is_fork_bomb(command):
        return _verdict(command, Severity.CRITICAL, "fork-bomb pattern", "table")

    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unbalanced quotes etc. — can't be proven safe.
        return _verdict(command, _AMBIGUOUS_DEFAULT, "unparseable command", "default")
    if not tokens:
        return _verdict(command, _AMBIGUOUS_DEFAULT, "empty command", "default")

    head = tokens[0]
    has_write_redirect = any(r in command for r in _WRITE_REDIRECTS)

    # CRITICAL first (un-promptable). sudo / root-path destructive.
    if head in _CRITICAL_COMMANDS:
        return _verdict(command, Severity.CRITICAL, f"privileged command '{head}'", "table")
    if head == "rm":
        recursive = any(t in _RM_DESTRUCTIVE_FLAGS for t in tokens)
        if _touches_root_path(tokens) and recursive:
            return _verdict(command, Severity.CRITICAL, "recursive rm on root/home path", "table")
        if _touches_root_path(tokens):
            return _verdict(command, Severity.CRITICAL, "rm targeting root/home path", "table")
    if head in _HIGH_COMMANDS and _touches_root_path(tokens):
        # e.g. chmod 777 /etc/passwd — escalate a privilege-bit op on a root path.
        if head in {"chmod", "chown"}:
            return _verdict(
                command, Severity.CRITICAL, f"{head} on root/system path", "table"
            )

    # HIGH: network / destructive-scoped / privilege-bit (non-root).
    if head in _HIGH_COMMANDS:
        return _verdict(command, Severity.HIGH, f"destructive/network command '{head}'", "table")

    # MEDIUM: explicit create/modify, or a write redirect on any command.
    if head in _MEDIUM_COMMANDS:
        return _verdict(command, Severity.MEDIUM, f"filesystem-modify command '{head}'", "table")
    if has_write_redirect:
        return _verdict(command, Severity.MEDIUM, "write redirect (> / >>)", "table")

    # LOW: read-only / introspection (python without a write redirect).
    if head in _LOW_COMMANDS or head in _PYTHON_COMMANDS:
        return _verdict(command, Severity.LOW, f"read-only command '{head}'", "table")

    # Unrecognised leading command → ambiguous band (defer to judge).
    return None


def _verdict(
    command: str, severity: Severity, reason: str, stage: str
) -> SeverityVerdict:
    return SeverityVerdict(
        command_preview=command[:200],
        severity=severity,
        band=band_for(severity),
        reason=reason,
        stage=stage,
    )


def classify_severity(
    command: str,
    *,
    judge: Callable[[str], Severity] | None = None,
) -> SeverityVerdict:
    """Tier ``command`` LOW/MED/HIGH/CRIT and map it to an approval band.

    The deterministic tables decide every recognised command (and CRITICAL is
    un-promptable — the ``judge`` is never consulted for a decided verdict). The
    optional ``judge`` adjudicates only the ambiguous band (unrecognised leading
    command); on judge absence or failure the band defaults conservatively to
    HIGH/ask — never silent LOW (fail-closed).
    """
    table = _classify_table(command)
    if table is not None:
        return table

    # Ambiguous band: the tables can't classify the leading command.
    if judge is None:
        return _verdict(command, _AMBIGUOUS_DEFAULT, "ambiguous; no judge (conservative default)", "default")
    try:
        judged = judge(command)
    except Exception:  # noqa: BLE001 - fail closed, never auto-run on judge error
        logger.warning(
            "shell_severity: judge failed; falling back to conservative default",
            exc_info=True,
        )
        return _verdict(command, _AMBIGUOUS_DEFAULT, "ambiguous; judge error (conservative default)", "default")

    # The judge adjudicates the ambiguous band but does NOT unlock auto-run: a
    # command the tables couldn't recognise is never silently LOW, so a LOW
    # judgement is floored up to the conservative default (fail-closed).
    if judged is Severity.LOW:
        return _verdict(
            command, _AMBIGUOUS_DEFAULT, "ambiguous; judge LOW floored to ask", "judge"
        )
    return _verdict(command, judged, "ambiguous; LLM-adjudicated", "judge")
