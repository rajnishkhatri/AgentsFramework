#!/usr/bin/env python
"""Model-swap A/B evaluation harness (plan Part II).

Run the SAME frozen corpus under two model arms and diff the two ``score_run``
summaries into a PROMOTE / HOLD / CONTAMINATED verdict. The fast pre-deploy gate
for "is this model swap safe to ship?" — the executable form of the Part I
"re-run the regression suites under MODEL_PROFILE_SET=anthropic" check.

An **arm** is either:
  * a pinned model name (``--baseline gpt-4o-mini --candidate claude-haiku-4-5``):
    seed ``selected_model=<arm model>`` into the graph input — the same dict the
    UI pins through, honored by the router's ``pinned_model`` branch; or
  * a whole profile set (``--baseline-set openai --candidate-set anthropic``):
    set ``MODEL_PROFILE_SET`` before ``build_agent_and_tools()`` so Auto routes
    per-tier across the chosen stack.

The graph / router / tools / carriers are IDENTICAL to prod; only the model id
differs, so behavior-parity (routing correctness, replan/reflexion/escalation
firing) is faithfully measured locally. The honest limit — local runs do NOT
exercise the deployed Cloud Run path, pgvector recall, or real Langfuse cost
panels — is stamped into every report.

Reuses, unchanged (imported, not subprocessed):
  * ``scripts.run_goaljudge_synthetic_batch`` — ``build_agent_and_tools``,
    ``run_case`` (the real compiled graph), ``truncate_eval_log`` isolation.
  * ``scripts.analyze_planning_traces`` — ``score_run`` (the unit of comparison),
    ``_load_blackbox_events``, ``_merge_corpus_expectations``.

Unit tests live in ``tests/scripts/test_model_ab_eval.py`` (no live LLM). The
``--smoke`` real-LLM path is opt-in and never runs in CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from scripts.analyze_planning_traces import (  # noqa: E402
    _load_blackbox_events,
    _merge_corpus_expectations,
    score_run,
)

# Default frozen corpus (the planning-stress phase-9 batch). The goaljudge
# corpus (cache/goaljudge_eval/*.jsonl) is the obvious alternate via --corpus.
_DEFAULT_CORPUS = AGENT_ROOT / "cache" / "planning_stress_phase9" / "ui_batch.jsonl"

# The per-phase hit-rate phases scored as a simple rate (candidate must be >=
# baseline - tolerance). Escalation/fan-out are precision-gated separately.
_RATE_PHASES = ("depth", "replan", "reflexion", "compaction")

# Verdicts. CONTAMINATED (instrumentation/identity failed) is reported SEPARATELY
# from HOLD (a real behavior regression) — never collapse them (governance: the
# audit's instrumentation-vs-outcome split).
PROMOTE = "PROMOTE"
HOLD = "HOLD"
CONTAMINATED = "CONTAMINATED"


# ── corpus / hashing ──────────────────────────────────────────────────────────


def load_corpus(path: Path) -> list[dict]:
    """Read a frozen ``ui_batch.jsonl`` corpus into row dicts."""
    rows = [
        json.loads(line)
        for line in path.read_text().strip().split("\n")
        if line
    ]
    return _merge_corpus_expectations(rows)


def corpus_hash(path: Path) -> str:
    """SHA-256 of the raw corpus bytes — the auditable record of *what was
    compared* so a PROMOTE is reconstructable later (governance: decision
    artifact). Short 16-hex prefix is plenty for a human report."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ── arm integrity (governance: the audit's zero/wrong-carrier rule on model id) ─


def _models_used(events: list[dict]) -> list[str]:
    """Every distinct non-empty ``model`` recorded on the STEP_EXECUTED carriers
    of one run (Recording pillar; react_loop.py STEP_EXECUTED details["model"]).
    An empty string here is the token-seam failure mode — the caller treats an
    all-empty run as a contamination, never a silent pass."""
    seen: list[str] = []
    for e in events:
        et = (e.get("event_type") or "")
        if not et.endswith("step_executed"):
            continue
        details = e.get("details")
        if not isinstance(details, dict):
            continue
        model = details.get("model")
        if isinstance(model, str) and model and model not in seen:
            seen.append(model)
    return seen


