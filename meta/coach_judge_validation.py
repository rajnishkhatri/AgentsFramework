"""Task 3.5b — coach judge-validation scorer (offline replay).

Replays a committed ``verdicts.json`` against the human-coded ``expected`` in the
judge fixture (``docs/evals/eng-coach/judge_test_cases.jsonl`` → committed as
``tests/fixtures/coach_judge_validation/cases.jsonl``) and reports:

* ``answer_leakage`` TPR/TNR/FPR/FNR **with raw counts** (FR-6), computed via
  ``meta.judge_validation.judge_rates`` — the confusion math is NEVER
  re-implemented here (meta convention / AP-6).
* per-axis agreement against the binary ``*_pass`` companions (FR-8).
* the H1≡C2 input-determinism check (FR-4) and control non-regression (FR-5).
* unscorable exclusion (FR-1) and ``null``-matched-only-by-abstain (FR-2).

This module is **pure**: it reads JSON and returns a report. It imports only
``services``/``trust`` (via ``judge_validation``) — never ``orchestration``
(Invariant #8 / AP-4). No live LLM: the recording that produces ``verdicts.json``
is a separate, local-only script (Task 3.5d).

Stage 3.5 is **advisory** (FR-11): this scorer *reports* rates; it exposes no
pass/fail leak-rate gate — that is deferred to Task 3.6 once the corpus grows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from services.governance.goaljudge_calibration import ConfusionCounts

from meta.judge_validation import JudgeRates, judge_rates

__all__ = [
    "ScorerError",
    "CoachValidationReport",
    "load_cases",
    "load_verdicts",
    "score",
]

# The 8 negative-control cases (spec §3 FR-5) that must never record leakage.
CONTROL_CASE_IDS = frozenset({"A4", "B2", "D2", "D3", "E3", "F1", "G1", "G4"})

# The byte-identical-input determinism pair (spec FR-4). Their recorded verdicts
# must match on every axis + answer_leakage.
DETERMINISM_PAIR = ("H1", "C2")

_PED_AXES = (
    "mistake_identification",
    "mistake_location",
    "actionability",
    "coherence",
    "productive_struggle",
    "illusion_of_competence",
)


class ScorerError(RuntimeError):
    """The fixture pair is structurally unusable (mismatch, duplicate, bad shape)."""


@dataclass
class CoachValidationReport:
    """Everything the replay produces. Reported, not gated (FR-11)."""

    counts: ConfusionCounts
    rates: JudgeRates
    excluded_unscorable: list[str] = field(default_factory=list)
    null_mismatches: list[str] = field(default_factory=list)
    control_regressions: list[str] = field(default_factory=list)
    determinism_ok: bool = True
    determinism_divergence: str | None = None
    # per case_id → {axis: "match"|"mismatch"} for the axes the case constrains
    per_axis_results: dict[str, dict[str, str]] = field(default_factory=dict)


def load_cases(path: Path) -> dict[str, dict[str, Any]]:
    """Load the fixture cases (one JSON object per line) keyed by ``case_id``."""
    cases: dict[str, dict[str, Any]] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        cid = row["case_id"]
        if cid in cases:
            raise ScorerError(f"duplicate case_id in cases: {cid}")
        cases[cid] = row
    return cases


def load_verdicts(path: Path) -> dict[str, dict[str, Any]]:
    """Load recorded verdicts keyed by ``case_id``.

    Raises ``ScorerError`` on a duplicate ``case_id`` — a re-record must not
    silently last-wins (FR-3 / edge).
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for row in payload.get("verdicts", []):
        cid = row["case_id"]
        if cid in out:
            raise ScorerError(f"duplicate case_id in verdicts: {cid}")
        out[cid] = row
    return out


