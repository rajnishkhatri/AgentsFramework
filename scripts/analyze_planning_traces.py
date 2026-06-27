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
import ast
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
_CORPUS = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "planning_stress_corpus.json"


def _merge_corpus_expectations(rows: list[dict]) -> list[dict]:
    """Backfill the ``want_*`` expectations onto each runtime row from the corpus.

    The stress spec's JSONL writer emits a RUNTIME row (case / trace_id /
    outcome / latency …) and only some phases' ``want_*`` fields. Expectations
    are the CORPUS's property, not the trace's — so join by ``case`` and fill any
    missing ``want_*`` keys (notably ``want_fanout`` / ``want_survives_partial``,
    which the writer never emits). Runtime values already on the row win; this
    only fills gaps. A row whose case is absent from the corpus is left as-is.
    """
    try:
        corpus = json.loads(_CORPUS.read_text())
    except Exception:
        return rows  # no corpus → score with whatever the row carries
    by_case = {c.get("case"): c for c in corpus if isinstance(c, dict)}
    merged: list[dict] = []
    for row in rows:
        c = by_case.get(row.get("case"))
        if c:
            row = {
                **{k: v for k, v in c.items() if k.startswith("want")},
                **row,
            }
        merged.append(row)
    return merged


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
                delay = float(retry_after) if retry_after else (2.0**attempt)
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


def _as_list(v: object) -> list[str]:
    """Coerce a carrier list to list[str].

    The BlackBox→Langfuse relay (``black_box_publisher.redact_details``) keeps
    native types only for an allowlist of safe scalar keys; every other value —
    including the carrier-gate ``missing_pillars`` / ``missing_carriers`` lists —
    falls to ``redact_text(str(value))``, so a list arrives as its Python repr
    string (e.g. ``"['identity', 'reasoning']"``). Parse both the native-list
    shape (offline BlackBox source) and the stringified shape (Langfuse source);
    a scalar string becomes a single-element list; anything unparseable is empty.
    """
    if isinstance(v, list):
        return [str(item) for item in v]
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        try:
            parsed = ast.literal_eval(s)
        except (ValueError, SyntaxError):
            return [s]
        if isinstance(parsed, (list, tuple)):
            return [str(item) for item in parsed]
        return [str(parsed)]
    if v is None:
        return []
    return [str(v)]


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
        et = e.get("event_type") or ""
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


def _context_compacted_carriers(events: list[dict]) -> list[dict]:
    """Every CONTEXT_COMPACTED carrier on the trace (one per fold).

    The BlackBox event_type is ``context_compacted``; the Langfuse observation
    name is ``context.compacted`` (publisher mapping at
    ``black_box_publisher.py:118``). The trace-source loader normalizes dots to
    underscores (line 162-167), so both sources land here as
    ``event_type == "context_compacted"``.
    """
    out: list[dict] = []
    for e in events:
        if not (e.get("event_type") or "").endswith("context_compacted"):
            continue
        details = e.get("details")
        if isinstance(details, dict):
            out.append(details)
    return out


def _compaction_token_drop(carriers: list[dict]) -> tuple[int, int, float]:
    """Per-trace (tokens_before_first_fold, tokens_after_last_fold, drop_ratio).

    Drop ratio is ``1 - last_tokens_after / first_tokens_before`` over the
    folds emitted on the trace. Returns (0, 0, 0.0) when nothing folded — the
    caller partitions on this. Per c1_message_compaction.impl.md §11 the bar
    is a STRICT DROP (drop_ratio >= 0.20) on the FOLDED SUBSET; rows that
    didn't fold are not penalized.
    """
    if not carriers:
        return (0, 0, 0.0)
    before = _as_int(carriers[0].get("tokens_before"), 0)
    after = _as_int(carriers[-1].get("tokens_after"), 0)
    ratio = (1.0 - (after / before)) if before > 0 else 0.0
    return (before, after, round(ratio, 3))


