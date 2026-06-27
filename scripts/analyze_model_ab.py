#!/usr/bin/env python
"""Analyze the extensive model A/B live matrix (model_ab_extensive_e2e.plan.md §3).

The other half of the model-A/B sweep: the Playwright spec drives every
(model × case) cell through the deployed UI and writes a JSONL capture row per
run; THIS script pulls each row's Langfuse trace, gates on integrity, and
aggregates per-(model, family) behavior/cost/latency/reasoning metrics into a
cross-model comparison report.

It REUSES, unchanged (imported, not reimplemented):
  * ``scripts.analyze_planning_traces`` — ``_load_langfuse_events`` (the live
    trace pull) and ``score_run`` (the per-phase scorer, used where a row carries
    a ``want_*`` expectation).
  * ``scripts.model_ab_eval`` — ``diff_summaries`` (the PROMOTE/HOLD engine),
    ``check_arm_integrity`` (the model-identity gate), ``corpus_hash``, and the
    report-writer helpers (``_LOCAL_LIMIT_NOTE`` posture, written via a model-A/B
    report writer here).

Per the plan this script is unit-tested with NO live LLM (the metric aggregation,
the integrity exclusion, the eligibility/sampling matrix construction, and the
matched-subset comparison run on synthetic fixtures —
``tests/scripts/test_analyze_model_ab.py``). The Langfuse pull is exercised only
by the live run, never in CI.

    .venv/bin/python scripts/analyze_model_ab.py \
        --jsonl cache/model_ab_live/<run-id>/ui_batch.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from scripts.analyze_planning_traces import (  # noqa: E402
    _load_langfuse_events,
    score_run,
)
from scripts.model_ab_eval import (  # noqa: E402
    _LOCAL_LIMIT_NOTE,
    corpus_hash,
    diff_summaries,
)

_CORPUS = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "model_ab_corpus.json"

# The reasoning arms are restricted to the eligible subset (plan §2.0). Keep this
# roster in sync with the locked matrix; the eligibility PREDICATE itself lives in
# the typed corpus reader (model_ab_corpus.ts ``isReasoningEligible``) — this is
# its Python mirror, used only to know WHICH arms are sampled/restricted.
REASONING_MODELS = ("claude-opus-4-8", "deepseek-v4-pro")

# A live-run honesty stamp distinct from the model_ab_eval LOCAL note: this IS the
# deployed path (the local caveat is dropped) but single-revision + stochasticity
# caveats still apply (plan §3.4).
_LIVE_LIMIT_NOTE = (
    "LIMIT: this is the DEPLOYED Cloud Run path (the local-only caveat of the "
    "model_ab_eval pre-deploy gate is dropped). Two caveats remain stamped: the "
    "reasoning arms (Opus/Pro) ran a seeded reasoning-only sample at REPEAT=1, so "
    "their n is small and their CI wide — they are compared ONLY on the matched "
    "shared case subset (§3.3a), never on the full grid; and all arms ran against "
    "a SINGLE deployed revision, so a regression here is revision-scoped."
)


# ── eligibility / sampling matrix (plan §2.0) ──────────────────────────────────


def is_reasoning_eligible(case: dict) -> bool:
    """Python mirror of the typed reader's ``isReasoningEligible`` (plan §1.3).

    A row is Opus/Pro-eligible iff ``difficulty ∈ {L2,L3}`` OR
    ``family ∈ {stress, multi-turn}``. The single source of truth at runtime is
    the TS predicate (the driver uses it); this mirror lets the analyzer reproduce
    the constructed matrix from the corpus alone so it can report what each arm
    SHOULD have run.
    """
    difficulty = case.get("difficulty")
    family = case.get("family")
    return difficulty in ("L2", "L3") or family in ("stress", "multi-turn")


def _seeded_sample(
    cases: list[dict], *, model: str, run_id: str, fraction: float, budget: int | None
) -> list[dict]:
    """A deterministic, reproducible sample of ``cases`` for a reasoning arm.

    Seeded on ``model + run_id`` so the report can name exactly which cases the
    pricey arm ran (plan §2.0). When ``budget`` is set it is an absolute hard cap
    that overrides the fraction (L2/L3 cases fill it first — the most reasoning-
    heavy work — then multi-turn). Ordering is a stable hash of (model, run_id,
    case) so it never depends on dict/iteration order.
    """
    import hashlib

    def _key(case: dict) -> str:
        h = hashlib.sha256(f"{model}|{run_id}|{case['case']}".encode()).hexdigest()
        return h

    if budget is not None and budget >= 0:
        # Budget mode: fill from the hardest (L3, then L2) first, then the rest.
        def _difficulty_rank(case: dict) -> int:
            return {"L3": 0, "L2": 1}.get(case.get("difficulty"), 2)

        ordered = sorted(cases, key=lambda c: (_difficulty_rank(c), _key(c)))
        return ordered[:budget]

    ordered = sorted(cases, key=_key)
    n = max(1, round(len(ordered) * fraction)) if ordered else 0
    return ordered[:n]


def build_matrix(
    corpus: list[dict],
    *,
    models: list[str],
    run_id: str,
    repeat: int = 3,
    reasoning_repeat: int = 1,
    reasoning_sample: float = 0.4,
    reasoning_budget: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Construct the (model → {cases, repeat}) matrix the same way the driver does.

    Cheap/Auto arms take EVERY case at ``repeat`` runs. Reasoning arms
    (``REASONING_MODELS``) take only the reasoning-eligible cases, then a seeded
    sample of those, at ``reasoning_repeat`` (forced low). The result encodes
    "never burn the pricey models on routine work" and is exactly reproducible
    from the corpus + run_id — so the analyzer can report the planned matrix
    independently of what the spec captured (a missing planned cell is then a
    visible gap).
    """
    eligible = [c for c in corpus if is_reasoning_eligible(c)]
    matrix: dict[str, dict[str, Any]] = {}
    for model in models:
        if model in REASONING_MODELS:
            sampled = _seeded_sample(
                eligible,
                model=model,
                run_id=run_id,
                fraction=reasoning_sample,
                budget=reasoning_budget,
            )
            matrix[model] = {
                "cases": sampled,
                "repeat": reasoning_repeat,
                "reasoning": True,
                "eligible_total": len(eligible),
            }
        else:
            matrix[model] = {
                "cases": list(corpus),
                "repeat": repeat,
                "reasoning": False,
                "eligible_total": len(corpus),
            }
    return matrix