@dataclass
class ArmIntegrity:
    """Per-arm integrity result. ``ok`` is the gate; ``mismatches`` is the
    verbatim evidence list the report prints."""

    ok: bool
    expected: set[str]
    rows_scored: int
    rows_missing_trace: int
    mismatches: list[str] = field(default_factory=list)


def check_arm_integrity(
    rows: list[dict],
    events_by_row: dict[str, list[dict]],
    expected_models: set[str],
) -> ArmIntegrity:
    """Assert each scored row actually ran on the arm's model(s).

    ``expected_models`` is the arm's pin (a one-name set) or the arm set's full
    name roster (a set arm). A row whose STEP_EXECUTED ``model`` is NOT in the
    expected set — OR which recorded NO model at all (empty token seam) — is a
    contamination. A missing trace is recorded but is NOT a contamination on its
    own (the run may have legitimately produced no recording); it is surfaced so
    a wholly-empty arm is visible.
    """
    mismatches: list[str] = []
    rows_scored = 0
    rows_missing = 0
    for row in rows:
        case = row["case"]
        events = events_by_row.get(case, [])
        if not events:
            rows_missing += 1
            continue
        rows_scored += 1
        used = _models_used(events)
        if not used:
            mismatches.append(f"EMPTY-MODEL :: {case} (no model_used carrier)")
            continue
        stray = [m for m in used if m not in expected_models]
        if stray:
            mismatches.append(
                f"WRONG-MODEL :: {case} ran {stray} ∉ {sorted(expected_models)}"
            )
    # An arm that produced NO scored rows at all is contaminated (nothing ran).
    ok = not mismatches and rows_scored > 0
    return ArmIntegrity(
        ok=ok,
        expected=expected_models,
        rows_scored=rows_scored,
        rows_missing_trace=rows_missing,
        mismatches=mismatches,
    )


# ── diff + verdict ─────────────────────────────────────────────────────────────


def _precision(confusion: dict[str, Any] | None) -> float | None:
    """Precision off a confusion-matrix dict, or None when the cell is empty
    (no positives predicted — precision is undefined, not a regression)."""
    if not confusion:
        return None
    tp = confusion.get("tp", 0)
    fp = confusion.get("fp", 0)
    if (tp + fp) == 0:
        return None
    return confusion.get("precision", round(tp / (tp + fp), 3))


