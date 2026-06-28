#!/usr/bin/env python3
"""Tier 1 floor-outcome validation — TaskUnderstanding checklist length vs depth cap.

Implements §3 of ``docs/research/planning_floor_outcome_validation.design.md``.

The deterministic floor's job is to BUDGET enough steps to cover a task's real
subtasks (caps L0=1 / L1=3 / L2=5). ``TaskUnderstanding`` generates the task's
real success checklist at plan time, BEFORE acting and INDEPENDENT of the fired
depth. So we can ask, fully offline (no agent run, no answer-quality noise):

    under_budgeted = effective_checklist_len > fired_depth_cap

If a ``depth-l2-trap`` prompt fires L1 (cap 3) but TaskUnderstanding returns a
4-5 item checklist, the floor under-budgeted — demonstrated deterministically.

Two correctness guards baked in (design §2 caveats):
  * ``success_conditions`` always carries the GENERIC_TAIL_CONDITION; subtract it
    before comparing to the cap (otherwise every count is inflated by one).
  * the list is FLOORED at 2 and CAPPED at 7, so this confirms "needs more than
    L1's 3" but SATURATES above 7 — fine for the L1-vs-L2 question only.

LLM non-determinism guard (design §3 / VD-3): capture ``--samples`` (default 3)
generations per prompt, record the per-prompt checklist-length spread, and FLAG
any prompt whose verdict (under_budgeted) would flip within its own samples.

Two phases, cleanly split so re-scoring costs nothing:

    # spend tokens ONCE — captures samples to the fixture (needs LLM creds):
    python scripts/diagnose_understanding_vs_depth.py --capture

    # re-score the existing fixture, free + deterministic (default):
    python scripts/diagnose_understanding_vs_depth.py

    # CI-style: exit 1 if any trap is NOT shown under-budgeted, or any verdict
    # flips within its samples (calibration only — wire later, not now):
    python scripts/diagnose_understanding_vs_depth.py --strict
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

from components.router import select_planning_depth  # noqa: E402
from components.task_understanding import GENERIC_TAIL_CONDITION  # noqa: E402

_CORPUS = AGENT_ROOT / "cache/goaljudge_eval/planning_floor_strata.jsonl"
_FIXTURE = AGENT_ROOT / "cache/goaljudge_eval/planning_floor_understanding.jsonl"

# The floor's step budget per fired depth (design §3 / plan_builder caps).
_DEPTH_CAP = {"L0": 1, "L1": 3, "L2": 5}


def _load_corpus_depth_rows() -> list[dict]:
    """The depth-surface subset (rows carrying ``want_depth``) — Tier 1 scope.

    MECE/replan/conditions rows are excluded: they have no agent-executable
    prompt form, so TaskUnderstanding cannot generate a meaningful checklist.
    """
    rows = [json.loads(l) for l in _CORPUS.read_text().splitlines() if l.strip()]
    depth = [r for r in rows if r.get("want_depth")]
    # Post-tool short-circuit rows fire L0 by GJ-012 design regardless of the
    # task text — a checklist about the ORIGINAL task would spuriously look
    # "under-budgeted" vs the cap=1 the short-circuit intends. They test a
    # different mechanism; exclude from the budgeting probe.
    return [r for r in depth if not int(r.get("task_tool_results_count") or 0)]


def _effective_len(success_conditions: list[str]) -> int:
    """Checklist length with the always-appended generic tail removed.

    Subtracts the tail by identity if present, else by one (the generator may
    rephrase, but ``_build`` appends the exact constant — identity is the common
    path). Never returns below the schema floor of 1 real condition.
    """
    real = [
        c for c in success_conditions if c.strip() != GENERIC_TAIL_CONDITION.strip()
    ]
    if len(real) == len(success_conditions) and success_conditions:
        # tail not found by identity — subtract one defensively
        return max(0, len(success_conditions) - 1)
    return len(real)


# ── capture phase (the only LLM spend) ───────────────────────────────────────


async def _capture(samples: int) -> None:
    """Generate ``samples`` checklists per depth-surface prompt; write fixture.

    Mirrors ``scripts/probe_guardrail.py`` service wiring: injected LLMService +
    PromptService + fast-tier ModelProfile. Capture-once: re-scoring reads the
    fixture and never calls the LLM again.
    """
    # Standalone scripts don't get the app entry point's env loading; pull the
    # API key from .env exactly like a `python scripts/...` invocation expects.
    # Only the capture phase needs creds — scoring stays fully offline.
    try:
        from dotenv import load_dotenv

        load_dotenv(AGENT_ROOT / ".env")
    except ImportError:
        pass

    from services.base_config import AgentConfig, default_fast_profile
    from services.llm_config import LLMService
    from services.prompt_service import PromptService
    from components.task_understanding import (
        TaskUnderstandingGenerator,
        TaskUnderstandingValidationError,
    )

    # Canonical fast-tier wiring, mirroring tests/components/
    # test_task_understanding_quality.py: one fast profile, LLMService bound to it.
    profile = default_fast_profile()
    config = AgentConfig(default_model=profile.name, models=[profile])
    gen = TaskUnderstandingGenerator(
        llm_service=LLMService(config=config),
        prompt_service=PromptService(),
        profile=profile,
        name="tier1_floor_validation",
    )

    rows = _load_corpus_depth_rows()
    out: list[dict] = []
    print(
        f"capturing {samples} sample(s) for {len(rows)} prompt(s) "
        f"({len(rows) * samples} fast-tier calls) ...",
        file=sys.stderr,
    )
    for row in rows:
        ti = row["task_input"]
        gathered: list[dict] = []
        for s in range(samples):
            try:
                tu = await gen.generate(task_input=ti)
                gathered.append(
                    {
                        "conditions": list(tu.success_conditions),
                        "confidence": tu.confidence,
                        "model": tu.model,
                        "error": None,
                    }
                )
            except TaskUnderstandingValidationError as exc:
                # Gate rejection is itself a datum (the model could not produce
                # a grounded checklist for this prompt) — record, don't crash.
                gathered.append(
                    {
                        "conditions": [],
                        "confidence": 0.0,
                        "model": gen.model_name,
                        "error": f"gate: {exc}",
                    }
                )
            print(
                f"  {row['id']} sample {s + 1}/{samples} "
                f"-> {len(gathered[-1]['conditions'])} conds",
                file=sys.stderr,
            )
        out.append(
            {
                "id": row["id"],
                "family": row["family"],
                "task_input": ti,
                "want_depth": row["want_depth"],
                "samples": gathered,
            }
        )

    _FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    _FIXTURE.write_text("\n".join(json.dumps(r) for r in out) + "\n")
    print(f"wrote {_FIXTURE} ({len(out)} prompts)", file=sys.stderr)


# ── scoring phase (free, deterministic on re-run) ─────────────────────────────


def _score_prompt(rec: dict) -> dict:
    """Score one captured prompt: fired depth, cap, per-sample lengths, verdict.

    ``under_budgeted`` is the majority verdict across samples; ``flips`` is True
    when samples disagree (the honesty flag VD-3 demands).
    """
    ti = rec["task_input"]
    fired, reason = select_planning_depth(task_input=ti, task_tool_results_count=0)
    cap = _DEPTH_CAP[fired]
    want_cap = _DEPTH_CAP[rec["want_depth"]]

    lens, errs = [], 0
    for s in rec["samples"]:
        if s.get("error"):
            errs += 1
            continue
        lens.append(_effective_len(s["conditions"]))

    per_sample_under = [n > cap for n in lens]
    n_under = sum(per_sample_under)
    n_valid = len(per_sample_under)
    flips = 0 < n_under < n_valid  # samples disagree on the verdict
    under_budgeted = n_valid > 0 and n_under * 2 > n_valid  # strict majority

    return {
        "id": rec["id"],
        "family": rec["family"],
        "fired_depth": fired,
        "fired_reason": reason,
        "want_depth": rec["want_depth"],
        "cap": cap,
        "want_cap": want_cap,
        "lens": lens,
        "errors": errs,
        "len_min": min(lens) if lens else None,
        "len_max": max(lens) if lens else None,
        "len_med": statistics.median(lens) if lens else None,
        "under_budgeted": under_budgeted,
        "flips": flips,
        # The clean expected-divergence signature (design §3): a row the floor
        # under-promotes (want > fired) should need more than fired_cap and
        # fit within want_cap.
        "is_underpromote": want_cap > cap,
        "confirms_underplan": (want_cap > cap)
        and under_budgeted
        and (rec["want_depth"] == "L0" or (lens and max(lens) <= want_cap)),
    }


def _report(scored: list[dict]) -> int:
    A = print
    A("\n" + "=" * 78)
    A("  Tier 1 — TaskUnderstanding checklist length vs fired depth cap")
    A("=" * 78)
    A("Signal: under_budgeted = (checklist_len - generic_tail) > fired_depth_cap")
    A("Caps: L0=1  L1=3  L2=5   |   checklist floored at 1 real cond, capped at 6\n")

    hdr = f"{'id':22} {'fam':22} {'fired':6} {'cap':4} {'lens':14} {'under?':7} {'flip?':6}"
    A(hdr)
    A("-" * len(hdr))
    for s in scored:
        lens = ",".join(str(n) for n in s["lens"]) if s["lens"] else "(gate-rej)"
        flag = "  FLIP" if s["flips"] else ""
        A(
            f"{s['id']:22} {s['family'][:22]:22} {s['fired_depth']:6} "
            f"{s['cap']:<4} {lens:14} {str(s['under_budgeted']):7} "
            f"{str(s['flips']):6}{flag}"
        )

    # The headline: do the under-promote rows (want>fired) show under-budgeting?
    underpromote = [s for s in scored if s["is_underpromote"]]
    confirmed = [s for s in underpromote if s["confirms_underplan"]]
    flips = [s for s in scored if s["flips"]]
    gate_rej = [s for s in scored if s["errors"] and not s["lens"]]

    A("\n" + "-" * 78)
    A("UNDER-PROMOTION FINDING (rows where want_depth > fired_depth):")
    if not underpromote:
        A("  none — every depth-surface row fired its want_depth (floor agrees).")
    for s in underpromote:
        verdict = (
            "CONFIRMS under-plan" if s["confirms_underplan"] else "does NOT confirm"
        )
        A(
            f"  {s['id']:22} fired {s['fired_depth']} (cap {s['cap']}) want "
            f"{s['want_depth']} (cap {s['want_cap']})  lens={s['lens']}  -> {verdict}"
        )
    A(
        f"\n  {len(confirmed)}/{len(underpromote)} under-promote rows show the floor "
        f"budgeting fewer steps than TaskUnderstanding's checklist needs."
    )

    if flips:
        A(
            f"\nVERDICT-FLIP FLAGS ({len(flips)}): samples disagreed — treat as "
            "INCONCLUSIVE, not a signal:"
        )
        for s in flips:
            A(f"  {s['id']}  lens={s['lens']} (cap {s['cap']})")
    if gate_rej:
        A(
            f"\nGATE-REJECTED ({len(gate_rej)}): model produced no grounded checklist "
            "(excluded from the verdict):"
        )
        for s in gate_rej:
            A(f"  {s['id']}")

    A("\nINTERPRETATION (calibration, not a gate):")
    if confirmed and not flips:
        A("  Floor UNDER-PLANS the trap prompts, confirmed offline. This raises the")
        A("  Option A `distinct_marker_count>=3 -> L2` ROI; the live A/B (Tier 2) is")
        A("  optional. Fold into options-tradeoff §7.")
    elif underpromote and not confirmed:
        A("  Checklists came back <= fired cap on the under-promote rows — the")
        A("  prompts may genuinely be smaller than their want_depth label. REVISIT")
        A("  the corpus labels (a finding about the corpus, not the floor).")
    elif flips:
        A("  Verdict flips within samples — Tier 1 is INCONCLUSIVE here. Either raise")
        A("  --samples, or escalate to Tier 2 (live GoalJudge A/B) per design §4.")
    else:
        A("  Floor and TaskUnderstanding agree on depth budget across the probe.")
    A("=" * 78 + "\n")

    return 1 if (not confirmed or flips) else 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--capture",
        action="store_true",
        help="Spend tokens: generate samples to the fixture (needs LLM creds).",
    )
    p.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Samples per prompt during --capture (VD-3 variance guard; default 3).",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 unless every under-promote row confirms under-planning "
        "with no verdict-flips (calibration aid; not yet a CI gate).",
    )
    args = p.parse_args()

    if args.capture:
        asyncio.run(_capture(args.samples))
        # fall through to score the freshly-captured fixture

    if not _FIXTURE.exists():
        print(
            f"no fixture at {_FIXTURE}. Run with --capture first (spends ~"
            f"{len(_load_corpus_depth_rows()) * args.samples} fast-tier calls).",
            file=sys.stderr,
        )
        return 2

    records = [json.loads(l) for l in _FIXTURE.read_text().splitlines() if l.strip()]
    scored = [_score_prompt(r) for r in records]
    code = _report(scored)
    return code if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
