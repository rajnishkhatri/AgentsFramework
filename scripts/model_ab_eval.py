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
import uuid
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
    rows = [json.loads(line) for line in path.read_text().strip().split("\n") if line]
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
        et = e.get("event_type") or ""
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
    verbatim evidence list the report prints.

    ``rows_scored`` / ``rows_missing_trace`` are per-arm totals. In the
    single-run path that is one trial's count; in the pass^k path
    (``_passk_arm_integrity``) they are the SUM across trials (total scored
    rows over all trials, not per-trial). A reader comparing arms should treat
    these as "instrumentation coverage," not "trials × rows"."""

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


# ── pass^k + statistical honesty (plan Track B-2 / B-3) ─────────────────────────
#
# Single-run A/B hides reliability: a 75%-per-trial arm over 3 trials is only
# ~42% all-pass (pass^3). We run the frozen corpus N times per arm with FRESH
# graph state and report pass^k -- the unbiased probability that a random size-k
# subset of a task's n trials ALL pass -- not pass^1. And at n=100, p=.5 a delta
# under ~4 points is inside the noise band, so a paired bootstrap downgrades such
# a HOLD to NOISE. These are pure functions: no graph, no I/O, no LLM.

NOISE = "NOISE"  # a HOLD whose paired-delta CI includes 0 -- not decision-grade


def _n_choose_k(n: int, k: int) -> int:
    """C(n, k) with the n<k -> 0 convention (no subset of size k exists)."""
    import math

    if k < 0 or n < 0 or k > n:
        return 0
    return math.comb(n, k)


def pass_hat_k(successes_per_task: list[int], trials: int, k: int) -> float | None:
    """Unbiased pass^k over a corpus (Chen et al. 2021, the pass@k estimator).

    ``successes_per_task[i]`` = how many of ``trials`` runs of task i passed.
    Per task the unbiased estimate that a random size-``k`` subset ALL pass is
    ``C(c, k) / C(trials, k)`` (with c successes); pass^k is the mean over tasks.

    Returns ``None`` when undecidable: no tasks, or ``k > trials`` (no size-k
    subset exists) -- never a fabricated 0.0 (AP-6).
    """
    if not successes_per_task or k < 1 or k > trials:
        return None
    denom = _n_choose_k(trials, k)
    if denom == 0:
        return None
    per_task = [_n_choose_k(c, k) / denom for c in successes_per_task]
    return sum(per_task) / len(per_task)


def paired_bootstrap_ci(
    deltas: list[float],
    *,
    iterations: int = 10_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Paired bootstrap CI on per-item deltas (candidate - baseline per task).

    The two arms run the SAME frozen corpus, so the deltas are PAIRED -- a paired
    bootstrap (resample tasks, average their deltas) is far more powerful than
    two independent CIs. Returns ``(mean_delta, lo, hi)`` at the given two-sided
    confidence. Deterministic for a fixed ``seed`` so the verdict is reproducible.

    Raises on empty input -- an empty delta list is a caller bug, not a 0-width CI.
    """
    if not deltas:
        raise ValueError("paired_bootstrap_ci: deltas must be non-empty")
    import random

    rng = random.Random(seed)
    n = len(deltas)
    mean_delta = sum(deltas) / n
    if n == 1:
        # One task: no resampling signal -- the point estimate IS the interval.
        return mean_delta, mean_delta, mean_delta
    means: list[float] = []
    for _ in range(iterations):
        resample = (deltas[rng.randrange(n)] for _ in range(n))
        means.append(sum(resample) / n)
    means.sort()
    # Percentile indices scaled by (iterations - 1) so lo/hi are symmetric about
    # the median and the hi index cannot reach ``iterations`` (no ``min`` guard
    # needed): for tail in (0, 0.5), (1-tail)*(n-1) < n-1 < n. This is the floor
    # of the standard linear-interpolation percentile index (numpy's default
    # uses interpolation between means[floor] and means[ceil]; at iterations=10k
    # the floor alone is well within the noise the bootstrap is estimating, and
    # keeping it floor-only preserves the deterministic-for-seed contract without
    # a fractional-index dependency).
    tail = (1.0 - confidence) / 2.0
    lo = means[int(tail * (iterations - 1))]
    hi = means[int((1.0 - tail) * (iterations - 1))]
    return mean_delta, lo, hi


