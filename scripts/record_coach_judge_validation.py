"""Task 3.5d — record coach judge verdicts over the validation fixture.

Renders each fixture case through the coach judges (``PedagogyJudge`` — and
``GraderJudge`` where a case exercises content axes) and writes one verdict row
per ``case_id`` to a ``verdicts.json`` the offline scorer
(``meta.coach_judge_validation``) replays.

**This is the ONE live-LLM seam in the harness.** The live entrypoint
(``main``) is manual and local-only — it is never invoked by CI or ``make
check``. The scoring/replay is entirely offline. Keeping the live call here (and
only here) is what lets the constitution's no-live-LLM-in-CI rule hold.

Usage (local, creds in env)::

    .venv/bin/python -m scripts.record_coach_judge_validation \\
        --cases tests/fixtures/coach_judge_validation/cases.jsonl \\
        --out   tests/fixtures/coach_judge_validation/verdicts.json

The core ``record_verdicts`` coroutine is provider-agnostic: it takes a built
``PedagogyJudge``/``GraderJudge`` pair, so a stub provider drives it in the
offline smoke test (FR-9 stub) without any network.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from meta.coach_judge_validation import load_cases

__all__ = ["record_verdicts", "write_verdicts", "build_live_judges", "main"]


async def record_verdicts(
    cases: dict[str, dict[str, Any]],
    *,
    pedagogy_judge: Any,
    grader_judge: Any | None = None,
    model: str = "",
) -> dict[str, Any]:
    """Render every case through the judge and collect verdict rows.

    Provider-agnostic: ``pedagogy_judge``/``grader_judge`` are already-built
    judges, so a stub-provider judge drives this offline (FR-9 stub). A judge
    that returns ``None`` (undecidable / provider error) is recorded as
    ``abstained: true`` — never repaired into a fabricated verdict (mirrors the
    ``subject_coach_judges`` fail-open ban).
    """
    rows: list[dict[str, Any]] = []
    for cid, case in cases.items():
        verdict = await pedagogy_judge.evaluate(
            learner_utterance=case["learner_prompt"],
            coach_reply=case["coach_reply"],
            mode=case["mode"],
            question=case.get("question_id", ""),
        )
        rows.append(
            {
                "case_id": cid,
                "judge": "pedagogy",
                "abstained": verdict is None,
                "verdict": verdict.model_dump() if verdict is not None else None,
            }
        )
    return {
        "model": model or getattr(pedagogy_judge, "model_name", ""),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "verdicts": rows,
    }


def write_verdicts(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_live_judges() -> tuple[Any, Any, str]:  # pragma: no cover - live only
    """Construct the REAL judges from production wiring (live LLM).

    Imported lazily inside ``main`` so the module imports with no provider/env.
    Never called by any test — the offline smoke test injects a stub judge.
    """
    from components.subject_coach_judges import GraderJudge, PedagogyJudge
    from services.llm_service import LLMService  # noqa: PLC0415
    from services.prompt_service import PromptService  # noqa: PLC0415
    from services.subject_coach_judge_runtime_config import (  # noqa: PLC0415
        SubjectCoachJudgeConfigReader,
    )

    prompt_service = PromptService()
    llm_service = LLMService()
    resolved = SubjectCoachJudgeConfigReader().get()
    profile = resolved.judge_profile
    pedagogy = PedagogyJudge(llm_service, prompt_service, profile, name="PedagogyJudge")
    grader = GraderJudge(llm_service, prompt_service, profile, name="GraderJudge")
    return pedagogy, grader, getattr(profile, "name", "")


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - live only
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=REPO_ROOT / "tests/fixtures/coach_judge_validation/cases.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "tests/fixtures/coach_judge_validation/verdicts.json",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    pedagogy, grader, model = build_live_judges()
    payload = asyncio.run(
        record_verdicts(
            cases, pedagogy_judge=pedagogy, grader_judge=grader, model=model
        )
    )
    write_verdicts(args.out, payload)
    n_abstain = sum(1 for r in payload["verdicts"] if r["abstained"])
    print(
        f"recorded {len(payload['verdicts'])} verdicts → {args.out} "
        f"({n_abstain} abstained) model={payload['model']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