def diff_summaries(
    baseline: dict,
    candidate: dict,
    *,
    cost_baseline: float = 0.0,
    cost_candidate: float = 0.0,
    n_tasks: int = 0,
    tolerance: float = 0.0,
    max_cost_ratio: float | None = None,
) -> dict:
    """Diff two ``score_run`` summaries into a verdict payload.

    Behavior gate (no GoalJudge-quality gate in v1): candidate hit-rate must be
    ``>= baseline - tolerance`` for every rate phase; escalation & fan-out
    PRECISION must not drop past tolerance (recall is deliberately NOT gated —
    a missed escalation/fan-out is the cheap error). Any phase below floor ⇒ HOLD
    with the offending phase + delta named.

    Cost never auto-HOLDs (a pricier model can still be worth it) — it is surfaced
    for the human decision; ``max_cost_ratio`` opts into a hard cap.

    Integrity is checked separately (``check_arm_integrity``) and folded in by the
    caller — ``diff_summaries`` assumes both arms are clean and only judges
    behavior + cost. The returned ``verdict`` is PROMOTE or HOLD; CONTAMINATED is
    set by the caller when an arm fails integrity.
    """
    regressions: list[str] = []
    phase_table: list[dict] = []

    base_phases = baseline.get("phases", {})
    cand_phases = candidate.get("phases", {})
    for phase in _RATE_PHASES:
        bp = base_phases.get(phase)
        cp = cand_phases.get(phase)
        if not bp or not cp or not bp.get("scored") or not cp.get("scored"):
            continue
        b_rate = bp["rate"]
        c_rate = cp["rate"]
        delta = round(c_rate - b_rate, 3)
        floor = round(b_rate - tolerance, 3)
        passed = c_rate >= floor
        phase_table.append(
            {
                "phase": phase,
                "baseline": b_rate,
                "candidate": c_rate,
                "delta": delta,
                "floor": floor,
                "pass": passed,
                "kind": "rate",
            }
        )
        if not passed:
            regressions.append(
                f"{phase}: candidate rate {c_rate} < floor {floor} "
                f"(baseline {b_rate}, Δ {delta})"
            )

    # Escalation + fan-out precision (the fp cell is the GAIA-failure detector).
    for key, label in (
        ("escalation_confusion", "escalation"),
        ("fanout_confusion", "fanout"),
    ):
        b_prec = _precision(baseline.get(key))
        c_prec = _precision(candidate.get(key))
        if b_prec is None or c_prec is None:
            continue
        delta = round(c_prec - b_prec, 3)
        floor = round(b_prec - tolerance, 3)
        passed = c_prec >= floor
        phase_table.append(
            {
                "phase": f"{label}-precision",
                "baseline": b_prec,
                "candidate": c_prec,
                "delta": delta,
                "floor": floor,
                "pass": passed,
                "kind": "precision",
            }
        )
        if not passed:
            regressions.append(
                f"{label} precision {c_prec} < floor {floor} "
                f"(baseline {b_prec}, Δ {delta})"
            )

    # Cost — surfaced, never auto-HOLD unless --max-cost-ratio opted in.
    cost_per_task_baseline = round(cost_baseline / n_tasks, 6) if n_tasks else 0.0
    cost_per_task_candidate = round(cost_candidate / n_tasks, 6) if n_tasks else 0.0
    cost_ratio = (
        round(cost_candidate / cost_baseline, 3)
        if cost_baseline > 0
        else None
    )
    cost_violation = (
        max_cost_ratio is not None
        and cost_ratio is not None
        and cost_ratio > max_cost_ratio
    )
    if cost_violation:
        regressions.append(
            f"cost ratio {cost_ratio} > cap {max_cost_ratio} "
            f"(${cost_per_task_candidate}/task vs ${cost_per_task_baseline})"
        )

    verdict = HOLD if regressions else PROMOTE
    return {
        "verdict": verdict,
        "regressions": regressions,
        "phase_table": phase_table,
        "cost": {
            "baseline_total_usd": round(cost_baseline, 6),
            "candidate_total_usd": round(cost_candidate, 6),
            "baseline_per_task_usd": cost_per_task_baseline,
            "candidate_per_task_usd": cost_per_task_candidate,
            "ratio": cost_ratio,
            "projected_per_1k_tasks_candidate": round(
                cost_per_task_candidate * 1000, 3
            ),
            "max_cost_ratio": max_cost_ratio,
            "violation": cost_violation,
        },
    }


def decide_verdict(
    diff: dict,
    baseline_integrity: ArmIntegrity,
    candidate_integrity: ArmIntegrity,
) -> str:
    """Fold integrity into the behavior verdict. CONTAMINATED dominates: if
    EITHER arm failed integrity, the diff is not trustworthy and we never
    PROMOTE — instrumentation failure is reported as its own verdict, not
    collapsed into HOLD."""
    if not baseline_integrity.ok or not candidate_integrity.ok:
        return CONTAMINATED
    return diff["verdict"]


# ── report writers (governance: decision artifact) ─────────────────────────────

_LOCAL_LIMIT_NOTE = (
    "LIMIT: this is a LOCAL pre-deploy gate. Local runs do NOT exercise the "
    "deployed Cloud Run path, pgvector recall, or real Langfuse cost panels. A "
    "local PROMOTE is NOT a prod sign-off — the deployed-revision regression run "
    "+ a governance-trace-audit pass on the tagged revision's real traces stay "
    "the FINAL gate before flipping MODEL_PROFILE_SET."
)


