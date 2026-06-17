"""Generate a case-by-case markdown walkthrough of the planning-floor corpus.

Reads cache/goaljudge_eval/planning_floor_strata.jsonl, runs each surface
against the REAL components (no LLM/network), and writes a per-case report:
prompt, expected vs actual, the deterministic signals that drove the result,
and a pass/miss verdict with reasoning.

Every "actual" value is COMPUTED here, never transcribed — so the report can be
regenerated and stays truthful.

    python scripts/report_planning_floor_walkthrough.py
    -> docs/research/planning_floor_baseline_walkthrough.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from components.plan_builder import (
    PlanArtifact,
    _GENERIC_TAIL_CONDITION,
    _extract_branches,
    derive_success_conditions,
    plan_is_stale,
    validate_plan_mece,
)
from components.router import select_planning_depth
from components.task_understanding import GENERIC_TAIL_CONDITION as _TU_TAIL

_CORPUS = Path("cache/goaljudge_eval/planning_floor_strata.jsonl")
_OUT = Path("docs/research/planning_floor_baseline_walkthrough.md")
# Optional Tier 1 fixture (planning_floor_outcome_validation.tier1_results.md).
# If present, a cross-check section is appended; if absent, it is skipped with
# a one-line pointer so the deterministic walkthrough still regenerates cleanly.
_TIER1_FIXTURE = Path("cache/goaljudge_eval/planning_floor_understanding.jsonl")
_DEPTH_CAP = {"L0": 1, "L1": 3, "L2": 5}

# Mirror of the signals select_planning_depth reads, for the "signals" column.
_MULTI_PART = ("compare", "trade-off", "tradeoff", "architecture", "migration",
               "refactor", "roadmap", "design")
_INCIDENT = ("trace how", "figure out", "root cause", "propagat", "identify every",
             "times out", "sometimes", "intermitt", "race condition")
_STRONG_VERBS = ("plan", "design", "refactor", "audit", "migrate", "implement",
                 "build", "investigate", "debug", "diagnose", "optimize",
                 "redesign", "trace", "compare")


def _depth_signals(text: str) -> str:
    low = (text or "").lower()
    words = [w for w in low.replace("\n", " ").split(" ") if w]
    wc = len(words)
    sig = [f"wc={wc}"]
    markers = [m for m in _MULTI_PART if m in low]
    if markers:
        sig.append("markers=[" + ",".join(markers) + "]")
    if any(c in low for c in (" and ", " then ", " also ", "\n- ", "\n1.")):
        sig.append("conj")
    enum = len(re.findall(r"\([1-9]\)", text or ""))
    if enum:
        sig.append(f"enum={enum}")
    inc = [m for m in _INCIDENT if m in low]
    if inc:
        sig.append("incident=[" + ",".join(inc) + "]")
    fw = words[0] if words else ""
    if fw in _STRONG_VERBS:
        sig.append(f"strong-verb={fw}")
    return ", ".join(sig)


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def _run_case(row: dict) -> list[dict]:
    """Return one result dict per scored surface."""
    out: list[dict] = []
    ti = row.get("task_input", "")

    if row.get("want_depth") is not None:
        got, reason = select_planning_depth(
            task_input=ti, task_tool_results_count=int(row.get("task_tool_results_count") or 0))
        out.append({
            "surface": "depth",
            "expected": row["want_depth"], "actual": got,
            "ok": got == row["want_depth"],
            "signals": f"count={row.get('task_tool_results_count', 0)}; "
                       + _depth_signals(ti) + f"; reason={reason}",
        })

    if row.get("want_branch_count") is not None:
        br = _extract_branches(ti)
        out.append({
            "surface": "branches",
            "expected": row["want_branch_count"], "actual": len(br),
            "ok": len(br) == row["want_branch_count"],
            "signals": "branches=[" + " | ".join(br) + "]",
        })

    if row.get("want_min_conditions") is not None or row.get("want_generic_tail") is not None:
        br = _extract_branches(ti)
        conds = derive_success_conditions(br)
        tail = _GENERIC_TAIL_CONDITION in conds
        exp = row.get("want_min_conditions")
        ok = (exp is None or len(conds) == exp) and (
            row.get("want_generic_tail") is None or tail == bool(row["want_generic_tail"]))
        out.append({
            "surface": "conditions",
            "expected": f"{exp} conds, tail={row.get('want_generic_tail')}",
            "actual": f"{len(conds)} conds, tail={tail}",
            "ok": ok,
            "signals": f"{len(br)} branches -> {len(conds)} conditions (incl. generic tail)",
        })

    if row.get("want_mece_valid") is not None:
        plan = PlanArtifact(**row["mece_plan"])
        res = validate_plan_mece(plan)
        valid_ok = res.is_valid == bool(row["want_mece_valid"])
        issue_ok = (not row.get("want_mece_issue")
                    or any(row["want_mece_issue"] in i for i in res.issues))
        out.append({
            "surface": "mece",
            "expected": f"valid={row['want_mece_valid']}"
                        + (f", issue~'{row['want_mece_issue']}'" if row.get("want_mece_issue") else ""),
            "actual": f"valid={res.is_valid}",
            "ok": valid_ok and issue_ok,
            "signals": "; ".join(res.issues) or "no issues",
        })

    if row.get("want_stale") is not None:
        plan = PlanArtifact(
            ordered_steps=[{"step_id": 1, "title": "a", "goal": "build"},
                           {"step_id": 2, "title": "b", "goal": "verify"}],
            success_conditions=["done"])
        got = plan_is_stale(plan, row.get("last_tool_result"))
        out.append({
            "surface": "replan",
            "expected": row["want_stale"], "actual": got,
            "ok": got == bool(row["want_stale"]),
            "signals": f"last_tool_result={row.get('last_tool_result')}",
        })

    return out


def _tu_effective_len(conditions: list[str]) -> int:
    """Checklist length with the always-appended generic tail removed.

    Same rule as ``scripts/diagnose_understanding_vs_depth.py._effective_len`` so
    the cross-check matches the Tier 1 results note exactly.
    """
    real = [c for c in conditions if c.strip() != _TU_TAIL.strip()]
    if len(real) == len(conditions) and conditions:
        return max(0, len(conditions) - 1)
    return len(real)


def _emit_tier1_crosscheck(lines: list[str]) -> None:
    """Append the Tier 1 (TaskUnderstanding vs depth-cap) cross-check, if captured.

    Joins each depth prompt's DETERMINISTIC result (did it fire the right depth?)
    with the Tier 1 EVIDENCE (does the LLM-generated checklist exceed the fired
    step cap?). Read-only over the fixture; no LLM calls here.
    """
    A = lines.append
    A("## Tier 1 cross-check — checklist length vs fired depth cap\n")
    if not _TIER1_FIXTURE.exists():
        A("*(Tier 1 fixture not captured — run "
          "`python scripts/diagnose_understanding_vs_depth.py --capture` to populate "
          f"`{_TIER1_FIXTURE}`, then regenerate this report. See "
          "[`planning_floor_outcome_validation.tier1_results.md`]"
          "(planning_floor_outcome_validation.tier1_results.md).)*\n")
        return

    recs = [json.loads(l) for l in _TIER1_FIXTURE.read_text().splitlines() if l.strip()]
    A("Cross-references the deterministic depth verdict above with the **Tier 1** "
      "offline probe ([`planning_floor_outcome_validation.tier1_results.md`]"
      "(planning_floor_outcome_validation.tier1_results.md)): a once-captured, "
      "3-sample `TaskUnderstanding.success_conditions` checklist per prompt. The "
      "checklist is generated **at plan time, independent of the fired depth**, so "
      "`effective_len > cap` (generic tail removed) is an offline under-budgeting "
      "signal. **Caveat (results §2a):** checklist length over-reads the step cap by "
      "a near-constant offset — every L0 task is \"over cap\" too — so read the trap "
      "rows *relative to* their correctly-fired L1 peers, not in absolute terms.\n")
    A("| id | det. depth (want→fired) | det. ✓ | cap | checklist len ×3 | spread | over cap? |")
    A("|----|-------------------------|--------|-----|------------------|--------|-----------|")
    for rec in recs:
        ti = rec["task_input"]
        fired, _ = select_planning_depth(task_input=ti, task_tool_results_count=0)
        cap = _DEPTH_CAP[fired]
        want = rec["want_depth"]
        det_ok = "✅" if want == fired else "❌"
        lens = [_tu_effective_len(s["conditions"]) for s in rec["samples"]
                if not s.get("error")]
        if not lens:
            lens_s, spread_s, over = "(gate-rej)", "—", "—"
        else:
            lens_s = ",".join(str(n) for n in lens)
            spread_s = str(max(lens) - min(lens))
            n_over = sum(1 for n in lens if n > cap)
            over = ("**yes**" if n_over * 2 > len(lens) else "no") + (
                " ⚠FLIP" if 0 < n_over < len(lens) else "")
        A(f"| `{rec['id']}` | {want}→{fired} | {det_ok} | {cap} | {lens_s} | "
          f"{spread_s} | {over} |")
    A("")
    A("**Reading.** The 3 multi-marker prose traps (`depth-l2-trap-1/2/3`) fire L1 "
      "(cap 3) yet stably return a 4-item checklist (spread 0) → the floor budgets "
      "fewer steps than the task's own success criteria, corroborating the divergence "
      "deep-dive above. `depth-l2-trap-4` stably returns 3 (a corpus-label question, "
      "not a floor miss). Rows marked ⚠FLIP straddle the cap across samples (the "
      "3-sample variance guard surfaced them) — honestly inconclusive, not signal. "
      "This raises the ROI of an Option A `distinct_marker_count >= 3 -> L2` rule but, "
      "per the §2a caveat, is *corroborating* not *causal* — a live A/B (Tier 2) "
      "remains the only test of \"deeper → better answer.\"\n")


# Group corpus by surface for section ordering.
_SURFACE_TITLES = {
    "depth": "1. Depth selection (`select_planning_depth`)",
    "branches": "2. Branch extraction (`_extract_branches`)",
    "conditions": "3. Success conditions (`derive_success_conditions`)",
    "mece": "4. MECE structure gate (`validate_plan_mece`)",
    "replan": "5. Replan gate (`plan_is_stale`)",
}
_ORDER = ["depth", "branches", "conditions", "mece", "replan"]


def main() -> None:
    rows = [json.loads(l) for l in _CORPUS.read_text().splitlines() if l.strip()]

    # primary surface of each row = its declared "surface" field
    scored: list[tuple[dict, dict]] = []
    surface_tally: dict[str, list[bool]] = {s: [] for s in _ORDER}
    for row in rows:
        for res in _run_case(row):
            scored.append((row, res))
            surface_tally[res["surface"]].append(res["ok"])

    lines: list[str] = []
    A = lines.append
    A("# Planning-floor baseline — case-by-case walkthrough\n")
    A("**Generated:** 2026-06-17 by `scripts/report_planning_floor_walkthrough.py` "
      "(every *Actual* value is computed live against `components/`, not transcribed).\n")
    A("**Corpus:** `cache/goaljudge_eval/planning_floor_strata.jsonl` "
      f"({len(rows)} rows) · **Harness:** `scripts/diagnose_planning_floor.py`\n")
    A("**Scope:** the case-by-case body is offline, deterministic, zero-cost — no LLM, "
      "no network, no deploy; each row is scored only on the surface(s) whose `want_*` "
      "field is set. The final **Tier 1 cross-check** section additionally reads a "
      "once-captured LLM checklist fixture (if present) for comparison.\n")

    # scorecard
    A("## Scorecard\n")
    A("| Surface | Pass | Total | % |")
    A("|---------|------|-------|---|")
    gt = go = 0
    for s in _ORDER:
        t = surface_tally[s]
        if not t:
            continue
        ok = sum(t)
        gt += len(t)
        go += ok
        A(f"| {s} | {ok} | {len(t)} | {100*ok/len(t):.1f}% |")
    A(f"| **OVERALL** | **{go}** | **{gt}** | **{100*go/gt:.1f}%** |\n")

    # per-surface sections
    for s in _ORDER:
        cases = [(r, res) for (r, res) in scored if res["surface"] == s]
        if not cases:
            continue
        A(f"## {_SURFACE_TITLES[s]}\n")
        A("| # | id | Prompt / input | Expected | Actual | ✓ | Signals & reasoning |")
        A("|---|----|----------------|----------|--------|---|---------------------|")
        for i, (row, res) in enumerate(cases, 1):
            verdict = "✅" if res["ok"] else "❌ **MISS**"
            prompt = row.get("task_input") or (
                "(plan fixture)" if s == "mece" else "")
            prompt = _md_escape(prompt)[:90] + ("…" if len(prompt) > 90 else "")
            note = _md_escape(row.get("note", ""))
            signals = _md_escape(str(res["signals"]))[:160]
            A(f"| {i} | `{row['id']}` | {prompt} | `{res['expected']}` | "
              f"`{res['actual']}` | {verdict} | {signals}<br/>**why:** {note} |")
        A("")

    # divergence deep-dive
    misses = [(r, res) for (r, res) in scored if not res["ok"]]
    A("## Divergence deep-dive\n")
    if not misses:
        A("No divergences — every scored surface matched its authored expectation.\n")
    else:
        A(f"{len(misses)} divergence(s). Each is a recorded baseline miss, surfaced not hidden.\n")
        A("**Root cause (all four are one failure mode).** The additive scorer needs "
          "`score >= 3` for L2. `has_multi_part_marker` contributes **+1 regardless of "
          "how many markers match** (it is a single boolean), and word count only adds "
          "points at >=35 / >=80. So a multi-marker *prose* task — many strong verbs but "
          "<35 words and no enumeration — tops out at score 2 (marker +1, conjunction +1) "
          "and fires `moderate-complexity-initial-task` (L1). Enumeration `(1)(2)(3)` is the "
          "orthogonal signal that pushes the comparable L2 rows over the line; prose lacks it. "
          "This is the single systematic residual and the only thing an Option A/B depth "
          "rule could move (e.g. a `distinct_marker_count >= 3 -> L2` rule).\n")
        for row, res in misses:
            A(f"### `{row['id']}` — {res['surface']} (family: `{row['family']}`)\n")
            A(f"- **Prompt:** {row.get('task_input', '')}")
            A(f"- **Expected:** `{res['expected']}`  **Actual:** `{res['actual']}`")
            A(f"- **Signals:** {res['signals']}")
            A(f"- **Reading:** {row.get('note', '')}\n")

    _emit_tier1_crosscheck(lines)

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {_OUT} ({len(scored)} scored cases, {len(misses)} divergences)")


if __name__ == "__main__":
    main()
