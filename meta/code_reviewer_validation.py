"""WI-8: validate the v3 code-reviewer LLM judge against the recorded fixture.

Pyramid layer:   L1 Deterministic at the core (reuses ``meta.judge_validation``
                 pure functions); the CLI does file I/O only.
Architecture:    Horizontal (``meta/``). Imports ``meta.judge_validation``
                 (meta→meta, fine) and stdlib only. MUST NOT import
                 ``orchestration/`` (AP-4).

This is the reviewer arm of judge validation. The GoalJudge arm lives in
``meta/judge_validation.run_validation_cli``; this module validates the
**code-reviewer** LLM judge against the WI-8 labeled fixture.

Convention (see ``tests/fixtures/code_reviewer/wi8_validation/README.md``):

* ``goal_met = True``  — the case is clean (no violation).
* ``goal_met = False`` — the case contains a violation.
* The judge says "not-met" (failure detected) iff it emitted at least one
  ``critical`` or ``warning`` LLM finding. This measures the judge's
  **detection** accuracy, decoupled from the verdict *policy* (WI-9): the v3
  policy ``>2 warnings → REQUEST_CHANGES`` means a single warning yields
  ``APPROVE``, so the verdict alone is too coarse a gate signal.

The gate: TPR ≥ 0.90 AND TNR ≥ 0.90 (``validate_judge``, fail-closed on
undecidable rates). When the gate passes, the v3 LLM verdicts become
gate-grade and the WI-8 honest limit lifts; until then it stays.
"""

from __future__ import annotations

import json
from pathlib import Path

from meta.judge_validation import (
    DEFAULT_TPR_MIN,
    DEFAULT_TNR_MIN,
    JudgeValidation,
    validate_judge,
)

AGENT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = AGENT_ROOT / "tests" / "fixtures" / "code_reviewer" / "wi8_validation"
CASES_JSON = FIXTURE_DIR / "cases.json"
VERDICTS_JSON = FIXTURE_DIR / "verdicts.json"


def _judge_goal_met(record: dict) -> bool | None:
    """Map a recorded verdict to the judge's goal_met (True = clean).

    ``detected`` is recorded by the recording script as
    "any critical/warning LLM finding". ``goal_met = not detected``. Returns
    ``None`` when the record has no usable verdict (e.g. the LLM call errored),
    which ``validate_judge`` excludes via key-set matching — but the caller
    drops ``None`` first so an errored case never silently counts as clean.
    """
    detected = record.get("detected")
    if detected is None:
        return None
    return not bool(detected)


def load_recorded(
    verdicts_path: Path = VERDICTS_JSON,
    cases_path: Path = CASES_JSON,
) -> tuple[dict[str, bool], dict[str, bool], dict]:
    """Load recorded verdicts + gold labels into ``(judge, gold, manifest)``.

    Raises ``FileNotFoundError`` if either file is absent (the CI test treats
    that as a skip, not a failure — mirroring the L3 fixture). Records whose
    ``detected`` is ``None`` (LLM errored) are dropped from BOTH maps so the
    key sets stay aligned; an errored case never biases the gate.
    """
    manifest = json.loads(cases_path.read_text())
    verdicts = json.loads(verdicts_path.read_text())
    gold_by_id = {c["id"]: bool(c["gold_goal_met"]) for c in manifest["cases"]}
    records = verdicts.get("records", [])

    judge: dict[str, bool] = {}
    gold: dict[str, bool] = {}
    for rec in records:
        cid = rec["case_id"]
        j = _judge_goal_met(rec)
        if j is None or cid not in gold_by_id:
            continue
        judge[cid] = j
        gold[cid] = gold_by_id[cid]
    return judge, gold, manifest


def validate_recorded(
    verdicts_path: Path = VERDICTS_JSON,
    cases_path: Path = CASES_JSON,
) -> JudgeValidation:
    """Run ``validate_judge`` on the recorded WI-8 fixture.

    Fail-closed on no usable data: if every record errored (no aligned cases
    remain), return a ``JudgeValidation`` with undecidable rates rather than
    raising — mirroring the ``validate_judge`` convention that a judge you
    cannot measure is a judge you cannot trust.
    """
    judge, gold, manifest = load_recorded(verdicts_path, cases_path)
    gate = manifest.get("gate", {})
    tpr_min = gate.get("tpr_min", DEFAULT_TPR_MIN)
    tnr_min = gate.get("tnr_min", DEFAULT_TNR_MIN)

    if not judge:
        from meta.judge_validation import JudgeRates, RoganGladen
        from services.governance.goaljudge_calibration import ConfusionCounts

        empty = ConfusionCounts(0, 0, 0, 0)
        return JudgeValidation(
            counts=empty,
            rates=JudgeRates(None, None, None, None),
            rogan_gladen=RoganGladen(0.0, None, None, False),
            tpr_min=tpr_min,
            tnr_min=tnr_min,
            passed=False,
            reasons=(
                "no aligned records (every LLM verdict errored or was "
                "dropped) -- fail-closed: cannot measure the judge",
            ),
        )

    return validate_judge(judge, gold, tpr_min=tpr_min, tnr_min=tnr_min)


def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.4f}"


def run_validation_cli(args: list[str] | None = None) -> int:
    """CLI: validate the recorded reviewer fixture; exit 0 pass / 1 fail / 2 err."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WI-8: validate the v3 code-reviewer LLM judge (TPR/TNR)."
    )
    parser.add_argument(
        "--verdicts",
        type=str,
        default=str(VERDICTS_JSON),
        help="recorded verdicts JSON (default: the WI-8 fixture verdicts.json)",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default=str(CASES_JSON),
        help="fixture manifest (default: the WI-8 cases.json)",
    )
    parsed = parser.parse_args(args)

    vpath = Path(parsed.verdicts)
    cpath = Path(parsed.cases)
    try:
        result = validate_recorded(vpath, cpath)
    except FileNotFoundError as exc:
        print(f"error: {exc}")
        return 2
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"error: malformed fixture: {exc}")
        return 2

    c, r = result.counts, result.rates
    verdict = "PASS" if result.passed else "FAIL"
    print(
        f"REVIEWER JUDGE VALIDATION: {verdict}  "
        f"(n={c.tp + c.fp + c.fn + c.tn}, "
        f"tpr_min={result.tpr_min}, tnr_min={result.tnr_min})"
    )
    print(f"  confusion  tp={c.tp} fp={c.fp} fn={c.fn} tn={c.tn}")
    print(f"  TPR (recall)      {_fmt(r.tpr)}  (floor {result.tpr_min})")
    print(f"  TNR (specificity) {_fmt(r.tnr)}  (floor {result.tnr_min})")
    print(f"  FPR (false-down)  {_fmt(r.fpr)}")
    print(f"  FNR (miss)        {_fmt(r.fnr)}")
    for reason in result.reasons:
        print(f"  - {reason}")
    if not result.passed:
        print(
            "  The v3 LLM judge is NOT validated. The honest limit stands: LLM "
            "verdicts are not gate-grade. Improve the v3 prompt and re-run "
            "scripts/record_code_reviewer_validation.py."
        )
    return 0 if result.passed else 1


if __name__ == "__main__":
    import sys

    sys.exit(run_validation_cli())