# ── capture-row loading + integrity ────────────────────────────────────────────


def load_capture_rows(jsonl_path: Path) -> list[dict]:
    """Read the spec's ``ui_batch.jsonl`` capture rows (one per run)."""
    rows = [
        json.loads(line) for line in jsonl_path.read_text().strip().split("\n") if line
    ]
    return rows


def _events_for_rows(
    rows: list[dict], *, source: str, langfuse_delay: float
) -> dict[str, list[dict]]:
    """Pull each capture row's trace events, keyed by the per-run ``trace_id``.

    Every run got a FRESH per-run trace_id (the superposition guard), so the key
    is the run's own ``trace_id`` — not the corpus trace_id. A lost trace is
    recorded as [] (a missing-trace row), never crashing the batch.
    """
    events_by_trace: dict[str, list[dict]] = {}
    for row in rows:
        trace_id = row.get("trace_id", "")
        if not trace_id:
            continue
        if trace_id in events_by_trace:
            continue
        if source == "langfuse":
            try:
                events_by_trace[trace_id] = _load_langfuse_events(trace_id)
            except Exception as exc:  # one lost trace must not sink the batch
                print(f"  warn: langfuse fetch failed for {trace_id}: {exc}")
                events_by_trace[trace_id] = []
            time.sleep(langfuse_delay)
        else:
            events_by_trace[trace_id] = []
    return events_by_trace


def _models_on_trace(events: list[dict]) -> list[str]:
    """Distinct non-empty STEP_EXECUTED ``model`` values on a trace (Recording
    pillar). An all-empty trace is the token-seam contamination."""
    seen: list[str] = []
    for e in events:
        if not (e.get("event_type") or "").endswith("step_executed"):
            continue
        details = e.get("details")
        if not isinstance(details, dict):
            continue
        model = details.get("model")
        if isinstance(model, str) and model and model not in seen:
            seen.append(model)
    return seen