def build_report_payload(
    *,
    run_id: str,
    corpus_path: Path,
    baseline_arm: str,
    candidate_arm: str,
    baseline_summary: dict,
    candidate_summary: dict,
    diff: dict,
    verdict: str,
    baseline_integrity: ArmIntegrity,
    candidate_integrity: ArmIntegrity,
    n_tasks: int,
) -> dict:
    """The machine-readable ``model_ab_report.json`` payload — both summaries,
    the diff, cost deltas, corpus hash, arm model ids, verdict."""
    return {
        "run_id": run_id,
        "verdict": verdict,
        "corpus": str(corpus_path),
        "corpus_hash": corpus_hash(corpus_path),
        "n_tasks": n_tasks,
        "arms": {"baseline": baseline_arm, "candidate": candidate_arm},
        "integrity": {
            "baseline": {
                "ok": baseline_integrity.ok,
                "expected": sorted(baseline_integrity.expected),
                "rows_scored": baseline_integrity.rows_scored,
                "rows_missing_trace": baseline_integrity.rows_missing_trace,
                "mismatches": baseline_integrity.mismatches,
            },
            "candidate": {
                "ok": candidate_integrity.ok,
                "expected": sorted(candidate_integrity.expected),
                "rows_scored": candidate_integrity.rows_scored,
                "rows_missing_trace": candidate_integrity.rows_missing_trace,
                "mismatches": candidate_integrity.mismatches,
            },
        },
        "diff": diff,
        "summaries": {
            "baseline": baseline_summary,
            "candidate": candidate_summary,
        },
        "limit": _LOCAL_LIMIT_NOTE,
    }


def render_markdown(payload: dict) -> str:
    """Human report: VERDICT banner first, then per-phase table, cost table, and
    the per-row mismatch evidence (governance: verbatim evidence)."""
    v = payload["verdict"]
    arms = payload["arms"]
    lines: list[str] = []
    lines.append(f"# Model A/B — {v}")
    lines.append("")
    lines.append(f"> **VERDICT: {v}**")
    lines.append("")
    lines.append(f"- run_id: `{payload['run_id']}`")
    lines.append(f"- baseline arm: `{arms['baseline']}`")
    lines.append(f"- candidate arm: `{arms['candidate']}`")
    lines.append(f"- corpus: `{payload['corpus']}` (hash `{payload['corpus_hash']}`)")
    lines.append(f"- tasks scored: {payload['n_tasks']}")
    lines.append("")

    # Integrity block first — a CONTAMINATED verdict is explained here.
    integ = payload["integrity"]
    lines.append("## Arm integrity")
    lines.append("")
    for arm in ("baseline", "candidate"):
        a = integ[arm]
        status = "OK" if a["ok"] else "CONTAMINATED"
        lines.append(
            f"- **{arm}** ({status}) — expected {a['expected']}, "
            f"{a['rows_scored']} rows scored, "
            f"{a['rows_missing_trace']} missing trace"
        )
        for m in a["mismatches"]:
            lines.append(f"  - {m}")
    lines.append("")

    # Per-phase parity table.
    lines.append("## Per-phase parity")
    lines.append("")
    lines.append("| phase | baseline | candidate | Δ | floor | pass |")
    lines.append("|---|---|---|---|---|---|")
    for r in payload["diff"]["phase_table"]:
        mark = "✅" if r["pass"] else "❌"
        lines.append(
            f"| {r['phase']} | {r['baseline']} | {r['candidate']} | "
            f"{r['delta']:+} | {r['floor']} | {mark} |"
        )
    lines.append("")

    if payload["diff"]["regressions"]:
        lines.append("### Regressions (drove HOLD)")
        lines.append("")
        for reg in payload["diff"]["regressions"]:
            lines.append(f"- {reg}")
        lines.append("")

    # Cost table.
    cost = payload["diff"]["cost"]
    lines.append("## Cost")
    lines.append("")
    lines.append("| metric | baseline | candidate |")
    lines.append("|---|---|---|")
    lines.append(
        f"| total USD | {cost['baseline_total_usd']} | "
        f"{cost['candidate_total_usd']} |"
    )
    lines.append(
        f"| per-task USD | {cost['baseline_per_task_usd']} | "
        f"{cost['candidate_per_task_usd']} |"
    )
    lines.append(
        f"| projected $/1k tasks (candidate) | — | "
        f"{cost['projected_per_1k_tasks_candidate']} |"
    )
    ratio = cost["ratio"]
    lines.append(f"| candidate/baseline ratio | — | {ratio} |")
    lines.append("")
    lines.append("Cost is surfaced, not auto-gated (a pricier model can be worth")
    lines.append("it) unless `--max-cost-ratio` is set.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_{payload['limit']}_")
    lines.append("")
    return "\n".join(lines)