def _compaction_unsafe_fold_count(carriers: list[dict]) -> int:
    """Per-trace count of folds the L1 gate declined.

    A CONTEXT_COMPACTED carrier with ``floor_exceeded=True`` is the §7-wire's
    way of surfacing an L1 decline (impl.md §10: L1 failure rolls into
    floor_exceeded). The inviolable §B2-R bar is ``unsafe_fold_count == 0``
    on every trace — any non-zero is a hard gate failure.
    """
    return sum(1 for c in carriers if _as_bool(c.get("floor_exceeded")))


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


# ── governance carrier-gate extraction + scoring (shadow validation) ───────────

# The phases the carrier gate is wired at (orchestration/react_loop.py). COMPLETION
# is deliberately unwired (its eval.goal_judge is in the eval-overlay sink, not the
# black box). TOOL_EXECUTION only fires when the run drove a tool — so its absence
# on a no-tool run is EXPECTED, not a gap.
_WIRED_CARRIER_PHASES = (
    "initialization",
    "routing",
    "model_invocation",
    "output_validation",
)
_TOOL_CARRIER_PHASE = "tool_execution"


def _carrier_gate_events(events: list[dict]) -> list[dict]:
    """The carrier-gate shadow carriers on a trace: guardrail_checked events whose
    details.source == 'carrier_gate'. Returns the list of detail dicts (one per
    checked phase boundary)."""
    out: list[dict] = []
    for e in events:
        if not (e.get("event_type") or "").endswith("guardrail_checked"):
            continue
        details = e.get("details")
        if isinstance(details, dict) and details.get("source") == "carrier_gate":
            out.append(details)
    return out


def _carrier_gate_enforce_events(events: list[dict]) -> list[dict]:
    """The Phase-2 ENFORCED carriers (source == 'carrier_gate_enforce'): the loud
    record that a gap was acted on (degrade/raise). Distinct from the shadow
    carrier so the report can tell 'gate observed' from 'gate enforced' — the live
    fault-injection run is where these are expected to appear."""
    out: list[dict] = []
    for e in events:
        if not (e.get("event_type") or "").endswith("guardrail_checked"):
            continue
        details = e.get("details")
        if (
            isinstance(details, dict)
            and details.get("source") == "carrier_gate_enforce"
        ):
            out.append(details)
    return out


