"""Fireworks candidate-screening harness (FR-7, ADR-0019).

Runs the frozen recert split against **each** candidate profile in the
``fireworks`` set on Fireworks, recording a per-candidate scoreboard
(TNR / TPR / κ / abstain) so the operator can RANK before the full ≥3-replay
FR-9 cert. GLM-5.2 is the lead; DeepSeek-R1 / Qwen3-235B / LN-Ultra are the
cross-family candidates screened alongside it. A candidate Fireworks does not
serve is recorded ``unavailable`` — never a fabricated score (FR-7).

Two layers, so CI stays live-free (mirrors ``run_coach_calibration``):

* **Pure core** (``score_candidate`` / ``screen_candidate``) — labels → a
  scoreboard row via the shared ``coach_calibration`` metric helpers; a
  provider-availability failure is captured as ``unavailable``. No LLM, no
  network — fully unit-tested.
* **Live loop** (``main`` / ``_run_candidate_labels``) — manual, creds-gated
  (``# pragma: no cover - live only``). Renders the frozen split through each
  candidate judge. NEVER wired to ``make check`` or CI.

Usage (local, ``FIREWORKS_API_KEY`` exported to the shell)::

    MODEL_PROFILE_SET=fireworks .venv/bin/python -m scripts.screen_coach_candidates \\
        --goldset tests/fixtures/coach_goldset/coach_recert_split_v1.json \\
        --out cache/coach_eval/fireworks_screen.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.coach_calibration import (
    coach_confusion,
    coach_kappa,
    tnr,
    tpr,
)
from services.governance.coach_goldset_dataset import (
    CoachGoldsetItem,
    GoldsetSplit,
)
from trust.exceptions import TrustProviderError

__all__ = ["score_candidate", "screen_candidate", "main"]


def score_candidate(
    model: str,
    *,
    judge_labels: dict[str, bool],
    items: list[CoachGoldsetItem],
) -> dict[str, Any]:
    """Compute a scoreboard row for one candidate from its judge labels.

    Gold comes from the TEST split; judge labels are restricted to those ids, so
    an abstained row (label absent) DROPS from the confusion — it is never scored
    a false (mirrors the cert's FR-11). Uses the shared ``coach_calibration``
    helpers so screening and certification compute metrics identically.
    """
    gold = {i.item_id: i.answer_leakage for i in items if i.split == GoldsetSplit.TEST}
    judge = {k: judge_labels[k] for k in gold if k in judge_labels}
    conf = coach_confusion(judge, gold)
    return {
        "model": model,
        "status": "scored",
        "tpr": tpr(conf),
        "tnr": tnr(conf),
        "kappa": coach_kappa(judge, gold),
        "abstain": len(gold) - len(judge),
        "n_scored": len(judge),
        "confusion": {"tp": conf.tp, "fp": conf.fp, "fn": conf.fn, "tn": conf.tn},
    }


def screen_candidate(
    model: str,
    *,
    run_labels: Callable[[], Any],
) -> dict[str, Any]:
    """Screen one candidate, capturing an unserved model as ``unavailable``.

    ``run_labels`` produces ``(judge_labels, items)`` for a served candidate.
    A ``TrustProviderError`` (the host's typed failure — e.g. a 404 for a model
    the catalog does not serve) is recorded as ``status="unavailable"`` with the
    message, NOT a fabricated score (FR-7). Any OTHER exception (a coding bug)
    propagates — only availability failures are swallowed.
    """
    try:
        judge_labels, items = run_labels()
    except TrustProviderError as exc:
        return {"model": model, "status": "unavailable", "error": str(exc)}
    return score_candidate(model, judge_labels=judge_labels, items=items)


# ── live seam — manual, local-only (never in CI) ─────────────────────────────


async def _run_candidate_labels(  # pragma: no cover - live only
    profile: Any,
    items: list[CoachGoldsetItem],
    *,
    per_call_timeout: float,
) -> tuple[dict[str, bool], list[CoachGoldsetItem]]:
    """Build the judge for one profile and replay the test split → labels.

    Reuses ``run_coach_calibration.replay_test_split_rows`` (with the FR-3 model
    stamp) so screening and the cert share one replay path.
    """
    from scripts.record_coach_judge_validation import build_judges_for_profile
    from scripts.run_coach_calibration import replay_test_split_rows

    # Fail-fast availability probe: ONE cheap direct call BEFORE the 47-row
    # replay. A model the catalog doesn't serve returns HTTP 404; without this
    # probe that 404 would be caught by the judge's bounded retry and turned into
    # a per-row ABSTAIN (verdict=None), so the candidate would look like "47
    # abstains" instead of ``unavailable`` — and burn 47×(3 retries) calls doing
    # it. Probing through the raw provider lets the TrustProviderError propagate
    # to ``screen_candidate``, which records ``unavailable`` (FR-7). A provider
    # error here is authoritative: the host cannot serve this model at all.
    await _probe_model_served(profile)

    pedagogy, _grader = build_judges_for_profile(profile)
    rows = await replay_test_split_rows(
        items,
        pedagogy_judge=pedagogy,
        per_call_timeout=per_call_timeout,
        model=profile.name,
    )
    labels = {
        r["item_id"]: r["judge_leak"] for r in rows if r["judge_leak"] is not None
    }
    return labels, items


async def _probe_model_served(profile: Any) -> None:  # pragma: no cover - live only
    """One minimal completion to confirm the host serves this model.

    Raises ``TrustProviderError`` (propagated to ``screen_candidate`` → recorded
    ``unavailable``) if the model 404s / is not deployed. Kept tiny (1-token
    budget, trivial prompt) so an available model pays ~nothing for the check.
    """
    from services.llm_providers import get_direct_provider

    provider = get_direct_provider(profile)
    await provider.acompletion(
        model=profile.litellm_id,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
    )


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - live only
    import asyncio
    import os

    from scripts.run_coach_calibration import load_goldset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goldset", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--per-call-timeout", type=float, default=90.0)
    args = parser.parse_args(argv)

    from services.llm_config import DEFAULT_MODEL_PROFILE_SET, build_model_registry

    profile_set = os.environ.get("MODEL_PROFILE_SET", DEFAULT_MODEL_PROFILE_SET)
    models, _default = build_model_registry(profile_set)
    # Screen only the direct Fireworks candidates in the set.
    candidates = [m for m in models if m.name.endswith("-fireworks")]

    items, manifest = load_goldset(args.goldset)
    if manifest.provisional:
        print("goldset is provisional — screening is meaningless; aborting.")
        return 1

    board: list[dict[str, Any]] = []
    for profile in candidates:
        print(f"── screening {profile.name} ──", file=sys.stderr)
        row = screen_candidate(
            profile.name,
            run_labels=lambda p=profile: asyncio.run(
                _run_candidate_labels(p, items, per_call_timeout=args.per_call_timeout)
            ),
        )
        board.append(row)
        print(f"  {profile.name}: {row['status']}", file=sys.stderr)

    payload = {
        "screen_kind": "coach_fireworks_candidates",
        "goldset": str(args.goldset),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scoreboard": board,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"scoreboard → {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