def decide_passk_verdict(
    base_passk: float | None,
    cand_passk: float | None,
    *,
    tolerance: float,
    ci_includes_zero: bool,
    integrity_ok: bool,
    provider_contaminated: bool,
) -> str:
    """The pass^k verdict rule, as a pure function (review #6).

    Extracted from ``_run_passk`` so the rule is tested DIRECTLY rather than only
    mirrored by a parallel spec — a refactor of the caller can no longer silently
    re-collapse NOISE into HOLD without this test failing.

    Precedence (instrumentation failure dominates a behavior signal):
      1. integrity failure OR provider error OR an undecidable pass^k (``None``)
         -> ``CONTAMINATED`` (never scored as a regression).
      2. candidate pass^k below baseline past ``tolerance`` -> ``HOLD``, unless the
         paired per-task delta CI straddles 0 (``ci_includes_zero``) -> ``NOISE``.
      3. otherwise -> ``PROMOTE``.
    """
    if (
        not integrity_ok
        or provider_contaminated
        or base_passk is None
        or cand_passk is None
    ):
        return CONTAMINATED
    if cand_passk < base_passk - tolerance:
        return NOISE if ci_includes_zero else HOLD
    return PROMOTE


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
    cost_ratio = round(cost_candidate / cost_baseline, 3) if cost_baseline > 0 else None
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

    # Answer-quality block (ANSWER-corpus mode) — this is the verdict driver
    # here; the planning per-phase table below is the secondary control lens.
    if payload.get("answer"):
        ans = payload["answer"]
        lines.append("## Answer quality (verdict driver — L1 deterministic only)")
        lines.append("")
        lines.append(f"_grader: {ans.get('grader', 'L1-deterministic')}_")
        lines.append("")
        if ans.get("provider_contaminated"):
            lines.append(
                "> **⚠ PROVIDER-CONTAMINATED:** one or more cases returned a "
                "provider/transport error (litellm InternalServerError / "
                "rate-limit / Cannot connect). Accuracy below is NOT a valid "
                "model signal — re-run. Verdict forced CONTAMINATED."
            )
            lines.append("")
        lines.append("| arm | accuracy | correct/n | errored | outcomes |")
        lines.append("|---|---|---|---|---|")
        for arm in ("baseline", "candidate"):
            a = ans[arm]
            lines.append(
                f"| {arm} | {a['accuracy']:.3f} | {a['correct']}/{a['n']} | "
                f"{a.get('errored', 0)} | {a['outcomes']} |"
            )
        lines.append("")
        lines.append(
            f"accuracy Δ (candidate − baseline): **{ans['accuracy_delta']:+}**"
        )
        lines.append("")
        # L2/L3 — ungraded for verdict; GoalJudge shown as informational only.
        l2 = ans.get("l2l3_ungraded")
        if l2 and l2.get("cases"):
            lines.append("### L2/L3 — UNGRADED (pending gold set)")
            lines.append("")
            lines.append(f"_{l2['note']}_")
            lines.append("")
            gj = l2.get("goaljudge_crosscheck", {})
            if gj.get("baseline") and gj.get("candidate"):
                lines.append(
                    "GoalJudge cross-check (informational, NOT a verdict input):"
                )
                lines.append("")
                lines.append("| arm | GoalJudge acc (L2/L3) |")
                lines.append("|---|---|")
                lines.append(
                    f"| baseline | {gj['baseline']['accuracy']:.3f} "
                    f"({gj['baseline']['correct']}/{gj['baseline']['n']}) |"
                )
                lines.append(
                    f"| candidate | {gj['candidate']['accuracy']:.3f} "
                    f"({gj['candidate']['correct']}/{gj['candidate']['n']}) |"
                )
                lines.append("")
        lines.append("### Per-case answers (candidate, L1)")
        lines.append("")
        lines.append("| case | outcome | expected | got |")
        lines.append("|---|---|---|---|")
        for c in ans["candidate"]["per_case"]:
            got = (c["answer"] or "").replace("\n", " ")[:60]
            lines.append(
                f"| {c['case']} | {c['outcome']} | `{c['expected']}` | {got} |"
            )
        lines.append("")

    # Per-phase parity table.
    lines.append("## Per-phase parity (planning control lens — secondary)")
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
        f"| total USD | {cost['baseline_total_usd']} | {cost['candidate_total_usd']} |"
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


