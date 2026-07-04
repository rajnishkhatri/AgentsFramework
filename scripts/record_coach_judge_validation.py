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
        # Route on the optional per-case ``judge`` axis (default pedagogy). A case
        # marked ``judge: "grader"`` MUST reach ``grader_judge`` — the spec (3.5d
        # '+ GraderJudge for content-axis cases') reserves the param for this.
        # Fail loud rather than silently rescoring a grader case as pedagogy.
        axis = case.get("judge", "pedagogy")
        if axis == "grader":
            if grader_judge is None:
                raise ValueError(
                    f"case {cid!r} declares judge='grader' but no grader_judge "
                    "was supplied — refusing to rescore it as pedagogy"
                )
            judge = grader_judge
        else:
            judge = pedagogy_judge
        verdict = await judge.evaluate(
            learner_utterance=case["learner_prompt"],
            coach_reply=case["coach_reply"],
            mode=case["mode"],
            # The judge needs the ITEM (passage/stem/choices) to run the
            # "is >1 option still live?" leak test — the bare question_id
            # ("q-gram-1") makes it undecidable (ADR-0017). ``question`` is the
            # rendered block from scripts.enrich_coach_judge_cases; fall back to
            # question_id only if a case predates enrichment.
            question=case.get("question") or case.get("question_id", ""),
        )
        rows.append(
            {
                "case_id": cid,
                "judge": axis,
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
    import os

    from components.subject_coach_judges import GraderJudge, PedagogyJudge
    from services.base_config import AgentConfig  # noqa: PLC0415
    from services.llm_config import (  # noqa: PLC0415
        DEFAULT_MODEL_PROFILE_SET,
        LLMService,
        build_model_registry,
    )
    from services.prompt_service import PromptService  # noqa: PLC0415

    # Build the full catalog (H2-canonical entry point), honoring MODEL_PROFILE_SET.
    profile_set = os.environ.get("MODEL_PROFILE_SET", DEFAULT_MODEL_PROFILE_SET)
    models, _default = build_model_registry(profile_set)

    # A leakage judge benefits from a stronger tier; default capable. Override via
    # COACH_JUDGE_TIER={fast|capable|reasoning} — reasoning is best for catching
    # the subtle indirect-leak channels the capable judge missed (0/5).
    _VALID_TIERS = {"fast", "capable", "reasoning"}
    want_tier = os.environ.get("COACH_JUDGE_TIER", "").strip().lower()
    if want_tier not in _VALID_TIERS:
        want_tier = "capable"
    profile = next(
        (m for m in models if getattr(m, "tier", None) == want_tier),
        # fall back to the strongest available tier, then the first profile
        next(
            (m for m in models if getattr(m, "tier", None) == "reasoning"),
            models[0],
        ),
    )

    agent_config = AgentConfig(default_model=profile.name, models=models)
    llm_service = LLMService(agent_config)
    prompt_service = PromptService()
    pedagogy = PedagogyJudge(llm_service, prompt_service, profile, name="PedagogyJudge")
    grader = GraderJudge(llm_service, prompt_service, profile, name="GraderJudge")
    return pedagogy, grader, profile.name


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
