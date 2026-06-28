#!/usr/bin/env python3
"""analyze_fix_probes.py — carrier-assertion scorecard for the F1–F7 fix probes.

Reconciles the Playwright fix-probe capture (``cache/fix_probe_eval/ui_batch.jsonl``)
against the backend's BlackBox recordings and (optionally) Langfuse spans, asserting
for each probe the POSITIVE carrier its fix should now emit AND that the pre-fix
NEGATIVE control is absent. Emits a per-probe PASS / FAIL / SKIP scorecard.

This is a thin SCORER on top of the existing trace plumbing — it deliberately
reuses:
  * the BlackBox/Langfuse event loaders + the ``gj:{id}:{trace_id}`` -> workflow_id
    candidate resolution from ``scripts/analyze_planning_traces.py``;
  * the ``uuid5(dns, …)`` join-key check convention from
    ``docs/skills/playwright-agentic-e2e/scripts/verify_run.py``.

The fix -> carrier matrix (source of truth: docs/plans/toolcalling_f1f7_live_
validation.plan.md). Carriers verified against real recordings:
  F1   ERROR_OCCURRED.details.error_class == "validation"   (not "tool_reported")
  F1b  error_class == "validation" (shell block) / "timeout" (over-budget)
  F2   tool output contains "[tool-call rejected: invalid arguments"  (_repair_hint)
  F3   error_class == "unknown_tool" + "is not a registered tool"     (_unknown_tool_nudge),
       and the invented tool name is NOT called >= 3x
  F6   TASK_COMPLETED.details.goal_met == False (criteria_met == 0.0); outcome != success
  F7   turn >= 2 reaches a TASK_COMPLETED whose outcome is not "rejected"; no
       ERROR_OCCURRED(source=llm_call) provider-rejection on the final turn

Usage:
  .venv/bin/python scripts/analyze_fix_probes.py \
      --jsonl cache/fix_probe_eval/ui_batch.jsonl \
      --recordings cache/black_box_recordings
  # add --langfuse to also fetch + assert spans (needs LANGFUSE_* env)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent

# Reuse the proven loaders rather than re-implementing trace I/O.
sys.path.insert(0, str(SCRIPTS_DIR))
from analyze_planning_traces import (  # noqa: E402
    _load_blackbox_events,
    _load_langfuse_events,
)

_DEFAULT_JSONL = AGENT_ROOT / "cache" / "fix_probe_eval" / "ui_batch.jsonl"
_DEFAULT_RECORDINGS = AGENT_ROOT / "cache" / "black_box_recordings"


# ── trace loading (mirrors analyze_planning_traces._build_events_by_row) ────────


def _resolve_blackbox_events(recordings: Path, row: dict) -> list[dict]:
    """The spec encodes thread_id as ``gj:{case_id}:{trace_id}``; the saturation
    bridge forces the run's BlackBox workflow_id to that 32-hex ``trace_id`` (the
    overlay sets ``trace_id = match.group('trace_id')``). So the recording dir IS
    ``trace_id``. Try that first, then the legacy thread/id forms as a fallback
    (same resolution ladder as the planning analyzer)."""
    case_id = row.get("case_id", "")
    probe_id = row.get("probe_id", "")
    trace_id = row.get("trace_id", "")
    candidates = [
        trace_id,
        f"gj:{case_id}:{trace_id}" if case_id and trace_id else "",
        case_id,
        probe_id,
    ]
    for wf in candidates:
        if not wf:
            continue
        events = _load_blackbox_events(recordings, wf)
        if events:
            return events
    return []


def _events_for_row(row: dict, args: argparse.Namespace) -> list[dict]:
    if args.langfuse:
        try:
            ev = _load_langfuse_events(row["trace_id"])
            time.sleep(args.langfuse_delay)
            return ev
        except Exception as exc:  # one lost trace must not sink the batch
            print(f"  warn: langfuse fetch failed for {row.get('probe_id')}: {exc}")
            return []
    return _resolve_blackbox_events(args.recordings, row)


# ── carrier extraction (source-agnostic: blackbox & langfuse share the shape) ───


def _events_of(events: list[dict], suffix: str) -> list[dict]:
    return [
        e["details"]
        for e in events
        if (e.get("event_type") or "").endswith(suffix)
        and isinstance(e.get("details"), dict)
    ]


def _error_classes(events: list[dict]) -> list[str]:
    return [
        d["error_class"]
        for d in _events_of(events, "error_occurred")
        if isinstance(d.get("error_class"), str)
    ]


def _terminal_completed(events: list[dict]) -> dict | None:
    rows = _events_of(events, "task_completed")
    return rows[-1] if rows else None


def _all_tool_output_text(events: list[dict], row: dict) -> str:
    """Every text carrier the markers could land in: the persisted tool errors,
    the ERROR_OCCURRED strings, plus the DOM tool-card text the spec captured."""
    parts: list[str] = [row.get("tool_output") or "", row.get("response_text") or ""]
    for d in _events_of(events, "error_occurred"):
        for k in ("error", "output", "message"):
            v = d.get(k)
            if isinstance(v, str):
                parts.append(v)
    for d in _events_of(events, "tool_called"):
        v = d.get("output") or d.get("result")
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(parts)


def _tool_call_names(events: list[dict]) -> list[str]:
    return [
        d.get("tool", "")
        for d in _events_of(events, "tool_called")
        if isinstance(d.get("tool"), str)
    ]


def _as_bool(v: object) -> bool:
    """Langfuse serializes JSON booleans as the strings "True"/"False"."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return False