def _judge_model(arm_set: str | None) -> set[str]:
    """The GoalJudge evaluator's model name(s) — shared INFRASTRUCTURE that runs
    on every arm regardless of the pin (react_loop picks the capable-tier profile
    as ``eval_profile``; run_goaljudge_synthetic_batch enables GoalJudge). It is
    NOT the model-under-test, so it must be allowed in every arm's expected set or
    it reads as false contamination. Derived from the registry (not hardcoded): a
    pinned arm leaves MODEL_PROFILE_SET unset → the default set's capable pick; a
    set arm uses that set's capable pick."""
    from services.llm_config import build_model_registry

    # A pinned arm builds from the "all" meta-set (see _drive_arm) so the pin can
    # resolve; the judge is that set's capable pick. A set arm uses its own set.
    set_name = arm_set or "all"
    try:
        models, _ = build_model_registry(set_name)
    except Exception:
        return set()
    # react_loop picks the FIRST capable profile as eval_profile (next(... tier
    # =="capable")) — that one model is the judge, not every capable in the set.
    first_capable = next(
        (m.name for m in models if getattr(m, "tier", None) == "capable"), None
    )
    return {first_capable} if first_capable else set()


def _arm_models(arm_model: str, arm_set: str | None) -> set[str]:
    """The expected-model roster for an arm: a one-name set for a pinned arm, or
    the full name roster of a profile set for a set arm — PLUS the GoalJudge
    evaluator model (shared infra, see _judge_model)."""
    judge = _judge_model(arm_set)
    if arm_set:
        from services.llm_config import build_model_registry

        models, _ = build_model_registry(arm_set)
        return {m.name for m in models} | judge
    return {arm_model} | judge


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
        # The drive (run_goaljudge_synthetic_batch.run_case) keys the BlackBox
        # recording dir by ``workflow_id = uuid5(NAMESPACE_DNS, case.id).hex`` —
        # NOT the corpus row's stored ``trace_id`` (that was the UI run's id).
        # So the deterministic uuid5(case) is the PRIMARY join key here; the
        # other forms are kept for corpora driven through different paths.
        drive_wf = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
        wf_candidates = [
            drive_wf,
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
        truncate_eval_log,
    )

    # Isolate the eval-capture log to THIS arm: truncate the global logs/evals.log
    # before the arm drives, snapshot it into the arm's out_dir afterward. The
    # answer scorer (scripts/model_ab_answer_score.py) reads the per-arm snapshot
    # to grade each case's final answer — without isolation both arms' answers
    # would interleave in the one global log and couldn't be attributed.
    truncate_eval_log()

    # Per-arm cache_dir isolates BOTH the black-box recordings
    # (cache_dir/black_box_recordings) and the checkpoint db — the two arms never
    # cross-contaminate. The harness scores each arm from cache_dir/recordings, so
    # symlink/point that name at the real recordings dir below.
    arm_cache = out_dir / "cache"
    arm_cache.mkdir(parents=True, exist_ok=True)
    # MODEL_PROFILE_SET is process-global; both arms (and every trial) run in this
    # one process, so save the prior value and restore it in the finally below
    # (review #9). Each arm overwrites it before building, but any code that reads
    # the var BEFORE the next arm resets it would otherwise see a stale arm's set.
    _prev_profile_set = os.environ.get("MODEL_PROFILE_SET")
    try:
        if arm_set:
            # Set arm: Auto routes across the named stack.
            os.environ["MODEL_PROFILE_SET"] = arm_set
        else:
            # Pinned arm: the router can only resolve a pin to a profile that EXISTS
            # in the active registry (_pick_profile_by_name). The default "openai"
            # set has only gpt-4o/gpt-4o-mini, so pinning e.g. claude-haiku-4-5 would
            # MISS and silently fall back to the default model — invalidating the
            # arm. Build from the "all" meta-set so every pinnable model is present;
            # the pin then resolves and the arm truly runs the model-under-test.
            os.environ["MODEL_PROFILE_SET"] = "all"
        await _drive_arm_body(
            rows,
            arm_model=arm_model,
            arm_set=arm_set,
            out_dir=out_dir,
            arm_cache=arm_cache,
        )
    finally:
        if _prev_profile_set is None:
            os.environ.pop("MODEL_PROFILE_SET", None)
        else:
            os.environ["MODEL_PROFILE_SET"] = _prev_profile_set


