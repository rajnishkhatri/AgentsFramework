"""Analyze the planning-stress run: score each captured trace per phase.

The other half of the hybrid eval (tiered-loops build plan §8): entry-router
accuracy and escalation precision are measured SEPARATELY. This script reads the
``ui_batch.jsonl`` the T3 stress spec produced, pulls each captured trace, reads
the Step 0 carriers (``planning_depth`` / ``replanned`` on STEP_PLANNED;
``escalation_decision`` / ``escalation_reason`` / ``reflexion_attempt`` on
TASK_COMPLETED; the per-reentry ``reflexion_attempt`` STEP_PLANNED carriers), and
scores the four phases against the row's ``want_*`` expectations.

Trace source (``--source``):
  - ``blackbox`` (default): read the BlackBox ``trace.jsonl`` recordings under a
    local recordings dir — the canonical source the relay itself tails. Right for
    a LOCAL run (the topology-sim, or a local server). No network, no quota.
  - ``langfuse``: pull each trace from Langfuse over the public API using the
    ``LANGFUSE_*`` creds in the env. Right for a live Cloud Run run (the backend
    tmpfs recordings are ephemeral; Langfuse is the durable store). NOTE: the
    Langfuse monthly trace quota has been exhausted before (429s) — check headroom
    and run the one-case-per-phase smoke first.

Scoring mode:
  - ``--calibration`` (default): RECORD the per-phase rates without failing. The
    first non-deterministic T3 batch sets the bars; hard bars come later. Always
    exits 0 (so a calibration run never red-flags CI), but prints the rates and
    any mismatches for inspection.
  - ``--gate``: assert the plan §5.2 pass bars and exit non-zero on any phase
    below bar. Only meaningful once the bars are calibrated.

It mutates nothing — read-only over the captured traces.

    python scripts/analyze_planning_traces.py --source blackbox \
        --jsonl cache/planning_stress/ui_batch.jsonl \
        --recordings cache/black_box_recordings
    python scripts/analyze_planning_traces.py --source langfuse \
        --jsonl cache/planning_stress/ui_batch.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent

_DEFAULT_JSONL = AGENT_ROOT / "cache" / "planning_stress" / "ui_batch.jsonl"
_DEFAULT_RECORDINGS = AGENT_ROOT / "cache" / "black_box_recordings"


# ── trace sources ─────────────────────────────────────────────────────────────


def _load_blackbox_events(recordings_dir: Path, workflow_id: str) -> list[dict]:
    """Read one workflow's BlackBox trace.jsonl as a list of event dicts.

    Returns [] when the trace is absent (the analysis records it as a miss rather
    than crashing the whole batch on one lost trace).
    """
    trace_file = recordings_dir / workflow_id / "trace.jsonl"
    if not trace_file.exists():
        return []
    events: list[dict] = []
    for line in trace_file.read_text().strip().split("\n"):
        if line:
            events.append(json.loads(line))
    return events


def _load_langfuse_events(trace_id: str) -> list[dict]:
    """Pull one trace's observations from Langfuse, flattened to event dicts
    with a ``details`` key (so the scorer is source-agnostic).

    Uses the public API with the ``LANGFUSE_*`` env creds. Imported lazily so the
    blackbox path needs neither the creds nor the dependency.
    """
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = (
        os.environ.get("LANGFUSE_HOST")
        or os.environ.get("LANGFUSE_BASE_URL")
        or "https://cloud.langfuse.com"
    ).rstrip("/")
    if not public_key or not secret_key:
        raise RuntimeError(
            "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY required for --source langfuse"
        )

    import base64
    import urllib.request

    url = f"{host}/api/public/traces/{trace_id}"
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        trace = json.loads(resp.read().decode())

    # Langfuse observations carry the BlackBox details under metadata/input;
    # normalize each into {"event_type", "details"} so the scorer is uniform.
    events: list[dict] = []
    for obs in trace.get("observations", []) or []:
        details = obs.get("metadata") or obs.get("input") or {}
        if not isinstance(details, dict):
            continue
        events.append(
            {
                "event_type": obs.get("name", ""),
                "details": details,
            }
        )
    return events


# ── carrier extraction (source-agnostic) ──────────────────────────────────────


def _terminal_completed(events: list[dict]) -> dict | None:
    """The chronologically last TASK_COMPLETED details (carries the escalation
    carrier + the verdict). None when the trace never completed."""
    completed = [
        e["details"]
        for e in events
        if (e.get("event_type") or "").endswith("task_completed")
        and isinstance(e.get("details"), dict)
    ]
    return completed[-1] if completed else None


def _step_planned(events: list[dict]) -> list[dict]:
    return [
        e["details"]
        for e in events
        if (e.get("event_type") or "").endswith("step_planned")
        and isinstance(e.get("details"), dict)
    ]


def _fired_depth(events: list[dict]) -> str | None:
    steps = _step_planned(events)
    depths = [s["planning_depth"] for s in steps if "planning_depth" in s]
    # The FIRST plan's depth is the entry-router decision (later replans memoize).
    return depths[0] if depths else None


def _replan_count(events: list[dict]) -> int:
    return sum(1 for s in _step_planned(events) if s.get("replanned") is True)


def _reflexion_attempts(events: list[dict]) -> int:
    """Number of recorded reflexion re-entries (the per-reentry STEP_PLANNED
    carrier). Counts entries that carry the reflexion-step shape."""
    return sum(
        1
        for s in _step_planned(events)
        if "reflexion_attempt" in s and "reflexion_critique_chars" in s
    )


# ── per-phase scoring ──────────────────────────────────────────────────────────


def score_run(rows: list[dict], events_by_row: dict[str, list[dict]]) -> dict:
    """Score the whole batch per phase. Returns a metrics dict (no side effects)."""
    per_phase: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "hits": 0, "missing_trace": 0, "mismatches": []}
    )
    # Escalation is the only phase scored as precision/recall (confusion matrix).
    esc = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

    for row in rows:
        phase = row["phase"]
        case = row["case"]
        events = events_by_row.get(case, [])
        bucket = per_phase[phase]
        bucket["n"] += 1
        if not events:
            bucket["missing_trace"] += 1
            bucket["mismatches"].append(f"MISSING-TRACE :: {case}")
            continue

        if phase == "depth":
            want = row.get("want_depth")
            got = _fired_depth(events)
            if got == want:
                bucket["hits"] += 1
            else:
                bucket["mismatches"].append(f"{case}: want={want} got={got}")

        elif phase == "replan":
            want = bool(row.get("want_replan"))
            got = _replan_count(events) >= 1
            if got == want:
                bucket["hits"] += 1
            else:
                bucket["mismatches"].append(
                    f"{case}: want_replan={want} got_replan={got}"
                )

        elif phase == "reflexion":
            want = bool(row.get("want_reflexion"))
            attempts = _reflexion_attempts(events)
            reentered = attempts >= 1
            completed = _terminal_completed(events) or {}
            ceiling = completed.get("max_reflexion_attempts")
            bounded = ceiling is None or attempts <= int(ceiling)
            ok = (reentered == want) and bounded
            if ok:
                bucket["hits"] += 1
            else:
                bucket["mismatches"].append(
                    f"{case}: want_reflexion={want} reentered={reentered} "
                    f"attempts={attempts} bounded={bounded}"
                )

        elif phase == "escalation":
            want = row.get("want_escalation")  # "reflect" | "done"
            completed = _terminal_completed(events) or {}
            got = completed.get("escalation_decision")
            want_escalate = want == "reflect"
            got_escalate = got == "reflect"
            if got_escalate and want_escalate:
                esc["tp"] += 1
                bucket["hits"] += 1
            elif got_escalate and not want_escalate:
                esc["fp"] += 1
                bucket["mismatches"].append(f"FALSE-ESCALATE :: {case}")
            elif not got_escalate and not want_escalate:
                esc["tn"] += 1
                bucket["hits"] += 1
            else:  # missed escalate
                esc["fn"] += 1
                bucket["mismatches"].append(
                    f"MISSED-ESCALATE :: {case} (got={got})"
                )

    # finalize per-phase rates
    summary: dict[str, Any] = {"phases": {}}
    for phase, b in per_phase.items():
        scored = b["n"] - b["missing_trace"]
        rate = (b["hits"] / scored) if scored else 0.0
        summary["phases"][phase] = {
            "n": b["n"],
            "scored": scored,
            "missing_trace": b["missing_trace"],
            "hits": b["hits"],
            "rate": round(rate, 3),
            "mismatches": b["mismatches"],
        }

    tp, fp, fn = esc["tp"], esc["fp"], esc["fn"]
    summary["escalation_confusion"] = {
        **esc,
        "precision": round(tp / (tp + fp), 3) if (tp + fp) else 1.0,
        "recall": round(tp / (tp + fn), 3) if (tp + fn) else 1.0,
    }
    return summary


# ── plan §5.2 pass bars (only enforced in --gate mode) ─────────────────────────


def gate_failures(summary: dict) -> list[str]:
    """Return the list of plan §5.2 bar violations (empty == pass)."""
    fails: list[str] = []
    phases = summary["phases"]
    depth = phases.get("depth")
    if depth and depth["scored"]:
        # 0 L0-collapses on L1/L2-intended rows is the headline regression; here
        # the proxy is a perfect depth-hit rate (the offline oracle's floor).
        if depth["rate"] < 1.0:
            fails.append(f"depth rate {depth['rate']} < 1.0 (entry-router accuracy)")
    replan = phases.get("replan")
    if replan and replan["scored"] and replan["rate"] < 1.0:
        fails.append(f"replan rate {replan['rate']} < 1.0")
    reflexion = phases.get("reflexion")
    if reflexion and reflexion["scored"] and reflexion["rate"] < 1.0:
        fails.append(f"reflexion rate {reflexion['rate']} < 1.0")
    conf = summary["escalation_confusion"]
    if conf["fp"] > 0:
        fails.append(f"escalation false-positives: {conf['fp']} (thrash risk)")
    if conf["fn"] > 0:
        fails.append(f"escalation missed-escalations: {conf['fn']} (ships wrong answer)")
    return fails


# ── driver ─────────────────────────────────────────────────────────────────────


def _build_events_by_row(rows: list[dict], args: argparse.Namespace) -> dict[str, list[dict]]:
    events_by_row: dict[str, list[dict]] = {}
    for row in rows:
        case = row["case"]
        if args.source == "blackbox":
            # The stress spec encodes thread_id as gj:{case}:{trace_id}; the
            # backend uses the checkpoint thread_id as the workflow_id. Try the
            # full thread form first, then the bare trace_id, then the case.
            wf_candidates = [
                f"gj:{case}:{row['trace_id']}",
                row["trace_id"],
                case,
            ]
            events: list[dict] = []
            for wf in wf_candidates:
                events = _load_blackbox_events(args.recordings, wf)
                if events:
                    break
            events_by_row[case] = events
        else:
            try:
                events_by_row[case] = _load_langfuse_events(row["trace_id"])
            except Exception as exc:  # one lost trace must not sink the batch
                print(f"  warn: langfuse fetch failed for {case}: {exc}")
                events_by_row[case] = []
    return events_by_row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, default=_DEFAULT_JSONL)
    parser.add_argument(
        "--source", choices=["blackbox", "langfuse"], default="blackbox"
    )
    parser.add_argument("--recordings", type=Path, default=_DEFAULT_RECORDINGS)
    parser.add_argument(
        "--gate",
        action="store_true",
        help="enforce the plan §5.2 bars (exit non-zero on a violation)",
    )
    args = parser.parse_args()

    if not args.jsonl.exists():
        print(f"no capture file at {args.jsonl} — run the stress spec first")
        return 2
    rows = [
        json.loads(line)
        for line in args.jsonl.read_text().strip().split("\n")
        if line
    ]
    if not rows:
        print(f"capture file {args.jsonl} is empty")
        return 2

    events_by_row = _build_events_by_row(rows, args)
    summary = score_run(rows, events_by_row)

    mode = "GATE" if args.gate else "CALIBRATION"
    print(f"planning-stress analysis :: source={args.source} mode={mode}")
    print(f"  rows={len(rows)} jsonl={args.jsonl.name}")
    print()
    for phase in ("depth", "replan", "reflexion", "escalation"):
        p = summary["phases"].get(phase)
        if not p:
            continue
        print(
            f"  {phase:11s} hit-rate {p['rate']:.3f}  "
            f"({p['hits']}/{p['scored']} scored, {p['missing_trace']} missing-trace)"
        )
        for m in p["mismatches"]:
            print(f"      - {m}")
    conf = summary["escalation_confusion"]
    print()
    print(
        f"  escalation precision {conf['precision']:.3f} (thrash/false-escalate) "
        f"recall {conf['recall']:.3f} (ships-wrong-answer) "
        f"tp={conf['tp']} fp={conf['fp']} tn={conf['tn']} fn={conf['fn']}"
    )
    print()
    print(
        "entry-router accuracy (depth) and escalation precision are the two halves "
        "of the hybrid, reported separately (build plan §8)."
    )

    if args.gate:
        fails = gate_failures(summary)
        if fails:
            print("\nGATE FAILED:")
            for f in fails:
                print(f"  - {f}")
            return 1
        print("\nGATE PASSED")
        return 0
    # Calibration mode never fails the gate — it sets the bars.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