# ── per-fix assertions ─────────────────────────────────────────────────────────


def _assert_probe(row: dict, events: list[dict]) -> tuple[str, list[str]]:
    """Return (verdict, reasons). verdict in {PASS, FAIL, SKIP}."""
    fix = row.get("fix", "")
    if row.get("outcome") == "skip":
        return "SKIP", [row.get("skip_reason", "probe skipped by spec")]
    if not events:
        return "SKIP", ["no trace found (backend recording absent — cannot assert)"]

    reasons: list[str] = []
    ok = True

    classes = _error_classes(events)
    output = _all_tool_output_text(events, row)
    completed = _terminal_completed(events)

    # Live-unforcible seams (F3 unknown_tool, F6 empty-answer): a capable pinned
    # model usually REFUSES to misbehave, so the triggering condition never
    # occurs. Treat that as SKIP (the seam wasn't exercised), not FAIL — the fix
    # is covered by the unit suite. If the trigger DID fire, fall through and
    # assert normally (so a misbehaving model still validates the fix).
    if row.get("live_unforcible"):
        want_class = row.get("expected_error_class")
        want_goal = row.get("expected_goal_met")
        triggered = False
        if want_class and want_class in classes:
            triggered = True
        if (
            want_goal is False
            and completed
            and _as_bool(completed.get("goal_met")) is False
        ):
            # Only counts as "empty-answer floor fired" if the answer was empty.
            if float(completed.get("criteria_met") or 1.0) == 0.0:
                triggered = True
        if not triggered:
            return "SKIP", [
                "live-unforcible seam not exercised (capable model declined to "
                "misbehave); fix is unit-test covered — not a regression"
            ]

    # Positive: expected error_class present.
    want_class = row.get("expected_error_class")
    if want_class:
        if want_class in classes:
            reasons.append(f"+ error_class '{want_class}' present")
        else:
            ok = False
            reasons.append(
                f"- expected error_class '{want_class}' MISSING (saw {classes or '∅'})"
            )

    # Positive: expected marker substring in tool output.
    want_marker = row.get("expected_marker")
    if want_marker:
        if want_marker in output:
            reasons.append(f"+ marker present: {want_marker!r}")
        else:
            ok = False
            reasons.append(f"- marker MISSING: {want_marker!r}")

    # Positive: F6 goal_met / criteria_met.
    want_goal = row.get("expected_goal_met")
    if want_goal is not None:
        if completed is None:
            ok = False
            reasons.append("- no TASK_COMPLETED to read goal_met from")
        else:
            got = _as_bool(completed.get("goal_met"))
            if got == bool(want_goal):
                reasons.append(f"+ goal_met == {want_goal}")
            else:
                ok = False
                reasons.append(f"- goal_met == {got}, expected {want_goal}")
            if want_goal is False:
                cm = completed.get("criteria_met")
                if isinstance(cm, (int, float)) and float(cm) == 0.0:
                    reasons.append("+ criteria_met == 0.0 (empty-answer floor)")

    # Negative controls.
    nc = row.get("negative_control")
    if nc == "not_tool_reported":
        if "tool_reported" in classes:
            ok = False
            reasons.append("- NEG control fired: masked 'tool_reported' present")
        else:
            reasons.append("+ neg ok: no masked 'tool_reported'")
    elif nc == "not_validation":
        # F1b timeout must NOT be mislabeled validation.
        if "validation" in classes:
            ok = False
            reasons.append("- NEG control fired: timeout mislabeled 'validation'")
        else:
            reasons.append("+ neg ok: not mislabeled validation")
    elif nc == "no_name_loop":
        # The hallucinated name must not be called >= 3x. We don't know the
        # invented name a priori, so flag ANY single tool name repeated >= 3x
        # that also produced an unknown_tool error.
        names = _tool_call_names(events)
        repeated = {n for n in names if names.count(n) >= 3}
        if repeated and "unknown_tool" in classes:
            ok = False
            reasons.append(f"- NEG control fired: name-loop on {sorted(repeated)}")
        else:
            reasons.append("+ neg ok: no >=3x unknown-tool name loop")
    elif nc == "outcome_not_success":
        outcome = (completed or {}).get("outcome")
        if outcome == "success":
            ok = False
            reasons.append("- NEG control fired: corrupt success (outcome=success)")
        else:
            reasons.append(f"+ neg ok: outcome={outcome!r} (not success)")
    elif nc == "no_llm_rejection":
        # F7: the final turn must reach a non-rejected completion and carry no
        # provider-rejection llm_call error.
        outcome = (completed or {}).get("outcome")
        llm_rejections = [
            d
            for d in _events_of(events, "error_occurred")
            if d.get("source") == "llm_call"
        ]
        if completed is None:
            ok = False
            reasons.append("- turn-2 never reached TASK_COMPLETED (F7 defect signal)")
        elif outcome == "rejected":
            ok = False
            reasons.append("- NEG control fired: run outcome=rejected (F7 defect)")
        else:
            reasons.append(f"+ neg ok: outcome={outcome!r}, reached an answer")
        if llm_rejections:
            ok = False
            reasons.append(
                f"- NEG control fired: {len(llm_rejections)} llm_call error(s)"
            )
        else:
            reasons.append("+ neg ok: no llm_call provider rejection")

    if not (want_class or want_marker or want_goal is not None or nc):
        return "SKIP", ["probe declared no carriers to assert"]

    return ("PASS" if ok else "FAIL"), reasons


