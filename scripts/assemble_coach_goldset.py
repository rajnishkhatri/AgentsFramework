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
    build_coach_goldset_manifest,
)

__all__ = ["seed_from_cases", "build_rows", "main"]

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


def build_rows(
    rows: list[CoachGoldsetItem], *, frozen_at: str, provisional: bool = True
) -> dict[str, Any]:
    """Assemble the artifact dict `{rows, manifest}` (FR-11 — a local JSON shape)."""
    manifest = build_coach_goldset_manifest(
        rows, frozen_at=frozen_at, provisional=provisional
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
    args = parser.parse_args(argv)

    rows = seed_from_cases(args.cases)
    artifact = build_rows(rows, frozen_at=args.frozen_at, provisional=args.provisional)
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
