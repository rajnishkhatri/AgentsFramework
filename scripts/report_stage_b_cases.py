"""Stage B case-by-case report: join the DOM results with the Langfuse traces.

Connects the two T3 Stage-B evidence sources keyed on the deterministic
``trace_id``:

  1. ``cache/planning_stress/ui_batch.jsonl`` — what the BROWSER received per
     case (response_chars, tool_card_count, the answer text). Append-only across
     runs; we keep the LAST row per case (latest run wins).
  2. Langfuse trace observations — what the GRAPH did server-side (supervisor
     fan_out|decline decision, # delegation_requested Sends, the fanout_join
     carrier with branches_total/completed/join_chars).

Plus the corpus expectation (``want_fanout``) so each case gets a verdict.

The point of the join: the DECISION can be correct server-side while the
EXECUTION answer never reaches the browser (the Stage-B empty-answer defect).
Only by putting graph-side join_chars next to browser-side response_chars,
per case, does that split become visible.

Usage:
    .venv/bin/python scripts/report_stage_b_cases.py            # dry: print
    .venv/bin/python scripts/report_stage_b_cases.py --write    # + write md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Reuse the analyzer's source-agnostic carrier extractors so this report and the
# gate read identical fields from the same traces (no second interpretation).
from analyze_planning_traces import (  # type: ignore
    _fanout_join,
    _load_langfuse_events,
    _step_planned,
    _supervisor_decision,
)


def _supervisor_branch_count(events: list[dict]) -> int | None:
    """The supervisor's proposed branch count from its STEP_PLANNED carrier.

    These traces carry NO ``delegation_requested`` observation — the fan-out
    signal lives entirely in ``supervisor_decision`` / ``supervisor_branch_count``
    (and the ``fanout_join`` carrier). Under reflexion the supervisor fires more
    than once; take the max proposed count.
    """
    counts = [
        int(s["supervisor_branch_count"])
        for s in _step_planned(events)
        if str(s.get("supervisor_branch_count", "")).isdigit()
    ]
    return max(counts) if counts else None


def _join_count(events: list[dict]) -> int:
    """How many fanout_join carriers fired (>1 == fanned out under reflexion)."""
    return sum(
        1
        for s in _step_planned(events)
        if str(s.get("fanout_join", "")).lower() == "true"
    )


def _supervisor_decisions(events: list[dict]) -> list[str]:
    """ALL supervisor decisions on the trace, in order."""
    return [
        str(s["supervisor_decision"])
        for s in _step_planned(events)
        if "supervisor_decision" in s
    ]


def _run_started_count(events: list[dict]) -> int:
    """Number of ``run.started`` markers. One run emits exactly one."""
    return sum(
        1 for e in events if (e.get("event_type") or "").endswith("run_started")
    )


def superposition_smell(events: list[dict]) -> str | None:
    """Detect a trace contaminated by >1 run superimposed under one trace_id.

    Two signals, because each alone has a blind spot:

    1. **>1 ``run.started``** — the PRIMARY, unambiguous signal. One run emits
       exactly one ``run.started``; more means distinct runs landed on the same
       trace_id (the static-trace_id reuse bug). This catches SAME-decision
       same-prompt reruns (e.g. fan_out×N) that signal 2 misses — and it does
       NOT false-fire on a single reflexion run that re-decides several times
       (run.started stays 1 there).
    2. **both ``fan_out`` and ``decline``** decisions present — a back-compat
       fallback for older traces that predate the run.started carrier.

    Returns a human string when contaminated, else None. Explainability /
    compliance require one trace == one run; the report surfaces this per row
    instead of silently reading the first carrier.
    """
    runs = _run_started_count(events)
    if runs > 1:
        return f"CONTAMINATED: {runs} run.started markers (>1 run superimposed on one trace_id)"
    decisions = set(_supervisor_decisions(events))
    if {"fan_out", "decline"} <= decisions:
        n = len(_supervisor_decisions(events))
        return f"CONTAMINATED: {n} decisions, both fan_out+decline (>1 run superimposed)"
    return None

AGENT_ROOT = Path(__file__).resolve().parents[1]
UI_BATCH = AGENT_ROOT / "cache" / "planning_stress" / "ui_batch.jsonl"
CORPUS = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "planning_stress_corpus.json"
OUT = AGENT_ROOT / "docs" / "plans" / "t3_stage_b_case_report.md"

FALLBACK = "completed without producing any output"


def _shot_link(d: dict) -> str:
    """Relative markdown link from the report (docs/plans/) to the PNG, if it
    exists on disk. ``screenshot_path`` is repo-root-relative in the row."""
    sp = d.get("screenshot_path")
    if not sp:
        return "—"
    abs_path = AGENT_ROOT / sp
    if not abs_path.exists():
        return "—"
    # report is at docs/plans/ -> two hops up to repo root, then the rel path.
    return f"[png](../../{sp})"


def _latest_fanout_rows() -> dict[str, dict]:
    """Last ui_batch row per fanout case (latest run wins)."""
    seen: dict[str, dict] = {}
    for line in UI_BATCH.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("phase") == "fanout":
            seen[r["case"]] = r
    return seen


def _corpus_expectations() -> dict[str, dict]:
    raw = json.loads(CORPUS.read_text())
    rows = raw if isinstance(raw, list) else raw.get("rows") or raw.get("cases") or []
    return {r["case"]: r for r in rows if "FANOUT" in str(r.get("case", ""))}


def _family(case: str) -> str:
    if "-independent-" in case:
        return "independent"
    if "-decline-" in case:
        return "decline"
    if "-fault-" in case:
        return "fault"
    return "control"


def build_records() -> list[dict]:
    dom = _latest_fanout_rows()
    corpus = _corpus_expectations()
    cases = sorted(set(dom) | set(corpus))

    records: list[dict] = []
    for case in cases:
        d = dom.get(case)
        c = corpus.get(case, {})
        want_fanout = bool(c.get("want_fanout"))
        rec: dict = {
            "case": case,
            "family": _family(case),
            "want_fanout": want_fanout,
            "want_branch_count": c.get("want_branch_count"),
            "ran": d is not None,
        }
        if d is None:
            rec["verdict"] = "NOT-RUN"
            records.append(rec)
            continue

        trace_id = d.get("trace_id", "")
        rec["trace_id"] = trace_id
        rec["dom_chars"] = d.get("response_chars")
        rec["dom_cards"] = d.get("tool_card_count")
        rec["is_fallback"] = FALLBACK in (d.get("response_text") or "")
        rec["shot"] = _shot_link(d)

        # Server-side carriers from Langfuse (best-effort; trace may be missing).
        decision = branch_count = join = None
        joins = 0
        trace_err = None
        smell = None
        try:
            events = _load_langfuse_events(trace_id)
            smell = superposition_smell(events)
            decision = _supervisor_decision(events)
            branch_count = _supervisor_branch_count(events)
            joins = _join_count(events)
            join = _fanout_join(events)
        except Exception as exc:  # noqa: BLE001
            trace_err = f"{type(exc).__name__}: {exc}"
        rec["trace_err"] = trace_err
        rec["smell"] = smell
        rec["supervisor_decision"] = decision
        rec["branch_count"] = branch_count
        rec["joins"] = joins  # >1 == fanned out again under reflexion
        # These traces carry no delegation_requested obs; the decision carrier
        # (+ a real fanout_join) IS the fan-out signal.
        got_fanout = decision == "fan_out" and join is not None
        rec["got_fanout"] = got_fanout
        if join:
            rec["join_chars"] = join.get("join_chars")
            rec["branches_total"] = join.get("branches_total")
            rec["branches_completed"] = join.get("branches_completed")

        # ── Verdict: split DECISION correctness from EXECUTION delivery ──
        # A contaminated trace cannot be scored — its carriers blend >1 run.
        # Surface it loudly (compliance) rather than emitting a false verdict.
        if smell:
            rec["verdict"] = "CONTAMINATED (untrustworthy trace)"
            records.append(rec)
            continue
        decision_ok = got_fanout == want_fanout
        delivered = not rec["is_fallback"] and (rec["dom_chars"] or 0) > 60
        if not decision_ok:
            # The expensive cell only when we fanned out a row that should not.
            rec["verdict"] = "DECISION-WRONG (GAIA fp)" if got_fanout else "MISSED (cheap)"
        elif want_fanout and not delivered:
            rec["verdict"] = "EXEC-EMPTY (decision ok, answer lost)"
        else:
            rec["verdict"] = "OK"
        records.append(rec)
    return records


def render(records: list[dict]) -> str:
    L: list[str] = []
    L.append("# T3 Stage B — Case-by-case report (DOM ⨝ Langfuse)\n")
    L.append(
        "Each fan-out case joined on the deterministic `trace_id`: the **browser** "
        "result (`cache/planning_stress/ui_batch.jsonl`, latest run per case) next "
        "to the **graph** carriers pulled live from Langfuse. The join makes the "
        "Stage-B split legible — a correct server-side fan-out *decision* whose "
        "*answer* never reached the browser.\n"
    )
    L.append("> `chars`/`cards` = browser-side; `decision`/`br#`/`joins`/"
             "`join_chars`/`br c/t` = graph-side (Langfuse); `want` = corpus "
             "expectation. `joins`>1 = fanned out again under reflexion. These "
             "traces carry no `delegation_requested` obs — the `decision` + a real "
             "`fanout_join` carrier IS the fan-out signal.\n")

    # legend
    L.append("**Verdict key:** `OK` = decision correct + answer delivered · "
             "`EXEC-EMPTY` = correct fan-out, empty browser answer (the defect) · "
             "`MISSED` = should have fanned out, ran sequential (cheap, un-gated) · "
             "`DECISION-WRONG` = fanned out a dependent chain (GAIA fp) · "
             "`NOT-RUN` = timed out / no trace.\n")

    header = (
        "| Case | Fam | want | decision | br# | joins | join_chars | br c/t | "
        "chars | cards | fallback | shot | Verdict |"
    )
    sep = "|" + "---|" * 13
    for fam in ("independent", "decline", "fault", "control"):
        fam_recs = [r for r in records if r["family"] == fam]
        if not fam_recs:
            continue
        L.append(f"\n## {fam.title()} family ({len(fam_recs)})\n")
        L.append(header)
        L.append(sep)
        for r in fam_recs:
            if not r.get("ran"):
                L.append(
                    f"| {r['case']} | {fam[:3]} | {r['want_fanout']} | — | — | — | "
                    f"— | — | — | — | — | — | **{r['verdict']}** |"
                )
                continue
            bc = (
                f"{r.get('branches_completed','?')}/{r.get('branches_total','?')}"
                if "branches_total" in r
                else "—"
            )
            L.append(
                f"| {r['case']} | {fam[:3]} | {r['want_fanout']} | "
                f"{r.get('supervisor_decision') or '—'} | "
                f"{r.get('branch_count') if r.get('branch_count') is not None else '—'} | "
                f"{r.get('joins','—')} | "
                f"{r.get('join_chars','—')} | {bc} | {r.get('dom_chars','—')} | "
                f"{r.get('dom_cards','—')} | {r.get('is_fallback')} | "
                f"{r.get('shot','—')} | "
                f"**{r['verdict']}** |"
            )

    # roll-up
    ran = [r for r in records if r.get("ran")]
    verdicts: dict[str, int] = {}
    for r in records:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    L.append("\n## Roll-up\n")
    L.append(f"- cases total: **{len(records)}**, ran: **{len(ran)}**, "
             f"not-run: **{len(records) - len(ran)}**")
    for v, n in sorted(verdicts.items()):
        L.append(f"- `{v}`: **{n}**")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write the report file")
    args = ap.parse_args()
    records = build_records()
    md = render(records)
    print(md)
    if args.write:
        OUT.write_text(md)
        print(f"\n[written] {OUT}")


if __name__ == "__main__":
    main()