def score(
    cases: dict[str, dict[str, Any]],
    verdicts: dict[str, dict[str, Any]],
) -> CoachValidationReport:
    """Replay ``verdicts`` against ``cases`` ``expected`` → a report.

    FR-3: every verdict must name a case present in ``cases`` (1:1 by id) — a
    stray verdict is a hard error, never a silently-scored subset.
    """
    stray = set(verdicts) - set(cases)
    if stray:
        raise ScorerError(
            f"verdicts reference case_ids absent from the case set: {sorted(stray)}"
        )

    tp = fp = fn = tn = 0
    excluded_unscorable: list[str] = []
    null_mismatches: list[str] = []
    control_regressions: list[str] = []
    per_axis_results: dict[str, dict[str, str]] = {}

    for cid, vrow in verdicts.items():
        case = cases[cid]
        expected = case["expected"]
        verdict = vrow.get("verdict")
        abstained = bool(vrow.get("abstained", False))

        # FR-1: unscorable cases never enter the confusion matrix / axis tally.
        if expected.get("scorable") is False:
            excluded_unscorable.append(cid)
            continue

        exp_leak = expected.get("answer_leakage")

        # FR-2: a null expected is matched only by an explicit abstain.
        if exp_leak is None:
            if not abstained:
                null_mismatches.append(cid)
            continue

        # A scorable, non-null case that abstained cannot be placed in a quadrant
        # — record it as a null-style mismatch so it is surfaced, not hidden.
        if verdict is None or abstained:
            null_mismatches.append(cid)
            continue

        judge_leak = bool(verdict.get("answer_leakage"))

        # Positive class = "leaked" (mirrors judge_validation's not-met positive).
        if exp_leak and judge_leak:
            tp += 1
        elif not exp_leak and judge_leak:
            fp += 1
        elif exp_leak and not judge_leak:
            fn += 1
        else:
            tn += 1

        # FR-5: a control must never record leakage.
        if cid in CONTROL_CASE_IDS and judge_leak:
            control_regressions.append(cid)

        # FR-8: per-axis mapping to the binary *_pass companion.
        axis_result = _axis_agreement(expected, verdict)
        if axis_result:
            per_axis_results[cid] = axis_result

    counts = ConfusionCounts(tp=tp, fp=fp, fn=fn, tn=tn)
    rates = judge_rates(counts)

    determinism_ok, divergence = _check_determinism(verdicts)

    return CoachValidationReport(
        counts=counts,
        rates=rates,
        excluded_unscorable=excluded_unscorable,
        null_mismatches=null_mismatches,
        control_regressions=control_regressions,
        determinism_ok=determinism_ok,
        determinism_divergence=divergence,
        per_axis_results=per_axis_results,
    )


def _axis_agreement(
    expected: dict[str, Any], verdict: dict[str, Any]
) -> dict[str, str]:
    """FR-8: map ``axis_fails``/``axis_passes`` to the binary ``*_pass`` field.

    ``axis_fails:[X]`` ⇒ ``X_pass`` must be ``False``; ``axis_passes:[X]`` ⇒
    ``X_pass`` must be ``True``. Axes in neither list are unconstrained (absent).
    """
    result: dict[str, str] = {}
    for axis in expected.get("axis_fails", []):
        got = verdict.get(f"{axis}_pass")
        result[axis] = "match" if got is False else "mismatch"
    for axis in expected.get("axis_passes", []):
        got = verdict.get(f"{axis}_pass")
        result[axis] = "match" if got is True else "mismatch"
    return result


def _check_determinism(
    verdicts: dict[str, dict[str, Any]],
) -> tuple[bool, str | None]:
    """FR-4: the byte-identical-input pair must carry identical verdicts."""
    a, b = DETERMINISM_PAIR
    if a not in verdicts or b not in verdicts:
        return True, None  # pair not present in this slice → nothing to check
    va = verdicts[a].get("verdict")
    vb = verdicts[b].get("verdict")
    if va == vb:
        return True, None
    fields = _diverging_fields(va, vb)
    return False, f"{a} vs {b} diverge on: {fields}"


def _diverging_fields(va: Any, vb: Any) -> list[str]:
    if not isinstance(va, dict) or not isinstance(vb, dict):
        return ["<verdict presence>"]
    keys = set(va) | set(vb)
    return sorted(k for k in keys if va.get(k) != vb.get(k))
