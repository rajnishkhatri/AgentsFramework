"""Capability -> regression graduation + the Langfuse -> goldset feedback bridge.

Pyramid layer:   L1 Deterministic -- pure functions, no I/O, no LLM. (The only
                 logging is the optional bridge emit, which delegates to
                 ``services.eval_capture``; the graduation MATH does no I/O.)
Architecture:    Horizontal (services/governance/). No imports from
                 ``components/``, ``orchestration/``, ``langgraph``, or
                 ``langchain``. The Langfuse bridge takes an already-harvested
                 record dict (the harvesting -- a network read -- lives in the
                 caller / a script), so this module stays framework-clean.

Plan: docs/plan/agentic_engineering_harness_adoption.plan.md Track B-4.

The two-tier eval lifecycle (the playbook's "capability vs regression" split):

* **CAPABILITY** evals probe a NOT-yet-reliable ability. They are EXPECTED to
  fail sometimes; you run them to discover whether a change moved the needle. A
  low pass rate here is information, not an alarm.
* **REGRESSION** evals are FROZEN, formerly-capability evals that the system now
  passes reliably. They run continuously and a drop below the floor (~100%) is a
  real regression -- the alarm.

``graduate`` is the promotion rule: a capability eval whose observed pass rate
clears ``min_pass_rate`` over at least ``min_runs`` independent runs has earned a
place in the regression suite. ``regression_floor_violations`` is the
continuously-run gate on the frozen tier.

The feedback loop: production Langfuse traces (harvested via ``eval_capture``'s
record shape) become *candidate* goldset rows -- new capability evals seeded from
real failures -- which, once they stabilize, graduate into regression. This
module supplies the deterministic seams; the network harvest is a caller step.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

# Default graduation thresholds (plan Track B-4). A capability eval graduates
# when it passes >= 95% over >= 5 runs; the regression suite floor is 100% (any
# miss on a FROZEN eval is a regression). Override per corpus risk tolerance.
DEFAULT_MIN_PASS_RATE = 0.95
DEFAULT_MIN_RUNS = 5
DEFAULT_REGRESSION_FLOOR = 1.0


class EvalTier(str, Enum):
    """The two-tier eval lifecycle. ``str`` mixin so a row's ``tier`` field can be
    a plain string on disk and still compare equal to the enum member."""

    CAPABILITY = "capability"
    REGRESSION = "regression"


def classify_tier(row: Mapping[str, object]) -> EvalTier:
    """Read a row's declared tier, defaulting to CAPABILITY.

    An untagged row is treated as CAPABILITY: a new/unknown eval has NOT earned
    regression status, so it must never gate a deploy at the 100% floor by
    accident (fail-safe direction -- the conservative default cannot raise a
    false regression alarm).
    """
    raw = row.get("tier")
    if raw is None:
        return EvalTier.CAPABILITY
    try:
        return EvalTier(str(raw).lower())
    except ValueError as exc:
        raise ValueError(
            f"row {row.get('case', row.get('id', '?'))!r} has unknown tier "
            f"{raw!r}; expected one of {[t.value for t in EvalTier]}"
        ) from exc


@dataclass(frozen=True)
class GraduationCandidate:
    """A capability eval evaluated for promotion to the regression tier."""

    case: str
    pass_rate: float
    runs: int
    graduates: bool
    reason: str


def graduate(
    rows: Sequence[Mapping[str, object]],
    pass_rates: Mapping[str, tuple[int, int]],
    *,
    min_pass_rate: float = DEFAULT_MIN_PASS_RATE,
    min_runs: int = DEFAULT_MIN_RUNS,
) -> list[GraduationCandidate]:
    """Evaluate which CAPABILITY evals have earned regression status.

    ``pass_rates`` maps ``case -> (successes, runs)``. A capability eval
    graduates when ``runs >= min_runs`` AND ``successes / runs >= min_pass_rate``.
    Rows already in the regression tier are skipped (nothing to graduate). A
    capability row with no run data is reported as ``graduates=False`` with an
    explicit "insufficient data" reason -- never silently dropped (AP-6).
    """
    out: list[GraduationCandidate] = []
    for row in rows:
        if classify_tier(row) is EvalTier.REGRESSION:
            continue
        case = str(row.get("case", row.get("id", "")))
        successes, runs = pass_rates.get(case, (0, 0))
        if runs == 0:
            out.append(
                GraduationCandidate(
                    case=case,
                    pass_rate=0.0,
                    runs=0,
                    graduates=False,
                    reason="insufficient data (0 runs)",
                )
            )
            continue
        rate = successes / runs
        if runs < min_runs:
            graduates, reason = False, f"only {runs} runs (< {min_runs} required)"
        elif rate < min_pass_rate:
            graduates, reason = (
                False,
                f"pass rate {rate:.3f} < {min_pass_rate} over {runs} runs",
            )
        else:
            graduates, reason = (
                True,
                f"pass rate {rate:.3f} >= {min_pass_rate} over {runs} runs",
            )
        out.append(
            GraduationCandidate(
                case=case,
                pass_rate=round(rate, 4),
                runs=runs,
                graduates=graduates,
                reason=reason,
            )
        )
    return out


@dataclass(frozen=True)
class RegressionViolation:
    """A FROZEN regression eval that dropped below the floor -- a real alarm."""

    case: str
    pass_rate: float
    runs: int
    floor: float


def regression_floor_violations(
    rows: Sequence[Mapping[str, object]],
    pass_rates: Mapping[str, tuple[int, int]],
    *,
    floor: float = DEFAULT_REGRESSION_FLOOR,
) -> list[RegressionViolation]:
    """The continuously-run gate: REGRESSION evals must stay at/above ``floor``.

    A regression eval with NO run data is itself a violation (rate 0.0): a frozen
    eval that did not run in the suite is a silent gap, which is exactly the
    failure mode the continuously-run regression tier exists to prevent.
    """
    out: list[RegressionViolation] = []
    for row in rows:
        if classify_tier(row) is not EvalTier.REGRESSION:
            continue
        case = str(row.get("case", row.get("id", "")))
        successes, runs = pass_rates.get(case, (0, 0))
        rate = (successes / runs) if runs else 0.0
        if rate < floor:
            out.append(
                RegressionViolation(
                    case=case, pass_rate=round(rate, 4), runs=runs, floor=floor
                )
            )
    return out


# ───────────────────────────────────────────────────────────────────────────
# Langfuse -> goldset feedback bridge
# ───────────────────────────────────────────────────────────────────────────


def eval_record_to_goldset_row(
    record: Mapping[str, object],
    *,
    tier: EvalTier = EvalTier.CAPABILITY,
) -> dict[str, object]:
    """Map one harvested ``eval_capture`` record into a candidate goldset row.

    ``record`` is the dict shape ``services.eval_capture.record`` emits (the same
    one ``meta/analysis.py`` parses): ``task_id``, ``ai_input``, ``ai_response``,
    ``model``, ``cost_usd``, etc. The harvest of these from Langfuse is a network
    read done by the caller; this function is the pure projection into a goldset
    candidate -- which always lands in the CAPABILITY tier (a freshly-harvested
    real failure has NOT earned regression status; it must prove itself first).

    The ``prompt``/``response_text`` keys match the existing corpus row shape
    (see ``cache/goaljudge_eval/ui_batch.jsonl``) so a harvested row drops
    straight into the A/B harness's ``load_corpus``.
    """
    ai_input = record.get("ai_input")
    prompt = ""
    if isinstance(ai_input, Mapping):
        prompt = str(ai_input.get("prompt", ai_input.get("task_input", "")))
    elif isinstance(ai_input, str):
        prompt = ai_input
    return {
        "case": str(record.get("task_id", "")),
        "case_id": str(record.get("task_id", "")),
        "prompt": prompt,
        "response_text": record.get("ai_response", ""),
        "model": record.get("model"),
        "cost_usd": record.get("cost_usd"),
        "trace_id": str(record.get("task_id", "")),
        "tier": tier.value,
        "provenance": "langfuse-harvest",
    }