def write_reports(out_dir: Path, payload: dict) -> tuple[Path, Path]:
    """Write both artifacts; return (md_path, json_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "model_ab_report.json"
    md_path = out_dir / "model_ab_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=False))
    md_path.write_text(render_markdown(payload))
    return md_path, json_path


# ── live drive (real LLM — opt-in, never in CI) ────────────────────────────────


def _arm_models(arm_model: str, arm_set: str | None) -> set[str]:
    """The expected-model roster for an arm: a one-name set for a pinned arm, or
    the full name roster of a profile set for a set arm."""
    if arm_set:
        from services.llm_config import build_model_registry

        models, _ = build_model_registry(arm_set)
        return {m.name for m in models}
    return {arm_model}


def _score_arm(
    rows: list[dict],
    recordings_dir: Path,
) -> tuple[dict, dict[str, list[dict]], float]:
    """Score one arm from its black-box recordings: (summary, events_by_row,
    total_cost_usd). Cost is summed from the STEP_EXECUTED ``cost_usd`` carriers
    — no new instrumentation (governance: cost is already on the wire)."""
    events_by_row: dict[str, list[dict]] = {}
    total_cost = 0.0
    for row in rows:
        case = row["case"]
        gj_id = row.get("gj_id", "")
        wf_candidates = [
            f"gj:{gj_id}:{row['trace_id']}" if gj_id else "",
            f"gj:{case}:{row['trace_id']}",
            row["trace_id"],
            gj_id,
            case,
        ]
        events: list[dict] = []
        for wf in wf_candidates:
            if not wf:
                continue
            events = _load_blackbox_events(recordings_dir, wf)
            if events:
                break
        events_by_row[case] = events
        for e in events:
            if (e.get("event_type") or "").endswith("step_executed"):
                details = e.get("details") or {}
                c = details.get("cost_usd")
                if isinstance(c, (int, float)):
                    total_cost += float(c)
    summary = score_run(rows, events_by_row)
    return summary, events_by_row, total_cost


async def _drive_arm(
    rows: list[dict],
    *,
    arm_model: str,
    arm_set: str | None,
    out_dir: Path,
) -> None:
    """Run every corpus row through the real compiled graph under this arm.

    A set arm sets ``MODEL_PROFILE_SET`` before building the graph (Auto routes
    per-tier). A pinned arm seeds ``selected_model`` into the graph input (the
    router's ``pinned_model`` branch honors it). Recordings land in the arm's own
    dir so the two arms never cross-contaminate.
    """
    import os

    from scripts.run_goaljudge_synthetic_batch import (
        build_agent_and_tools,
        run_case,
    )
    from tests.fixtures.goaljudge.case_registry import GoalJudgeCase

    # Per-arm cache_dir isolates BOTH the black-box recordings
    # (cache_dir/black_box_recordings) and the checkpoint db — the two arms never
    # cross-contaminate. The harness scores each arm from cache_dir/recordings, so
    # symlink/point that name at the real recordings dir below.
    arm_cache = out_dir / "cache"
    arm_cache.mkdir(parents=True, exist_ok=True)
    if arm_set:
        os.environ["MODEL_PROFILE_SET"] = arm_set

    workspace = AGENT_ROOT / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("WORKSPACE_DIR", str(workspace))

    agent_config, routing_config, tool_registry, agent_facts_registry = (
        build_agent_and_tools()
    )

    # A set arm lets Auto route (no extra input); a pinned arm seeds
    # selected_model exactly the way the UI pins a model.
    extra = None if arm_set else {"selected_model": arm_model}
    for row in rows:
        case = GoalJudgeCase(
            id=row["case"],
            prompt=row["prompt"],
            target_code=row.get("gj_id", ""),
            stratum=row.get("phase", ""),
            domain=row.get("phase", ""),
        )
        await run_case(
            case,
            agent_config,
            routing_config,
            tool_registry,
            agent_facts_registry,
            workspace=workspace,
            cache_dir=arm_cache,
            graph_input_extra=extra,
        )

    # Point the arm's "recordings" dir (what _score_arm reads) at the real
    # black_box_recordings the graph just wrote under arm_cache.
    recordings = out_dir / "recordings"
    real = arm_cache / "black_box_recordings"
    if not recordings.exists() and real.exists():
        recordings.symlink_to(real, target_is_directory=True)


# ── CLI ────────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    p.add_argument("--baseline", default="", help="baseline pinned model name")
    p.add_argument("--candidate", default="", help="candidate pinned model name")
    p.add_argument("--baseline-set", default=None, help="baseline profile set")
    p.add_argument("--candidate-set", default=None, help="candidate profile set")
    p.add_argument(
        "--out",
        type=Path,
        default=AGENT_ROOT / "cache" / "model_ab",
        help="base output dir; a <run-id> subdir is created under it",
    )
    p.add_argument("--tolerance", type=float, default=0.0)
    p.add_argument("--max-cost-ratio", type=float, default=None)
    p.add_argument(
        "--gate",
        action="store_true",
        help="exit non-zero on HOLD/CONTAMINATED (CI mode)",
    )
    p.add_argument(
        "--score-only",
        action="store_true",
        help=(
            "skip the live drive; score from already-written recordings under "
            "--out/<run-id>/{baseline,candidate}/recordings (re-diff a prior run)"
        ),
    )
    p.add_argument("--run-id", default=None, help="explicit run id (else timestamp)")
    p.add_argument("--limit", type=int, default=0, help="cap rows (smoke runs)")
    return p


def main(argv: list[str] | None = None) -> int:
    import time

    args = _build_parser().parse_args(argv)
    if not args.corpus.exists():
        print(f"no corpus at {args.corpus}")
        return 2

    baseline_arm = args.baseline_set or args.baseline
    candidate_arm = args.candidate_set or args.candidate
    if not baseline_arm or not candidate_arm:
        print("both a baseline and candidate arm are required "
              "(--baseline/--candidate or --baseline-set/--candidate-set)")
        return 2

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%S")
    run_dir = args.out / run_id
    baseline_dir = run_dir / "baseline"
    candidate_dir = run_dir / "candidate"

    rows = load_corpus(args.corpus)
    if args.limit:
        rows = rows[: args.limit]
    n_tasks = len(rows)

    if not args.score_only:
        import asyncio

        for arm_model, arm_set, out_dir in (
            (args.baseline, args.baseline_set, baseline_dir),
            (args.candidate, args.candidate_set, candidate_dir),
        ):
            asyncio.run(
                _drive_arm(
                    rows, arm_model=arm_model, arm_set=arm_set, out_dir=out_dir
                )
            )

    base_summary, base_events, base_cost = _score_arm(
        rows, baseline_dir / "recordings"
    )
    cand_summary, cand_events, cand_cost = _score_arm(
        rows, candidate_dir / "recordings"
    )

    base_integrity = check_arm_integrity(
        rows, base_events, _arm_models(args.baseline, args.baseline_set)
    )
    cand_integrity = check_arm_integrity(
        rows, cand_events, _arm_models(args.candidate, args.candidate_set)
    )

    diff = diff_summaries(
        base_summary,
        cand_summary,
        cost_baseline=base_cost,
        cost_candidate=cand_cost,
        n_tasks=n_tasks,
        tolerance=args.tolerance,
        max_cost_ratio=args.max_cost_ratio,
    )
    verdict = decide_verdict(diff, base_integrity, cand_integrity)

    payload = build_report_payload(
        run_id=run_id,
        corpus_path=args.corpus,
        baseline_arm=baseline_arm,
        candidate_arm=candidate_arm,
        baseline_summary=base_summary,
        candidate_summary=cand_summary,
        diff=diff,
        verdict=verdict,
        baseline_integrity=base_integrity,
        candidate_integrity=cand_integrity,
        n_tasks=n_tasks,
    )
    md_path, json_path = write_reports(run_dir, payload)

    print(f"VERDICT: {verdict}")
    print(f"  baseline={baseline_arm} candidate={candidate_arm}")
    print(f"  report: {md_path}")
    print(f"  json:   {json_path}")
    for reg in diff["regressions"]:
        print(f"  - {reg}")

    if args.gate and verdict in (HOLD, CONTAMINATED):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