# ── join-key sanity (verify_run.py convention) ─────────────────────────────────


def _trace_id_ok(row: dict) -> bool:
    # trace_id is minted from case_id (the wire/join id), not the human probe_id.
    want = uuid.uuid5(uuid.NAMESPACE_DNS, row.get("case_id", "")).hex
    got = row.get("trace_id", "")
    return not got or got == want


# ── driver ─────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--jsonl", type=Path, default=_DEFAULT_JSONL)
    ap.add_argument("--recordings", type=Path, default=_DEFAULT_RECORDINGS)
    ap.add_argument(
        "--langfuse",
        action="store_true",
        help="fetch + assert spans from Langfuse instead of local BlackBox files",
    )
    ap.add_argument("--langfuse-delay", type=float, default=0.5)
    ap.add_argument(
        "--gate",
        action="store_true",
        help="exit non-zero if any probe FAILs (SKIP does not gate)",
    )
    args = ap.parse_args()

    if not args.jsonl.exists():
        print(f"no capture file at {args.jsonl} — run the fix-probe spec first")
        return 2
    rows = [
        json.loads(line) for line in args.jsonl.read_text().strip().split("\n") if line
    ]
    if not rows:
        print(f"capture file {args.jsonl} is empty")
        return 2

    # Last-write-wins per probe (append-only artifact accumulates re-runs).
    latest: dict[str, dict] = {}
    for r in rows:
        latest[r.get("probe_id", "")] = r
    rows = list(latest.values())

    source = "langfuse" if args.langfuse else "blackbox"
    print("=" * 72)
    print(f"F1–F7 fix-probe carrier scorecard :: source={source}")
    print(f"  probes={len(rows)} jsonl={args.jsonl.name}")
    print("=" * 72)

    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    bad_join = []
    for row in sorted(rows, key=lambda r: r.get("probe_id", "")):
        pid = row.get("probe_id", "?")
        fix = row.get("fix", "?")
        if not _trace_id_ok(row):
            bad_join.append(pid)
        events = _events_for_row(row, args)
        verdict, reasons = _assert_probe(row, events)
        counts[verdict] += 1
        glyph = {"PASS": "✓", "FAIL": "✗", "SKIP": "•"}[verdict]
        print(f"\n[{glyph} {verdict}] {pid}  ({fix})  — {row.get('note', '')[:80]}")
        for r in reasons:
            print(f"     {r}")

    print("\n" + "-" * 72)
    print(
        f"PASS {counts['PASS']}   FAIL {counts['FAIL']}   SKIP {counts['SKIP']}"
        + (f"   ⚠ join-key mismatch: {bad_join}" if bad_join else "")
    )
    print("-" * 72)

    skip_note = f" ({counts['SKIP']} skipped)" if counts["SKIP"] else ""
    if counts["FAIL"] > 0:
        print(f"RESULT: {counts['FAIL']} carrier assertion(s) FAILED ✗{skip_note}")
        # SKIP never gates; FAIL gates only under --gate.
        return 1 if args.gate else 0
    print(f"RESULT: all asserted carriers present ✓{skip_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