async def _drive_arm_body(
    rows: list[dict],
    *,
    arm_model: str,
    arm_set: str | None,
    out_dir: Path,
    arm_cache: Path,
) -> None:
    """The arm-drive work, after MODEL_PROFILE_SET has been set by the caller.

    Split out of ``_drive_arm`` so the env save/restore (review #9) wraps the whole
    body in a single ``try/finally`` without indenting it.
    """
    import os

    from scripts.run_goaljudge_synthetic_batch import (
        AGENT_ROOT as _BATCH_ROOT,
        build_agent_and_tools,
        run_case,
    )
    from tests.fixtures.goaljudge.case_registry import GoalJudgeCase

    workspace = AGENT_ROOT / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("WORKSPACE_DIR", str(workspace))

    agent_config, routing_config, tool_registry, agent_facts_registry = (
        build_agent_and_tools()
    )

    # A set arm lets Auto route (no extra input); a pinned arm seeds the pin
    # exactly the way the UI does. The pin rides ``pinned_model`` (NOT
    # ``selected_model``): the router reads ``state["pinned_model"]`` from its own
    # channel (react_loop.py select_model call), because the route node writes
    # back ``selected_model``=routed-name each step, so reusing that key as the
    # pin input would misread step-1's routed model as a pin on later steps. The
    # UI rides ``input.pinned_model`` (ui_input_to_agent_request.ts) — match it.
    extra = None if arm_set else {"pinned_model": arm_model}
    for row in rows:
        # target_axes / expected_feasibility are GoalJudge *scoring* metadata;
        # the A/B drive only needs id/prompt/target_code/stratum/domain (run_case
        # reads those). Supply schema-required defaults so construction succeeds —
        # the harness scores behavior via score_run on the recordings, not via the
        # GoalJudge rubric, so these values don't affect the A/B verdict.
        case = GoalJudgeCase(
            id=row["case"],
            prompt=row["prompt"],
            target_code=row.get("gj_id", ""),
            target_axes={},
            stratum=row.get("phase", ""),
            domain=row.get("phase", ""),
            expected_feasibility="achievable",
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
    # black_box_recordings the graph just wrote under arm_cache. Use an ABSOLUTE
    # target: a symlink target is resolved relative to the LINK's directory, not
    # the CWD, so a project-relative target doubles the path (…/baseline/cache/
    # model_ab_offline/…/baseline/cache/…) and resolves to nothing. resolve()
    # makes the join correct from any CWD and for --score-only re-reads.
    recordings = out_dir / "recordings"
    real = (arm_cache / "black_box_recordings").resolve()
    if recordings.is_symlink() and not recordings.exists():
        recordings.unlink()  # stale/broken link from a prior run
    if not recordings.exists() and real.exists():
        recordings.symlink_to(real, target_is_directory=True)

    # Snapshot the arm's eval-capture log (holds each call_llm ai_response = the
    # final answer text, which the black-box recordings do NOT carry) into the
    # arm dir for the answer scorer. Copy, don't move — leaves the global log for
    # any other reader.
    eval_src = _BATCH_ROOT / "logs" / "evals.log"
    if eval_src.exists():
        (out_dir / "evals.log").write_text(eval_src.read_text())


# ── multi-trial drive (pass^k, plan Track B-2) ──────────────────────────────────


async def _drive_arm_trials(
    rows: list[dict],
    *,
    arm_model: str,
    arm_set: str | None,
    out_dir: Path,
    trials: int,
) -> None:
    """Drive an arm ``trials`` times into ``out_dir/trial_<i>`` with FRESH state.

    Each trial is a full independent ``_drive_arm`` into its own subdir, so the
    per-trial recordings/checkpoint/eval-log never cross-contaminate -- exactly
    the fresh-graph-state requirement pass^k needs (a re-used checkpointer would
    leak trial i's context into trial i+1 and collapse the variance pass^k
    measures).
    """
    for i in range(trials):
        await _drive_arm(
            rows,
            arm_model=arm_model,
            arm_set=arm_set,
            out_dir=out_dir / f"trial_{i}",
        )


def _successes_per_task(
    rows: list[dict],
    arm_dir: Path,
    trials: int,
    cases: list[str],
) -> dict[str, int]:
    """Per L1 task, count how many of ``trials`` runs produced a correct answer.

    Reads each trial's ``evals.log`` snapshot via the existing answer scorer
    (single source of truth for correctness) -- no new grading logic. A task with
    no score in a trial (missing/errored) counts as a non-pass for that trial,
    which is the conservative pass^k reading.
    """
    from scripts.model_ab_answer_score import score_answers

    counts: dict[str, int] = {c: 0 for c in cases}
    for i in range(trials):
        log = arm_dir / f"trial_{i}" / "evals.log"
        if not log.exists():
            continue
        summary = score_answers(log, cases=cases)
        for s in summary.scores:
            if s.correct and s.case in counts:
                counts[s.case] += 1
    return counts


def _recordings_dir(arm_dir: Path) -> Path:
    """Resolve an arm's recordings dir. Prefer the ``recordings`` symlink the
    drive creates; fall back to the real ``cache/black_box_recordings`` when
    the symlink is absent or broken (e.g. ``--score-only`` re-reads, which
    skip ``_drive_arm`` and so never create the link)."""
    link = arm_dir / "recordings"
    if link.exists():
        return link
    real = arm_dir / "cache" / "black_box_recordings"
    return real if real.exists() else link


def _passk_trials_with_eval_log(arm_dir: Path, trials: int) -> int:
    """How many ``trial_<i>/evals.log`` snapshots exist (0 => nothing to score)."""
    return sum(
        1 for i in range(trials) if (arm_dir / f"trial_{i}" / "evals.log").exists()
    )


def _passk_provider_contaminated(arm_dir: Path, trials: int) -> bool:
    """True if ANY trial's eval log has a provider/transport error.

    Sweeps EVERY ``call_llm`` answer in each trial log, not just the L1
    ``EXPECTED_BY_CASE`` subset that ``score_answers`` grades — a transport error
    on an L2/L3 case must contaminate the pass^k verdict too (review #2)."""
    from scripts.model_ab_answer_score import log_has_provider_error

    for i in range(trials):
        if log_has_provider_error(arm_dir / f"trial_{i}" / "evals.log"):
            return True
    return False


def _passk_arm_integrity(
    rows: list[dict],
    arm_dir: Path,
    trials: int,
    expected_models: set[str],
) -> ArmIntegrity:
    """Per-trial arm integrity — ANY trial with wrong/empty model contaminates.

    A trial that produced NO scored rows at all (no recordings) is itself a
    mismatch, not a silent pass: ``check_arm_integrity`` returns ``mismatches=[]``
    for a wholly-uninstrumented trial (every row hits ``rows_missing += 1;
    continue``), and a previous ``max(...)`` roll-up let one good trial mask a
    fully-empty sibling — a contamination that ALSO depresses pass^k, so it would
    masquerade as a real regression. We flag the empty trial explicitly and
    ``sum`` the per-trial counts so the report payload isn't undercounted.
    """
    mismatches: list[str] = []
    rows_scored = 0
    rows_missing = 0
    for i in range(trials):
        trial_dir = arm_dir / f"trial_{i}"
        _, events_by_row, _ = _score_arm(rows, _recordings_dir(trial_dir))
        trial = check_arm_integrity(rows, events_by_row, expected_models)
        rows_scored += trial.rows_scored
        rows_missing += trial.rows_missing_trace
        if trial.rows_scored == 0:
            mismatches.append(f"trial_{i}: no scored rows (no recordings)")
        for m in trial.mismatches:
            mismatches.append(f"trial_{i}: {m}")
    ok = not mismatches and rows_scored > 0
    return ArmIntegrity(
        ok=ok,
        expected=expected_models,
        rows_scored=rows_scored,
        rows_missing_trace=rows_missing,
        mismatches=mismatches,
    )


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
        help=(
            "CI mode: exit non-zero on HOLD/CONTAMINATED. NOISE and PROMOTE exit 0 "
            "(NOISE = inside the noise band, not decision-grade, so it does not "
            "block a swap)."
        ),
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
    p.add_argument(
        "--trials",
        type=int,
        default=1,
        help=(
            "run each arm N times with fresh graph state and report pass^k "
            "(plan Track B-2) instead of a single pass^1. N>=8 recommended to "
            "read pass^8. Requires --answer-score (pass/fail is per-task answer "
            "correctness). N=1 (default) keeps the single-run path unchanged."
        ),
    )
    p.add_argument(
        "--passk-k",
        type=int,
        default=0,
        help="k for pass^k (default: --trials, i.e. pass^N = all-trials-pass).",
    )
    p.add_argument(
        "--answer-score",
        action="store_true",
        help=(
            "ANSWER-corpus mode: grade each arm's final answer vs the deterministic "
            "EXPECTED table (scripts/model_ab_answer_score) and make answer accuracy "
            "the verdict (not the planning score_run, which is a control-behavior "
            "lens — design doc §6). Reads each arm's evals.log snapshot."
        ),
    )
    return p


def _run_passk(args: Any, run_dir: Path, rows: list[dict]) -> int:
    """Multi-trial pass^k path (plan Track B-2/B-3). Additive: only reached when
    ``--trials > 1``; the single-run ``main`` body is never touched.

    Drives each arm ``--trials`` times with fresh state, scores per-task answer
    correctness per trial, reports pass^k per arm + the pass^k delta, then runs a
    PAIRED bootstrap over the per-task pass-rate deltas and DOWNGRADES a
    behavior-HOLD to NOISE when the delta CI includes 0 (the delta is inside the
    noise band -- not decision-grade).
    """
    import asyncio

    from scripts.model_ab_answer_score import EXPECTED_BY_CASE

    k = args.passk_k or args.trials
    if k > args.trials:
        print(f"--passk-k={k} exceeds --trials={args.trials} (no size-k subset)")
        return 2

    case_ids = [r["case"] for r in rows]
    l1_cases = [c for c in case_ids if c in EXPECTED_BY_CASE]
    if not l1_cases:
        print(
            "pass^k needs L1 cases with a deterministic EXPECTED answer; none in "
            "this corpus. Use the GEN-L1 answer corpus."
        )
        return 2

    baseline_dir = run_dir / "baseline"
    candidate_dir = run_dir / "candidate"
    if not args.score_only:
        for arm_model, arm_set, out_dir in (
            (args.baseline, args.baseline_set, baseline_dir),
            (args.candidate, args.candidate_set, candidate_dir),
        ):
            asyncio.run(
                _drive_arm_trials(
                    rows,
                    arm_model=arm_model,
                    arm_set=arm_set,
                    out_dir=out_dir,
                    trials=args.trials,
                )
            )

    base_logs = _passk_trials_with_eval_log(baseline_dir, args.trials)
    cand_logs = _passk_trials_with_eval_log(candidate_dir, args.trials)
    if base_logs == 0 or cand_logs == 0:
        print(
            "pass^k: missing trial evals.log on one or both arms "
            f"(baseline {base_logs}/{args.trials}, candidate {cand_logs}/{args.trials})"
        )
        return 2

    base_integrity = _passk_arm_integrity(
        rows, baseline_dir, args.trials, _arm_models(args.baseline, args.baseline_set)
    )
    cand_integrity = _passk_arm_integrity(
        rows,
        candidate_dir,
        args.trials,
        _arm_models(args.candidate, args.candidate_set),
    )
    provider_contaminated = _passk_provider_contaminated(
        baseline_dir, args.trials
    ) or _passk_provider_contaminated(candidate_dir, args.trials)

    base_succ = _successes_per_task(rows, baseline_dir, args.trials, l1_cases)
    cand_succ = _successes_per_task(rows, candidate_dir, args.trials, l1_cases)

    base_passk = pass_hat_k([base_succ[c] for c in l1_cases], args.trials, k)
    cand_passk = pass_hat_k([cand_succ[c] for c in l1_cases], args.trials, k)

    # Per-task pass-RATE delta (candidate - baseline), the paired bootstrap unit.
    deltas = [
        (cand_succ[c] / args.trials) - (base_succ[c] / args.trials) for c in l1_cases
    ]
    mean_delta, lo, hi = paired_bootstrap_ci(deltas)
    ci_includes_zero = lo <= 0.0 <= hi

    passk_delta = (
        round(cand_passk - base_passk, 4)
        if (base_passk is not None and cand_passk is not None)
        else None
    )
    # Verdict rule lives in decide_passk_verdict (pure, directly tested — review #6).
    verdict = decide_passk_verdict(
        base_passk,
        cand_passk,
        tolerance=args.tolerance,
        ci_includes_zero=ci_includes_zero,
        integrity_ok=base_integrity.ok and cand_integrity.ok,
        provider_contaminated=provider_contaminated,
    )

    payload = {
        "run_id": run_dir.name,
        "verdict": verdict,
        "mode": "passk",
        "corpus": str(args.corpus),
        "corpus_hash": corpus_hash(args.corpus),
        "trials": args.trials,
        "k": k,
        "n_l1_tasks": len(l1_cases),
        "arms": {
            "baseline": args.baseline_set or args.baseline,
            "candidate": args.candidate_set or args.candidate,
        },
        "integrity": {
            "baseline": {
                "ok": base_integrity.ok,
                "expected": sorted(base_integrity.expected),
                "rows_scored": base_integrity.rows_scored,
                "rows_missing_trace": base_integrity.rows_missing_trace,
                "mismatches": base_integrity.mismatches,
            },
            "candidate": {
                "ok": cand_integrity.ok,
                "expected": sorted(cand_integrity.expected),
                "rows_scored": cand_integrity.rows_scored,
                "rows_missing_trace": cand_integrity.rows_missing_trace,
                "mismatches": cand_integrity.mismatches,
            },
        },
        "provider_contaminated": provider_contaminated,
        "passk": {
            "baseline": base_passk,
            "candidate": cand_passk,
            "delta": passk_delta,
        },
        "paired_bootstrap": {
            "mean_delta": round(mean_delta, 4),
            "ci_95": [round(lo, 4), round(hi, 4)],
            "ci_includes_zero": ci_includes_zero,
            "note": (
                "per-task pass-rate delta (candidate - baseline); CI includes 0 "
                "=> inside the noise band, HOLD downgraded to NOISE"
            ),
        },
        "successes_per_task": {
            "baseline": base_succ,
            "candidate": cand_succ,
        },
        "limit": _LOCAL_LIMIT_NOTE,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "model_ab_passk_report.json").write_text(json.dumps(payload, indent=2))

    print(f"VERDICT: {verdict}  (pass^{k} over {args.trials} trials)")
    print(f"  baseline pass^{k}={base_passk}  candidate pass^{k}={cand_passk}")
    print(f"  pass^{k} delta: {passk_delta}")
    print(
        f"  paired bootstrap mean Δ={round(mean_delta, 4)} "
        f"95% CI [{round(lo, 4)}, {round(hi, 4)}] "
        f"(includes 0: {ci_includes_zero})"
    )
    if args.gate and verdict in (HOLD, CONTAMINATED):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    import time

    args = _build_parser().parse_args(argv)
    if not args.corpus.exists():
        print(f"no corpus at {args.corpus}")
        return 2

    baseline_arm = args.baseline_set or args.baseline
    candidate_arm = args.candidate_set or args.candidate
    if not baseline_arm or not candidate_arm:
        print(
            "both a baseline and candidate arm are required "
            "(--baseline/--candidate or --baseline-set/--candidate-set)"
        )
        return 2

    # F2: a SET arm runs Auto routing, but the "all" set is PIN-ONLY — its first
    # reasoning profile is opus-4-8, so an Auto run on "all" escalates into Opus
    # on any failure, skewing the arm's cost/behavior away from the set under
    # test. Reject it explicitly (pinned arms reach "all" internally via
    # MODEL_PROFILE_SET so the pin resolves — that path is unaffected; this guard
    # is only on the Auto-routing --*-set selectors). Fail loud, not silently.
    for flag, value in (
        ("--baseline-set", args.baseline_set),
        ("--candidate-set", args.candidate_set),
    ):
        if value == "all":
            print(
                f"{flag}=all is rejected: the 'all' set is pin-only (Auto would "
                f"escalate into opus-4-8). Use a routable set "
                f"(openai/anthropic/deepseek) for a set arm, or pin a single "
                f"model with --baseline/--candidate."
            )
            return 2

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%S")
    run_dir = args.out / run_id
    baseline_dir = run_dir / "baseline"
    candidate_dir = run_dir / "candidate"

    rows = load_corpus(args.corpus)
    if args.limit:
        rows = rows[: args.limit]
    n_tasks = len(rows)

    # Multi-trial pass^k path (plan Track B-2/B-3) -- additive, self-contained.
    # The default --trials=1 falls straight through to the single-run path below.
    if args.trials > 1:
        if not args.answer_score:
            print("--trials>1 requires --answer-score (pass/fail = answer correctness)")
            return 2
        return _run_passk(args, run_dir, rows)

    if not args.score_only:
        import asyncio

        for arm_model, arm_set, out_dir in (
            (args.baseline, args.baseline_set, baseline_dir),
            (args.candidate, args.candidate_set, candidate_dir),
        ):
            asyncio.run(
                _drive_arm(rows, arm_model=arm_model, arm_set=arm_set, out_dir=out_dir)
            )

    base_summary, base_events, base_cost = _score_arm(
        rows, _recordings_dir(baseline_dir)
    )
    cand_summary, cand_events, cand_cost = _score_arm(
        rows, _recordings_dir(candidate_dir)
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

    # ── ANSWER-corpus mode: grade actual answers, make accuracy the verdict ──
    answer_block = None
    if args.answer_score:
        from scripts.model_ab_answer_score import (
            EXPECTED_BY_CASE,
            score_answers,
            score_answers_goaljudge,
        )

        # VERDICT is L1-DETERMINISTIC ONLY (decision 2026-06-25): the hardened
        # deterministic scorer is the only trustworthy automated grader. L2/L3 use
        # prose answers — their grading is DEFERRED to the blind-adjudication /
        # gold-set process (docs/plans/model_ab_l2l3_blind_adjudication.plan.md);
        # GoalJudge on L2/L3 is off-label + over-strict, so it is shown as an
        # informational cross-check ONLY, never as a verdict input.
        case_ids = [r["case"] for r in rows]
        l1_cases = [c for c in case_ids if c in EXPECTED_BY_CASE]
        l2l3_cases = [c for c in case_ids if c not in EXPECTED_BY_CASE]

        base_ans = score_answers(baseline_dir / "evals.log", cases=l1_cases)
        cand_ans = score_answers(candidate_dir / "evals.log", cases=l1_cases)

        # PROVIDER-ERROR GUARD (dominant): a run with transport/provider failures
        # (litellm InternalServerError, rate-limit, Cannot connect) is NOT a model
        # signal — its accuracy is meaningless. Flag CONTAMINATED, never score 0.0.
        provider_contaminated = base_ans.contaminated or cand_ans.contaminated

        answer_regression = cand_ans.accuracy < (base_ans.accuracy - args.tolerance)
        if not (base_integrity.ok and cand_integrity.ok) or provider_contaminated:
            verdict = CONTAMINATED
        elif answer_regression:
            verdict = HOLD
        else:
            verdict = PROMOTE

        # L2/L3 GoalJudge cross-check — INFORMATIONAL ONLY (ungraded for verdict).
        base_gj = (
            score_answers_goaljudge(baseline_dir / "evals.log", l2l3_cases)
            if l2l3_cases
            else None
        )
        cand_gj = (
            score_answers_goaljudge(candidate_dir / "evals.log", l2l3_cases)
            if l2l3_cases
            else None
        )

        def _arm_block(ans):
            return {
                "accuracy": ans.accuracy,
                "correct": ans.correct,
                "n": ans.n,
                "errored": ans.errored,
                "contaminated": ans.contaminated,
                "outcomes": ans.outcomes(),
                "per_case": [
                    {
                        "case": s.case,
                        "outcome": s.outcome,
                        "expected": s.expected,
                        "answer": s.answer,
                    }
                    for s in ans.scores
                ],
            }

        answer_block = {
            "grader": "L1-deterministic (verdict); L2/L3 ungraded (pending gold set)",
            "provider_contaminated": provider_contaminated,
            "baseline": _arm_block(base_ans),
            "candidate": _arm_block(cand_ans),
            "accuracy_delta": round(cand_ans.accuracy - base_ans.accuracy, 4),
            "l2l3_ungraded": {
                "cases": l2l3_cases,
                "note": "prose answers; verdict-excluded. GoalJudge shown as "
                "informational cross-check only — see "
                "docs/plans/model_ab_l2l3_blind_adjudication.plan.md",
                "goaljudge_crosscheck": {
                    "baseline": (
                        {
                            "accuracy": base_gj.accuracy,
                            "correct": base_gj.correct,
                            "n": base_gj.n,
                        }
                        if base_gj
                        else None
                    ),
                    "candidate": (
                        {
                            "accuracy": cand_gj.accuracy,
                            "correct": cand_gj.correct,
                            "n": cand_gj.n,
                        }
                        if cand_gj
                        else None
                    ),
                },
            },
        }

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
    if answer_block is not None:
        payload["answer"] = answer_block
    md_path, json_path = write_reports(run_dir, payload)

    print(f"VERDICT: {verdict}")
    print(f"  baseline={baseline_arm} candidate={candidate_arm}")
    if answer_block is not None:
        print(
            f"  answer accuracy: baseline={answer_block['baseline']['accuracy']:.3f} "
            f"candidate={answer_block['candidate']['accuracy']:.3f} "
            f"(Δ {answer_block['accuracy_delta']:+})"
        )
    print(f"  report: {md_path}")
    print(f"  json:   {json_path}")
    for reg in diff["regressions"]:
        print(f"  - {reg}")

    if args.gate and verdict in (HOLD, CONTAMINATED):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
