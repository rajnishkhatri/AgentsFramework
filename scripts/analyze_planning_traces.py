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
import time
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
    import time
    import urllib.error
    import urllib.request

    url = f"{host}/api/public/traces/{trace_id}"
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    # Langfuse rate-limits the read API; a tight 42-trace loop trips 429. Retry
    # with exponential backoff (honoring Retry-After when present) so a batch
    # run does not lose its tail to throttling.
    trace = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                trace = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 5:
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else (2.0 ** attempt)
                time.sleep(min(delay, 30.0))
                continue
            raise
    if trace is None:
        raise RuntimeError("langfuse fetch exhausted retries")

    # Langfuse observations carry the BlackBox event ``details`` in the
    # observation ``output`` (verified live 2026-06-15: escalation_*/reflexion_*
    # on task.completed.output; planning_depth/replanned/plan_source on
    # step.planned.output). Observation NAMES are dotted (``task.completed``);
    # normalize to the underscore form the scorer expects (BlackBox event_type)
    # so the scoring layer is source-agnostic. Merge output over metadata/input
    # in case some carriers land elsewhere.
    events: list[dict] = []
    for obs in trace.get("observations", []) or []:
        details: dict = {}
        for field in ("metadata", "input", "output"):
            v = obs.get(field)
            if isinstance(v, dict):
                details = {**details, **v}
        events.append(
            {
                "event_type": (obs.get("name", "") or "").replace(".", "_"),
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


def _as_bool(v: object) -> bool:
    """Coerce a carrier flag to bool. Langfuse serializes JSON booleans as the
    STRINGS "True"/"False" in the observation output, so a plain ``is True``
    silently reads every replan/flag as False — coerce both shapes."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


def _as_int(v: object, default: int = 0) -> int:
    """Coerce a carrier count to int (Langfuse serializes ints as strings too)."""
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _fired_depth(events: list[dict]) -> str | None:
    steps = _step_planned(events)
    depths = [s["planning_depth"] for s in steps if "planning_depth" in s]
    # The FIRST plan's depth is the entry-router decision (later replans memoize).
    return depths[0] if depths else None


def _replan_count(events: list[dict]) -> int:
    return sum(1 for s in _step_planned(events) if _as_bool(s.get("replanned")))


def _reflexion_attempts(events: list[dict]) -> int:
    """Number of recorded reflexion re-entries. The per-reentry STEP_PLANNED
    carrier has reflexion_critique_chars; but the AUTHORITATIVE count is the
    terminal task.completed.reflexion_attempt (the post-loop attempt index),
    which survives the relay even when the per-step carrier shape varies. Take
    the max of (terminal attempt, counted step carriers)."""
    step_carriers = sum(
        1
        for s in _step_planned(events)
        if "reflexion_attempt" in s and "reflexion_critique_chars" in s
    )
    terminal = _terminal_completed(events) or {}
    terminal_attempt = _as_int(terminal.get("reflexion_attempt"), 0)
    return max(step_carriers, terminal_attempt)


def _reflexion_within_budget(events: list[dict]) -> bool:
    """True if no single run cycle exceeded its reflexion ceiling.

    Checks each task.completed independently (a checkpoint thread can hold
    several cycles); a cycle is bounded when its reflexion_attempt does not
    exceed its own max_reflexion_attempts. Absent ceiling => treat as bounded.
    """
    completed = [
        e["details"]
        for e in events
        if (e.get("event_type") or "").endswith("task_completed")
        and isinstance(e.get("details"), dict)
    ]
    for c in completed:
        ceiling = c.get("max_reflexion_attempts")
        if ceiling is None:
            continue
        if _as_int(c.get("reflexion_attempt"), 0) > _as_int(ceiling, 0):
            return False
    return True


def _delegation_requested_count(events: list[dict]) -> int:
    """Number of per-branch delegation_requested carriers on the trace (T3).

    Tolerant of both export shapes: a trace_service event whose ``event_type``
    is ``delegation_requested``, and the BlackBox fallback whose
    ``details.delegation_event`` is ``delegation_requested`` (a TOOL_CALLED
    event). >= 2 of these == the supervisor issued >= 2 Sends == it fanned out.
    """
    n = 0
    for e in events:
        et = (e.get("event_type") or "")
        details = e.get("details") if isinstance(e.get("details"), dict) else {}
        if et.endswith("delegation_requested"):
            n += 1
        elif details.get("delegation_event") == "delegation_requested":
            n += 1
    return n


def _supervisor_decision(events: list[dict]) -> str | None:
    """The supervisor's fan_out|decline decision from its STEP_PLANNED carrier."""
    for s in _step_planned(events):
        if "supervisor_decision" in s:
            return str(s["supervisor_decision"])
    return None


def _fanout_join(events: list[dict]) -> dict | None:
    """The join carrier (STEP_PLANNED with fanout_join=True), or None."""
    for s in _step_planned(events):
        if _as_bool(s.get("fanout_join")):
            return s
    return None


def _fanout_partial_survived(events: list[dict]) -> bool:
    """A fault row survived partially iff the join produced a non-empty answer
    AND at least one branch failed (a sentinel was recorded) AND the run did not
    hang (the join carrier exists). This is the MAST-bounded survival signal."""
    join = _fanout_join(events)
    if not join:
        return False
    total = _as_int(join.get("branches_total"), 0)
    completed = _as_int(join.get("branches_completed"), 0)
    join_chars = _as_int(join.get("join_chars"), 0)
    had_failure = total > completed
    return join_chars > 0 and had_failure


# ── per-phase scoring ──────────────────────────────────────────────────────────


def score_run(rows: list[dict], events_by_row: dict[str, list[dict]]) -> dict:
    """Score the whole batch per phase. Returns a metrics dict (no side effects)."""
    per_phase: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "hits": 0, "missing_trace": 0, "mismatches": []}
    )
    # Escalation is the only phase scored as precision/recall (confusion matrix).
    esc = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    # Fan-out (T3) is also scored as a confusion matrix — the fp cell is the
    # GAIA-failure detector (a near-miss ⚠ decline row that got fanned out
    # anyway). Plus partial-survival over the fault rows.
    fan = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    fan_survival = {"eligible": 0, "survived": 0}

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
            # Budget bound is PER CYCLE, not per trace: a checkpoint thread can
            # accumulate several independent run cycles (each respecting the
            # ceiling), so summing carriers across cycles would falsely report
            # "unbounded". Bound = no single task.completed.reflexion_attempt
            # exceeded its own max_reflexion_attempts (verified live 2026-06-15:
            # the loop hit reflexion_attempt=2/max=2 -> escalation_reason=
            # budget_exhausted -> stopped, correctly, every cycle).
            bounded = _reflexion_within_budget(events)
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
            want_escalate = want == "reflect"
            # Escalation fired if ANY task.completed in the trace decided
            # "reflect" — a loop can escalate on a failed verdict and then
            # RECOVER (terminal decision "done"). Scoring only the terminal
            # event mislabels a successful recovery as a missed escalation
            # (verified live 2026-06-15: STRESS-ESCALATION-wrong-prone-01
            # escalated on verdict at attempt 0, fixed it, ended "done").
            all_completed = [
                e["details"]
                for e in events
                if (e.get("event_type") or "").endswith("task_completed")
                and isinstance(e.get("details"), dict)
            ]
            got_escalate = any(
                c.get("escalation_decision") == "reflect" for c in all_completed
            )
            got = "reflect" if got_escalate else "done"
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

        elif phase == "fanout":
            want_fanout = _as_bool(row.get("want_fanout"))
            # Got fan-out iff the supervisor issued >= 2 Sends (>= 2
            # delegation_requested carriers). Fall back to the decision carrier.
            got_fanout = _delegation_requested_count(events) >= 2
            if not got_fanout and _supervisor_decision(events) == "fan_out":
                got_fanout = True

            if got_fanout and want_fanout:
                fan["tp"] += 1
                bucket["hits"] += 1
            elif got_fanout and not want_fanout:
                # THE GAIA-FAILURE CELL: a near-miss decline row fanned out anyway.
                fan["fp"] += 1
                bucket["mismatches"].append(f"FALSE-FANOUT (GAIA) :: {case}")
            elif not got_fanout and not want_fanout:
                fan["tn"] += 1
                bucket["hits"] += 1
            else:  # missed fan-out (the CHEAP error — runs sequentially)
                fan["fn"] += 1
                bucket["mismatches"].append(f"MISSED-FANOUT :: {case}")

            # Partial-survival, scored only over the fault rows.
            if _as_bool(row.get("want_survives_partial")):
                fan_survival["eligible"] += 1
                if _fanout_partial_survived(events):
                    fan_survival["survived"] += 1
                else:
                    bucket["mismatches"].append(f"NO-PARTIAL-SURVIVAL :: {case}")

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
    # Fan-out (T3): precision is the headline (the fp cell = GAIA-failure
    # detector). Recall is reported but NOT gated — a missed fan-out is the cheap
    # error (it just runs sequentially). partial_survival is gated toward 1.0.
    ftp, ffp, ffn = fan["tp"], fan["fp"], fan["fn"]
    summary["fanout_confusion"] = {
        **fan,
        "precision": round(ftp / (ftp + ffp), 3) if (ftp + ffp) else 1.0,
        "recall": round(ftp / (ftp + ffn), 3) if (ftp + ffn) else 1.0,
    }
    summary["partial_survival_rate"] = (
        round(fan_survival["survived"] / fan_survival["eligible"], 3)
        if fan_survival["eligible"]
        else 1.0
    )
    summary["partial_survival"] = fan_survival
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
    # Fan-out (T3): precision >= 0.9 (the fp cell is the GAIA-failure headline);
    # partial-survival == 1.0. Recall is reported but NOT gated — a missed
    # fan-out is the cheap error (plan §3.5a / Stage B5).
    fan = summary.get("fanout_confusion")
    if fan and (fan["tp"] + fan["fp"]) and fan["precision"] < 0.9:
        fails.append(
            f"fanout precision {fan['precision']} < 0.9 "
            f"({fan['fp']} false-fan-out / GAIA failures)"
        )
    if summary.get("partial_survival", {}).get("eligible"):
        rate = summary.get("partial_survival_rate", 1.0)
        if rate < 1.0:
            fails.append(f"fanout partial-survival rate {rate} < 1.0")
    return fails


# ── driver ─────────────────────────────────────────────────────────────────────


def _build_events_by_row(rows: list[dict], args: argparse.Namespace) -> dict[str, list[dict]]:
    events_by_row: dict[str, list[dict]] = {}
    for row in rows:
        case = row["case"]
        if args.source == "blackbox":
            # The stress spec encodes thread_id as gj:{gj_id}:{trace_id}; the
            # backend uses the checkpoint thread_id as the workflow_id. Try the
            # full thread forms first, then the bare trace_id, then the ids.
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
            # Space requests so a 42-trace batch does not hammer the read API
            # into a 429 (the per-call retry/backoff handles transient spikes).
            time.sleep(args.langfuse_delay)
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
    parser.add_argument(
        "--langfuse-delay",
        type=float,
        default=0.5,
        help="seconds between Langfuse fetches (avoid 429 on large batches)",
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