def score_carrier_gate(rows: list[dict], events_by_row: dict[str, list[dict]]) -> dict:
    """Score the carrier-gate shadow signal across the batch.

    Per phase: emitted-on-N-of-M-runs (coverage) + #alert (gap) + the pillars seen
    missing. Run-level: the batch GAP RATE (fraction of emitted carriers with
    outcome=='alert') = the §5 Phase-2 go/no-go calibration input, and a verdict.
    No per-row want_* — on healthy traffic the expectation is "every wired phase
    that ran emitted a pass carrier"; gaps are the exception to triage.
    """
    # phase -> counters
    per_phase: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs_with_carrier": 0, "pass": 0, "alert": 0, "missing_pillars": []}
    )
    total_carriers = 0
    total_alerts = 0
    total_enforced = 0  # Phase-2 carrier_gate_enforce carriers (degrade/raise acted)
    enforced_detail: list[str] = []
    runs_scored = 0
    runs_missing_trace: list[str] = []
    no_carrier_runs: list[str] = []  # a run that emitted NO carrier-gate event at all

    for row in rows:
        case = row["case"]
        events = events_by_row.get(case, [])
        if not events:
            runs_missing_trace.append(case)
            continue
        runs_scored += 1
        gate = _carrier_gate_events(events)
        for ed in _carrier_gate_enforce_events(events):
            total_enforced += 1
            enforced_detail.append(
                f"{case}: {ed.get('phase')} → {ed.get('action')} "
                f"({_as_list(ed.get('missing_pillars'))})"
            )
        if not gate:
            no_carrier_runs.append(case)
            continue
        for d in gate:
            phase = d.get("phase") or "unknown"
            outcome = d.get("outcome") or "unknown"
            b = per_phase[phase]
            b["runs_with_carrier"] += 1
            total_carriers += 1
            if outcome == "alert":
                b["alert"] += 1
                total_alerts += 1
                pillars = _as_list(d.get("missing_pillars"))
                b["missing_pillars"].append(f"{case}: {pillars}")
            else:
                b["pass"] += 1

    # Coverage check: did each ALWAYS-wired phase emit on (nearly) every scored run?
    coverage_gaps: list[str] = []
    for phase in _WIRED_CARRIER_PHASES:
        seen = per_phase.get(phase, {}).get("runs_with_carrier", 0)
        if runs_scored and seen < runs_scored:
            coverage_gaps.append(f"{phase}: emitted on {seen}/{runs_scored} runs")
    # tool_execution is conditional — report coverage only over the tool rows.
    tool_rows = [r["case"] for r in rows if r.get("used_tool")]
    if tool_rows:
        tool_seen = per_phase.get(_TOOL_CARRIER_PHASE, {}).get("runs_with_carrier", 0)
        # (best-effort: a tool prompt may not actually drive a tool every run)
        per_phase[_TOOL_CARRIER_PHASE]["tool_rows"] = len(tool_rows)
        per_phase[_TOOL_CARRIER_PHASE]["tool_runs_seen"] = tool_seen

    gap_rate = round(total_alerts / total_carriers, 3) if total_carriers else 0.0

    # Verdict (§6): CLEAN = carriers landed at every wired phase, 0 alerts.
    # SIGNAL = alerts present (real seam defects OR false-positives to triage —
    # the human reads missing_pillars). FALSE-POSITIVE / DEFECT discrimination is a
    # triage step, not auto-decided. NO-EMISSION = the gate never fired (the wiring
    # or the relay is broken — the worst outcome, blocks Phase 2).
    if not total_carriers:
        verdict = "NO-EMISSION"
    elif coverage_gaps or no_carrier_runs:
        verdict = "PARTIAL-COVERAGE"
    elif total_alerts == 0:
        verdict = "CLEAN"
    else:
        verdict = "SIGNAL"

    return {
        "runs_scored": runs_scored,
        "runs_missing_trace": runs_missing_trace,
        "no_carrier_runs": no_carrier_runs,
        "total_carriers": total_carriers,
        "total_alerts": total_alerts,
        "total_enforced": total_enforced,
        "enforced_detail": enforced_detail,
        "gap_rate": gap_rate,
        "coverage_gaps": coverage_gaps,
        "per_phase": dict(per_phase),
        "verdict": verdict,
    }


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
    # C1 compaction (Phase 9) — partitioned over rows that ACTUALLY folded vs
    # didn't (want_compaction is a tendency, not a guarantee). Per
    # c1_message_compaction.impl.md §11:
    #   - bar (folded subset): mean drop_ratio >= 0.20 (sanity-floor, not a
    #     calibrated target; the first N real folded traces inform the gold-set
    #     later, design §8.5)
    #   - bar (every row): unsafe_fold_count == 0 (INVIOLABLE; §B2-R)
    # We DO NOT track prompt-cache hit-rate here — that signal is
    # provider-side (Anthropic prefix-cache metrics), pulled separately from the
    # Langfuse cost panel during the live run, not from the carrier wire.
    comp = {
        "folded": 0,
        "not_folded": 0,
        "fold_counts": [],
        "drop_ratios": [],  # only populated for folded traces
        "unsafe_folds_total": 0,
        "unsafe_fold_rows": [],
    }

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
                bucket["mismatches"].append(f"MISSED-ESCALATE :: {case} (got={got})")

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

        elif phase == "compaction":
            # Phase 9 — C1 message-history compaction.
            #
            # Hit = (folded ⇒ tokens dropped ≥20%) AND (always, unsafe_fold==0).
            # A row that didn't fold ISN'T penalized on the drop bar
            # (want_compaction is a tendency under model-window variance) but is
            # still subject to the unsafe-fold bar (trivially: 0 folds ⇒ 0 unsafe).
            carriers = _context_compacted_carriers(events)
            fold_n = len(carriers)
            unsafe = _compaction_unsafe_fold_count(carriers)
            tokens_before, tokens_after, drop_ratio = _compaction_token_drop(carriers)
            comp["fold_counts"].append(fold_n)
            comp["unsafe_folds_total"] += unsafe
            if unsafe > 0:
                comp["unsafe_fold_rows"].append(case)
                bucket["mismatches"].append(
                    f"UNSAFE-FOLD :: {case} ({unsafe} fold(s) with floor_exceeded=True)"
                )
                # An unsafe fold is a hard fail regardless of token drop.
                continue
            if fold_n >= 1:
                comp["folded"] += 1
                comp["drop_ratios"].append(drop_ratio)
                if drop_ratio >= 0.20:
                    bucket["hits"] += 1
                else:
                    bucket["mismatches"].append(
                        f"LOW-DROP :: {case} ratio={drop_ratio:.3f} "
                        f"(before={tokens_before} after={tokens_after} folds={fold_n})"
                    )
            else:
                # Did not fold — neither hit nor miss on the drop bar; record it.
                comp["not_folded"] += 1
                bucket["mismatches"].append(
                    f"NO-FOLD :: {case} (under trigger; not penalized)"
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
    # C1 compaction metrics (Phase 9). The folded subset is the scoring
    # denominator for the drop bar; unsafe_fold rate is over every row.
    mean_drop = (
        round(sum(comp["drop_ratios"]) / len(comp["drop_ratios"]), 3)
        if comp["drop_ratios"]
        else 0.0
    )
    summary["compaction"] = {
        "folded": comp["folded"],
        "not_folded": comp["not_folded"],
        "fold_counts": comp["fold_counts"],
        "drop_ratios": comp["drop_ratios"],
        "mean_drop_ratio": mean_drop,
        "unsafe_folds_total": comp["unsafe_folds_total"],
        "unsafe_fold_rows": comp["unsafe_fold_rows"],
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
        fails.append(
            f"escalation missed-escalations: {conf['fn']} (ships wrong answer)"
        )
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
    # C1 compaction (Phase 9): unsafe_fold_count is the INVIOLABLE bar.
    # Mean drop ratio ≥ 0.20 is the sanity-floor bar, only meaningful when
    # at least one row actually folded (otherwise the live run was below
    # the trigger threshold — a separate signal, not a gate failure).
    comp = summary.get("compaction") or {}
    if comp.get("unsafe_folds_total", 0) > 0:
        fails.append(
            f"compaction unsafe_folds_total={comp['unsafe_folds_total']} on "
            f"{len(comp.get('unsafe_fold_rows') or [])} row(s) "
            f"(any L1 floor_exceeded fold is a hard fail — §B2-R)"
        )
    if comp.get("folded", 0) >= 1 and comp.get("mean_drop_ratio", 0.0) < 0.20:
        fails.append(
            f"compaction mean_drop_ratio={comp['mean_drop_ratio']} < 0.20 "
            f"on {comp['folded']} folded row(s) (sanity-floor bar)"
        )
    return fails


# ── driver ─────────────────────────────────────────────────────────────────────


def _build_events_by_row(
    rows: list[dict], args: argparse.Namespace
) -> dict[str, list[dict]]:
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
    parser.add_argument(
        "--carrier-gate",
        action="store_true",
        help=(
            "score the governance carrier-gate shadow signal (per-phase coverage + "
            "batch gap-rate) instead of the planning phases"
        ),
    )
    args = parser.parse_args()

    if not args.jsonl.exists():
        print(f"no capture file at {args.jsonl} — run the stress spec first")
        return 2
    rows = [
        json.loads(line) for line in args.jsonl.read_text().strip().split("\n") if line
    ]
    if not rows:
        print(f"capture file {args.jsonl} is empty")
        return 2

    # Carrier-gate mode: distinct shape (per-phase coverage + gap-rate, no per-row
    # want_*). Score + print its own report, then return.
    if args.carrier_gate:
        events_by_row = _build_events_by_row(rows, args)
        cg = score_carrier_gate(rows, events_by_row)
        print(f"carrier-gate shadow validation :: source={args.source}")
        print(
            f"  rows={len(rows)} jsonl={args.jsonl.name} runs_scored={cg['runs_scored']}"
        )
        print()
        for phase in (*_WIRED_CARRIER_PHASES, _TOOL_CARRIER_PHASE):
            b = cg["per_phase"].get(phase)
            if not b:
                if phase in _WIRED_CARRIER_PHASES:
                    print(f"  {phase:18s} NO CARRIER (expected on every run)")
                continue
            print(
                f"  {phase:18s} emitted on {b['runs_with_carrier']} run(s)  "
                f"pass={b['pass']} alert={b['alert']}"
            )
            for mp in b["missing_pillars"]:
                print(f"      ALERT - {mp}")
        print()
        print(f"  total carriers   {cg['total_carriers']}")
        print(f"  total alerts     {cg['total_alerts']}")
        print(f"  GAP RATE         {cg['gap_rate']:.3f}")
        # Phase-2 enforcement (only non-zero when enforce mode is ON, e.g. the
        # fault-injection validation revision).
        if cg.get("total_enforced"):
            print(
                f"  ENFORCED         {cg['total_enforced']} (Phase-2 acted: degrade/raise)"
            )
            for ed in cg["enforced_detail"]:
                print(f"      * {ed}")
        if cg["coverage_gaps"]:
            print("  coverage gaps:")
            for g in cg["coverage_gaps"]:
                print(f"      - {g}")
        if cg["no_carrier_runs"]:
            print(f"  runs with NO carrier-gate event: {cg['no_carrier_runs']}")
        if cg["runs_missing_trace"]:
            print(f"  runs missing trace (Langfuse): {cg['runs_missing_trace']}")
        print()
        print(f"  VERDICT: {cg['verdict']}")
        # In --gate mode, only NO-EMISSION / PARTIAL-COVERAGE fail (a SIGNAL is a
        # human-triage signal, not an auto-fail — calibration, not enforcement).
        if args.gate and cg["verdict"] in ("NO-EMISSION", "PARTIAL-COVERAGE"):
            return 1
        return 0

    # Expectations live in the corpus, not the runtime trace — backfill them so
    # phases whose want_* the spec writer doesn't emit (e.g. fanout) score.
    rows = _merge_corpus_expectations(rows)

    events_by_row = _build_events_by_row(rows, args)
    summary = score_run(rows, events_by_row)

    mode = "GATE" if args.gate else "CALIBRATION"
    print(f"planning-stress analysis :: source={args.source} mode={mode}")
    print(f"  rows={len(rows)} jsonl={args.jsonl.name}")
    print()
    for phase in ("depth", "replan", "reflexion", "escalation", "fanout", "compaction"):
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
    fan = summary.get("fanout_confusion")
    if fan and (fan["tp"] + fan["fp"] + fan["tn"] + fan["fn"]):
        print(
            f"  fanout     precision {fan['precision']:.3f} (fp=GAIA-failure) "
            f"recall {fan['recall']:.3f} (missed=cheap, not gated) "
            f"tp={fan['tp']} fp={fan['fp']} tn={fan['tn']} fn={fan['fn']}"
        )
        ps = summary.get("partial_survival", {})
        if ps.get("eligible"):
            print(
                f"  fanout     partial-survival {summary['partial_survival_rate']:.3f} "
                f"({ps['survived']}/{ps['eligible']} fault rows survived)"
            )
    comp = summary.get("compaction") or {}
    if (
        comp.get("folded", 0)
        or comp.get("not_folded", 0)
        or comp.get("unsafe_folds_total", 0)
    ):
        print(
            f"  compaction folded {comp['folded']} of "
            f"{comp['folded'] + comp['not_folded']} rows  "
            f"mean drop {comp['mean_drop_ratio']:.3f} "
            f"(bar 0.200, INVIOLABLE unsafe_folds={comp['unsafe_folds_total']})"
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