def gate_row_integrity(
    row: dict, events: list[dict], registry_models: set[str] | None
) -> tuple[bool, str | None]:
    """Per-cell integrity (plan §3.2). Returns (clean, reason).

    The pinned arm must have run its model: every STEP ``model`` on the trace must
    equal the row's ``model``. For the ``Auto`` arm the model must be IN the
    registry roster (Auto may route across tiers). An empty model (token-seam) is
    CONTAMINATED. A row with no trace at all is reported by the caller (not a
    contamination on its own — it may simply be a lost recording).
    """
    pinned = row.get("model", "")
    used = _models_on_trace(events)
    if not used:
        return False, f"EMPTY-MODEL :: {row.get('case')} (no model carrier)"
    if pinned == "Auto":
        roster = registry_models or set()
        stray = [m for m in used if roster and m not in roster]
        if stray:
            return False, (
                f"AUTO-OFF-ROSTER :: {row.get('case')} ran {stray} ∉ registry"
            )
        return True, None
    stray = [m for m in used if m != pinned]
    if stray:
        return False, (f"WRONG-MODEL :: {row.get('case')} pinned={pinned} ran {stray}")
    return True, None


# ── per-(model, family) metric aggregation (plan §3.3) ─────────────────────────


def _percentile(values: list[float], pct: float) -> float | None:
    """The ``pct`` percentile (0..100) of ``values`` by nearest-rank, or None on
    an empty list. p50 == median; p95 is the tail the report headlines."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(float(ordered[0]), 3)
    # nearest-rank: index = ceil(pct/100 * n) - 1, clamped.
    import math

    rank = math.ceil((pct / 100.0) * len(ordered)) - 1
    rank = max(0, min(rank, len(ordered) - 1))
    return round(float(ordered[rank]), 3)


def _trace_tokens_cost(events: list[dict]) -> tuple[int, int, float]:
    """Sum (tokens_in, tokens_out, cost_usd) over a trace's STEP_EXECUTED
    carriers — the token/cost source already on the wire (no new instrumentation).
    """
    tin = tout = 0
    cost = 0.0
    for e in events:
        if not (e.get("event_type") or "").endswith("step_executed"):
            continue
        details = e.get("details")
        if not isinstance(details, dict):
            continue
        ti = details.get("tokens_in")
        to = details.get("tokens_out")
        c = details.get("cost_usd")
        if isinstance(ti, (int, float)):
            tin += int(ti)
        if isinstance(to, (int, float)):
            tout += int(to)
        if isinstance(c, (int, float)):
            cost += float(c)
    return tin, tout, cost


def _mean(values: list[float]) -> float:
    return round(statistics.mean(values), 3) if values else 0.0


def _median(values: list[float]) -> float:
    return round(statistics.median(values), 3) if values else 0.0


def aggregate_cell(
    rows: list[dict],
    events_by_trace: dict[str, list[dict]],
    *,
    registry_models: set[str] | None = None,
) -> dict[str, Any]:
    """Aggregate one (model, family) cell from its capture rows.

    Each row is one run. Contaminated rows (the pinned model didn't run / empty
    model) are EXCLUDED from every metric (plan §3.2 — an arm that didn't run
    what it claimed is not scored) and surfaced in ``contaminated``. Missing-trace
    rows are counted but not contaminations.

    Returns token/cost/latency/tool metrics plus the cleaned ``cases`` set (the
    distinct case ids that contributed a clean run — the matched-subset
    intersection key, §3.3a).
    """
    tokens_in: list[float] = []
    tokens_out: list[float] = []
    costs: list[float] = []
    ttft: list[float] = []
    latency: list[float] = []
    tool_calls: list[float] = []
    clean_cases: set[str] = set()
    contaminated: list[str] = []
    missing_trace: list[str] = []
    n_runs = 0

    for row in rows:
        trace_id = row.get("trace_id", "")
        events = events_by_trace.get(trace_id, [])
        if not events:
            missing_trace.append(row.get("case", trace_id))
            continue
        clean, reason = gate_row_integrity(row, events, registry_models)
        if not clean:
            contaminated.append(reason or row.get("case", trace_id))
            continue
        n_runs += 1
        clean_cases.add(row.get("case", trace_id))
        tin, tout, cost = _trace_tokens_cost(events)
        tokens_in.append(tin)
        tokens_out.append(tout)
        costs.append(cost)
        # latency / TTFT / tool-card-count come from the DOM capture row (the spec
        # measured them; they are not on the trace).
        if isinstance(row.get("ttft_ms"), (int, float)):
            ttft.append(float(row["ttft_ms"]))
        if isinstance(row.get("latency_ms"), (int, float)):
            latency.append(float(row["latency_ms"]))
        if isinstance(row.get("tool_card_count"), (int, float)):
            tool_calls.append(float(row["tool_card_count"]))

    return {
        "n_runs": n_runs,
        "cases": sorted(clean_cases),
        "tokens_in_mean": _mean(tokens_in),
        "tokens_in_median": _median(tokens_in),
        "tokens_out_mean": _mean(tokens_out),
        "tokens_out_median": _median(tokens_out),
        "cost_mean_usd": round(_mean(costs), 6),
        "cost_median_usd": round(_median(costs), 6),
        "cost_total_usd": round(sum(costs), 6),
        "projected_per_1k_tasks_usd": round(_mean(costs) * 1000, 3),
        "ttft_p50_ms": _percentile(ttft, 50),
        "ttft_p95_ms": _percentile(ttft, 95),
        "latency_p50_ms": _percentile(latency, 50),
        "latency_p95_ms": _percentile(latency, 95),
        "tool_calls_mean": _mean(tool_calls),
        "contaminated": contaminated,
        "missing_trace": missing_trace,
    }


def aggregate_matrix(
    rows: list[dict],
    events_by_trace: dict[str, list[dict]],
    *,
    registry_models: set[str] | None = None,
) -> dict[str, dict[str, dict]]:
    """Aggregate every (model, family) cell from the full capture set.

    Returns ``{model: {family: cell, ..., "__all__": cell}}`` where ``__all__`` is
    the model's across-family roll-up (every family's rows). The ``cases`` field
    on each cell is the matched-subset intersection key used by §3.3a.
    """
    by_model_family: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        model = row.get("model", "")
        family = row.get("family", "")
        by_model_family[model][family].append(row)
        by_model_family[model]["__all__"].append(row)

    out: dict[str, dict[str, dict]] = {}
    for model, families in by_model_family.items():
        out[model] = {}
        for family, family_rows in families.items():
            out[model][family] = aggregate_cell(
                family_rows, events_by_trace, registry_models=registry_models
            )
    return out


# ── matched-subset fairness comparison (plan §3.3a) ────────────────────────────


def _score_summary_for_cases(
    rows: list[dict],
    events_by_trace: dict[str, list[dict]],
    case_ids: set[str],
) -> dict:
    """Run the reused ``score_run`` over the subset of capture rows whose case is
    in ``case_ids``. The capture rows carry the ``family`` as ``phase`` so the
    reused per-phase scorer slots them in; rows without a ``want_*`` simply don't
    score a hit (behavior parity for those families is the --judge add).
    """
    subset = [r for r in rows if r.get("case") in case_ids]
    # score_run reads events_by_row keyed by case; build that view over the run's
    # own trace_id (one run per (model, case) here — the matched subset is per
    # reasoning arm, REPEAT=1).
    events_by_case: dict[str, list[dict]] = {}
    scoring_rows: list[dict] = []
    for r in subset:
        case = r.get("case", "")
        events_by_case[case] = events_by_trace.get(r.get("trace_id", ""), [])
        # score_run expects a `phase` key; map the family onto it so reused phase
        # dispatch works. (general/multi-turn/memory have no want_* phase scorer,
        # so they fall through harmlessly — the matched-subset metric the report
        # headlines is cost/latency, not the phase rate, for those families.)
        scoring_rows.append({**r, "phase": r.get("family", "")})
    return score_run(scoring_rows, events_by_case)


def matched_comparison(
    rows: list[dict],
    events_by_trace: dict[str, list[dict]],
    *,
    reasoning_model: str,
    baseline_model: str,
    matrix_aggregate: dict[str, dict[str, dict]],
) -> dict:
    """The honest head-to-head (plan §3.3a): restrict BOTH arms to the
    INTERSECTION of cases they both ran, then diff on that matched subset.

    A naive "Opus cost vs Haiku cost" compares different case sets (Opus ran only
    a sampled reasoning slice) — apples-to-oranges. The matched view is the only
    fair comparison: same cases, same difficulty. ``diff_summaries`` runs on the
    matched subset; the report states the matched-set size and that the reasoning
    arms are NOT compared on routine L1 cases by design.
    """
    reasoning_cases: set[str] = set()
    baseline_cases: set[str] = set()
    for cell in matrix_aggregate.get(reasoning_model, {}).values():
        reasoning_cases.update(cell.get("cases", []))
    for cell in matrix_aggregate.get(baseline_model, {}).values():
        baseline_cases.update(cell.get("cases", []))
    matched = reasoning_cases & baseline_cases

    reasoning_rows = [r for r in rows if r.get("model") == reasoning_model]
    baseline_rows = [r for r in rows if r.get("model") == baseline_model]

    base_summary = _score_summary_for_cases(baseline_rows, events_by_trace, matched)
    cand_summary = _score_summary_for_cases(reasoning_rows, events_by_trace, matched)

    # Cost on the matched subset only (the headline fair number).
    def _matched_cost(model_rows: list[dict]) -> float:
        total = 0.0
        for r in model_rows:
            if r.get("case") not in matched:
                continue
            _, _, c = _trace_tokens_cost(events_by_trace.get(r.get("trace_id", ""), []))
            total += c
        return total

    base_cost = _matched_cost(baseline_rows)
    cand_cost = _matched_cost(reasoning_rows)

    diff = diff_summaries(
        base_summary,
        cand_summary,
        cost_baseline=base_cost,
        cost_candidate=cand_cost,
        n_tasks=len(matched),
    )
    return {
        "reasoning_model": reasoning_model,
        "baseline_model": baseline_model,
        "matched_case_count": len(matched),
        "matched_cases": sorted(matched),
        "note": (
            "Matched on the INTERSECTION of cases both arms ran — the reasoning "
            "arm is NOT compared on routine L1 cases (it never ran them by design)."
        ),
        "diff": diff,
    }


# ── report writers (plan §3.4) ─────────────────────────────────────────────────


def build_report_payload(
    *,
    run_id: str,
    corpus_path: Path,
    baseline_model: str,
    matrix_aggregate: dict[str, dict[str, dict]],
    matched_comparisons: list[dict],
    rows: list[dict],
) -> dict:
    """The machine-readable ``model_ab_live_report.json`` payload (plan §3.4)."""
    contamination: list[str] = []
    trace_ids: list[str] = []
    for model, families in matrix_aggregate.items():
        for family, cell in families.items():
            if family == "__all__":
                continue
            for c in cell.get("contaminated", []):
                contamination.append(f"[{model}/{family}] {c}")
    for r in rows:
        tid = r.get("trace_id")
        if tid and tid not in trace_ids:
            trace_ids.append(tid)
    return {
        "run_id": run_id,
        "corpus": str(corpus_path),
        "corpus_hash": corpus_hash(corpus_path) if corpus_path.exists() else None,
        "baseline_model": baseline_model,
        "per_model_family": matrix_aggregate,
        "matched_comparisons": matched_comparisons,
        "contaminated_cells": contamination,
        "trace_ids": trace_ids,
        "limit": _LIVE_LIMIT_NOTE,
        "local_gate_note": _LOCAL_LIMIT_NOTE,
    }


def render_markdown(payload: dict) -> str:
    """Human report (plan §3.4): the headline cross-model table, per-family
    breakdowns, the matched-subset comparison verdicts, the contaminated-cell
    list, and the honest-limit stamp."""
    lines: list[str] = []
    lines.append("# Model A/B — live cross-model report")
    lines.append("")
    lines.append(f"- run_id: `{payload['run_id']}`")
    lines.append(f"- corpus: `{payload['corpus']}` (hash `{payload['corpus_hash']}`)")
    lines.append(f"- baseline model: `{payload['baseline_model']}`")
    lines.append("")

    # Headline cross-model table (rows = models, the __all__ roll-up).
    lines.append("## Headline (all families)")
    lines.append("")
    lines.append(
        "| model | runs | tokens_in (mean) | tokens_out (mean) | cost/task | "
        "TTFT p50 | latency p50 | tool calls |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for model in sorted(payload["per_model_family"]):
        cell = payload["per_model_family"][model].get("__all__", {})
        lines.append(
            f"| {model} | {cell.get('n_runs', 0)} | "
            f"{cell.get('tokens_in_mean', 0)} | {cell.get('tokens_out_mean', 0)} | "
            f"${cell.get('cost_mean_usd', 0)} | {cell.get('ttft_p50_ms')} | "
            f"{cell.get('latency_p50_ms')} | {cell.get('tool_calls_mean', 0)} |"
        )
    lines.append("")

    # Per-family breakdown.
    lines.append("## Per-family breakdown")
    lines.append("")
    for model in sorted(payload["per_model_family"]):
        lines.append(f"### {model}")
        lines.append("")
        lines.append("| family | runs | cost/task | latency p50 | latency p95 |")
        lines.append("|---|---|---|---|---|")
        for family in sorted(payload["per_model_family"][model]):
            if family == "__all__":
                continue
            cell = payload["per_model_family"][model][family]
            lines.append(
                f"| {family} | {cell.get('n_runs', 0)} | "
                f"${cell.get('cost_mean_usd', 0)} | {cell.get('latency_p50_ms')} | "
                f"{cell.get('latency_p95_ms')} |"
            )
        lines.append("")

    # Matched-subset comparisons (the fair head-to-head, §3.3a).
    if payload["matched_comparisons"]:
        lines.append("## Matched-subset comparisons (the fair head-to-head)")
        lines.append("")
        for mc in payload["matched_comparisons"]:
            v = mc["diff"]["verdict"]
            lines.append(
                f"- **{mc['reasoning_model']}** vs `{mc['baseline_model']}` "
                f"(matched on {mc['matched_case_count']} cases): **{v}**"
            )
            for reg in mc["diff"]["regressions"]:
                lines.append(f"  - {reg}")
            lines.append(f"  - {mc['note']}")
        lines.append("")

    # Contaminated cells.
    lines.append("## Contaminated cells (excluded from aggregates)")
    lines.append("")
    if payload["contaminated_cells"]:
        for c in payload["contaminated_cells"]:
            lines.append(f"- {c}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_{payload['limit']}_")
    lines.append("")
    return "\n".join(lines)


def write_reports(out_dir: Path, payload: dict) -> tuple[Path, Path]:
    """Write both artifacts; return (md_path, json_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "model_ab_live_report.json"
    md_path = out_dir / "model_ab_live_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=False))
    md_path.write_text(render_markdown(payload))
    return md_path, json_path


# ── CLI ────────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--jsonl",
        type=Path,
        required=True,
        help="the spec's ui_batch.jsonl capture file",
    )
    p.add_argument("--source", choices=["blackbox", "langfuse"], default="langfuse")
    p.add_argument(
        "--corpus", type=Path, default=_CORPUS, help="the frozen corpus (for hash)"
    )
    p.add_argument(
        "--baseline-model",
        default="gpt-4o",
        help="the model every other arm's matched comparison is run against",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output dir (default: alongside --jsonl)",
    )
    p.add_argument("--langfuse-delay", type=float, default=0.5)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.jsonl.exists():
        print(f"no capture file at {args.jsonl} — run the model-ab spec first")
        return 2
    rows = load_capture_rows(args.jsonl)
    if not rows:
        print(f"capture file {args.jsonl} is empty")
        return 2

    run_id = args.jsonl.parent.name or "run"
    out_dir = args.out or args.jsonl.parent

    # Registry roster (for the Auto-arm integrity gate). Best-effort: a missing
    # registry just disables the off-roster check, never crashes the analyzer.
    registry_models: set[str] | None = None
    try:
        from services.llm_config import build_model_registry

        models, _ = build_model_registry("all")
        registry_models = {m.name for m in models}
    except Exception:
        registry_models = None

    events_by_trace = _events_for_rows(
        rows, source=args.source, langfuse_delay=args.langfuse_delay
    )
    matrix_aggregate = aggregate_matrix(
        rows, events_by_trace, registry_models=registry_models
    )

    # Matched comparisons: each reasoning arm vs the baseline.
    matched_comparisons: list[dict] = []
    for reasoning_model in REASONING_MODELS:
        if reasoning_model not in matrix_aggregate:
            continue
        matched_comparisons.append(
            matched_comparison(
                rows,
                events_by_trace,
                reasoning_model=reasoning_model,
                baseline_model=args.baseline_model,
                matrix_aggregate=matrix_aggregate,
            )
        )

    payload = build_report_payload(
        run_id=run_id,
        corpus_path=args.corpus,
        baseline_model=args.baseline_model,
        matrix_aggregate=matrix_aggregate,
        matched_comparisons=matched_comparisons,
        rows=rows,
    )
    md_path, json_path = write_reports(out_dir, payload)

    print(f"model-ab live analysis :: source={args.source} rows={len(rows)}")
    print(f"  models: {sorted(matrix_aggregate)}")
    print(f"  report: {md_path}")
    print(f"  json:   {json_path}")
    for c in payload["contaminated_cells"]:
        print(f"  CONTAMINATED - {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
