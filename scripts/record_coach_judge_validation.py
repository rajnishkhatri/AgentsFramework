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

__all__ = [
    "record_verdicts",
    "write_verdicts",
    "select_judge_profile",
    "build_live_judges",
    "main",
]


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


_VALID_JUDGE_TIERS = frozenset({"fast", "capable", "reasoning"})


def select_judge_profile(
    models: list[Any],
    *,
    model_pin: str | None,
    tier: str,
) -> Any:
    """Pick the judge ``ModelProfile`` from a profile list — the PURE selection
    core of :func:`build_live_judges` (fresh-recert spec FR-8).

    Two modes, pin taking precedence:

    * **``model_pin`` set** — an explicit by-NAME pin (``COACH_JUDGE_MODEL``).
      Returns that exact profile; raises ``KeyError(name)`` naming the pin and the
      available names if it is absent from the active set (mirrors
      ``LLMService.get_profile``). This is the ONLY way to reach a ``provider=
      "direct"`` model such as ``glm-5.2``, which is opt-in-by-pin and lives only
      in ``MODEL_PROFILE_SET=glm`` (whose *tier* default is ``glm-5.1`` — so a
      tier-only override would pick the wrong GLM; the pin is required).
    * **``model_pin`` unset** — today's behavior: the requested ``tier`` (falling
      back to the strongest tier, then the first profile). Unchanged from 3.9.

    Kept as a free function (no ``LLMService``/network) so the branch is L1-testable
    offline — ``build_live_judges`` stays ``# pragma: no cover - live only``.
    """
    if model_pin:
        for m in models:
            if getattr(m, "name", None) == model_pin:
                return m
        available = [getattr(m, "name", "?") for m in models]
        raise KeyError(
            f"COACH_JUDGE_MODEL='{model_pin}' not in the active profile set. "
            f"Available: {available}. (glm-5.2 requires MODEL_PROFILE_SET=glm.)"
        )
    want_tier = tier if tier in _VALID_JUDGE_TIERS else "capable"
    return next(
        (m for m in models if getattr(m, "tier", None) == want_tier),
        # fall back to the strongest available tier, then the first profile
        next(
            (m for m in models if getattr(m, "tier", None) == "reasoning"),
            models[0],
        ),
    )


def build_live_judges() -> tuple[Any, Any, str]:  # pragma: no cover - live only
    """Construct the REAL judges from production wiring (live LLM).

    Imported lazily inside ``main`` so the module imports with no provider/env.
    Never called by any test — the offline smoke test injects a stub judge. The
    pure model-selection branch lives in :func:`select_judge_profile` (L1-tested).
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

    # Model selection (FR-8): an explicit COACH_JUDGE_MODEL pin wins (the only way
    # to reach a provider="direct" model like glm-5.2 for the 3.9 re-cert);
    # otherwise COACH_JUDGE_TIER={fast|capable|reasoning}, default capable —
    # reasoning is best for the subtle indirect-leak channels the capable judge
    # missed (0/5). Selection stays inside the registry (H2 — no hardcoded string).
    profile = select_judge_profile(
        models,
        model_pin=os.environ.get("COACH_JUDGE_MODEL", "").strip() or None,
        tier=os.environ.get("COACH_JUDGE_TIER", "").strip().lower(),
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
