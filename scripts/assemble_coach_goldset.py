"""Assemble the provisional ``coach_goldset_v1`` from the judge-validation cases.

Task 3.7 (Stage 5). Seeds a **provisional single-label** gold set from the 22
corrected `cases.jsonl` rows (item-enriched, FR-13/FR-14 in 3.6), excluding the
unscorable I1 → 21 rows. The real 200–300-row **double-labeled** set (α ≥ 0.80) is a
human coding pass slotted before the 3.8 cert; this build stamps the manifest
``provisional=true`` so the cert refuses by construction (fail-closed).

Mirrors ``scripts/assemble_goaljudge_goldset.py``'s ``--provisional`` shape.
**Offline** — pure file I/O over authored labels, no network, no live LLM.

Usage (local)::

    .venv/bin/python -m scripts.assemble_coach_goldset --provisional \\
        --frozen-at 2026-07-04T00:00:00Z \\
        --out tests/fixtures/coach_goldset/coach_goldset_v1.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.coach_goldset_dataset import (  # noqa: E402
    CoachGoldsetItem,
    GoldsetProvenance,
    GoldsetSplit,
    assert_dev_test_disjoint,
    build_coach_goldset_manifest,
)

__all__ = [
    "seed_from_cases",
    "rows_from_combined_sheet",
    "alpha_from_combined_sheet",
    "build_rows",
    "main",
]

DEFAULT_CASES = REPO_ROOT / "tests/fixtures/coach_judge_validation/cases.jsonl"
DEFAULT_OUT = REPO_ROOT / "tests/fixtures/coach_goldset/coach_goldset_v1.json"

# The six pedagogy axes, in PedagogyVerdict order.
_PED_AXES = (
    "mistake_identification",
    "mistake_location",
    "actionability",
    "coherence",
    "productive_struggle",
    "illusion_of_competence",
)


def _derive_pass(axis: str, expected: dict[str, Any]) -> bool | None:
    """FR-10 axis derivation: axis_fails ⇒ False, axis_passes ⇒ True, else None.

    ``None`` (unconstrained) is preserved — a fabricated bool on an axis the fixture
    never labeled is an AP-6 violation.
    """
    if axis in expected.get("axis_fails", []):
        return False
    if axis in expected.get("axis_passes", []):
        return True
    return None


def seed_from_cases(cases_path: Path = DEFAULT_CASES) -> list[CoachGoldsetItem]:
    """Map the corrected `cases.jsonl` rows → `CoachGoldsetItem`s.

    Excludes ``expected.scorable is False`` rows (the truncated I1). Synthetic
    provenance ⇒ dev split (firewall). ``answer_leakage=null`` rows (abstain-only
    cases) are excluded — a gold row requires a definite label (FR-2).
    """
    rows: list[CoachGoldsetItem] = []
    for line in cases_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        case = json.loads(line)
        expected = case["expected"]
        if expected.get("scorable") is False:
            continue
        if expected.get("answer_leakage") is None:
            # abstain-expected (null) rows are not gradeable gold labels.
            continue
        axes = {f"{a}_pass": _derive_pass(a, expected) for a in _PED_AXES}
        rows.append(
            CoachGoldsetItem(
                item_id=case["case_id"],
                mode=case["mode"],
                question=case.get("question", ""),
                learner_utterance=case["learner_prompt"],
                coach_reply=case["coach_reply"],
                answer_leakage=bool(expected["answer_leakage"]),
                leak_channel=expected.get("leak_channel"),
                failure_mode=None,
                stratum=case.get("stratum", ""),
                split=GoldsetSplit.DEV,
                provenance=GoldsetProvenance.SYNTHETIC,
                taxonomy_version="coach_axial_v1",
                **axes,
            )
        )
    return rows


def _read_combined(sheet_path: Path) -> list[dict[str, str]]:
    with sheet_path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _cell(row: dict[str, str], key: str) -> str:
    return (row.get(key, "") or "").strip()


def rows_from_combined_sheet(sheet_path: Path) -> list[CoachGoldsetItem]:
    """E6: build the real gold rows from the ADJUDICATED combined IAA sheet.

    The combined sheet is the single source of truth after E4: it carries the
    join (dev synthetic + test fresh-authored), the item context, and the
    ``adjudicated_answer_leakage`` gold label. This maps each row to a
    :class:`CoachGoldsetItem`.

    Fail-closed: a blank ``adjudicated_answer_leakage`` raises — E6 must never
    default a missing adjudication to a label (that would silently invent gold).
    ``leak_channel`` stays ``None`` (raters labeled only the binary; the firewall
    still permits a null channel on a leak row).
    """
    items: list[CoachGoldsetItem] = []
    for r in _read_combined(sheet_path):
        adj = _cell(r, "adjudicated_answer_leakage").lower()
        if adj not in {"true", "false"}:
            raise ValueError(
                f"row {r.get('item_id')!r}: adjudicated_answer_leakage is "
                f"{adj!r} (must be resolved to true/false before freeze)"
            )
        items.append(
            CoachGoldsetItem(
                item_id=r["item_id"],
                mode=r["mode"],
                question=r.get("question", ""),
                learner_utterance=r["learner_utterance"],
                coach_reply=r["coach_reply"],
                answer_leakage=(adj == "true"),
                leak_channel=None,
                failure_mode=None,
                stratum=r.get("stratum", ""),
                split=GoldsetSplit(r["split"]),
                provenance=GoldsetProvenance(r["provenance"]),
                taxonomy_version="coach_axial_v1",
            )
        )
    return items


def alpha_from_combined_sheet(sheet_path: Path) -> float | None:
    """Recompute the human–human α (``answer_leakage``) off the two rater columns.

    Reuses the same combined-sheet reader as :func:`alpha_from_combined_rows` in
    ``compute_coach_goldset_alpha`` — the canonical Krippendorff path (NaN→None).
    """
    from scripts.compute_coach_goldset_alpha import alpha_from_combined_rows

    return alpha_from_combined_rows(_read_combined(sheet_path))


def build_rows(
    rows: list[CoachGoldsetItem],
    *,
    frozen_at: str,
    provisional: bool = True,
    human_alpha_answer_leakage: float | None = None,
) -> dict[str, Any]:
    """Assemble the artifact dict `{rows, manifest}` (FR-11 — a local JSON shape).

    When freezing the real (non-provisional) v1 the caller passes
    ``provisional=False`` + the measured α; the manifest builder still forces
    provisional back on if a floor is unmet (fail-closed). ``assert_dev_test_disjoint``
    is enforced here so a contaminated freeze can never be written.
    """
    assert_dev_test_disjoint(rows)
    manifest = build_coach_goldset_manifest(
        rows,
        frozen_at=frozen_at,
        provisional=provisional,
        human_alpha_answer_leakage=human_alpha_answer_leakage,
    )
    return {
        "rows": [r.model_dump(mode="json") for r in rows],
        "manifest": manifest.model_dump(mode="json"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--frozen-at", type=str, required=True)
    parser.add_argument(
        "--provisional",
        action="store_true",
        help="Stamp provisional=true and skip the 200-row + α floors (the only "
        "supported mode until the human double-labeling pass lands).",
    )
    parser.add_argument("--rubric-version", type=str, default="coach_rubric_v1_revised")
    # E6: freeze the real non-provisional v1 from the adjudicated combined sheet
    # (dev synthetic + test fresh-authored, gold = adjudicated_answer_leakage).
    parser.add_argument(
        "--combined-sheet",
        type=Path,
        default=None,
        help="E6 mode: build rows from an adjudicated IAA combined sheet and stamp "
        "the measured α; the manifest still fails closed if a floor is unmet.",
    )
    args = parser.parse_args(argv)

    if args.combined_sheet is not None:
        rows = rows_from_combined_sheet(args.combined_sheet)
        alpha = alpha_from_combined_sheet(args.combined_sheet)
        artifact = build_rows(
            rows,
            frozen_at=args.frozen_at,
            provisional=args.provisional,
            human_alpha_answer_leakage=alpha,
        )
    else:
        rows = seed_from_cases(args.cases)
        artifact = build_rows(
            rows, frozen_at=args.frozen_at, provisional=args.provisional
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    m = artifact["manifest"]
    print(
        f"assembled {len(rows)} coach gold rows → {args.out} "
        f"(provisional={m['provisional']}, α={m['human_alpha_answer_leakage']}, "
        f"leak_share={m['leak_class_share']}, rubric={m['rubric_version']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
