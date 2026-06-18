"""Analyze the memory multi-session run: score cross-session recall + governance.

The other half of the memory-layer validation: the T3 spec
(`frontend/e2e/full-stack/memory-multisession.spec.ts`) drives each conversation
as N sessions for one persistent user and appends one PROBE row per probe turn
to `cache/memory_multisession/probe_batch.jsonl`. This script reads that JSONL,
pulls each probe trace, reads the memory carriers, and scores per ability:

  MEMORY_RECALLED details: {user_id, count, query_len, error_kind?}
  MEMORY_STORED   details: {user_id, key, error_kind?}

Per-ability RATE metrics (calibration) + THREE HARD-0 gates (always enforced):
  - cross_user_leaks   — a leak-control probe (user_B) recalled count>=1
  - stale_after_update — a knowledge-update probe answer still carries the OLD
                         value X instead of the corrected Y
  - fabricated_memories — an abstention probe recalled count>=1 OR claimed to
                         remember though nothing was ever seeded

The hard-0 gates can NEVER be calibrated away (a leak/fabrication is a privacy /
honesty defect, not a quality miss); they fail the gate regardless of mode.

Trace source (``--source``) + the Langfuse reader + the coercion helpers are
REUSED verbatim from ``scripts/analyze_planning_traces.py`` (no new API surface).

    python scripts/analyze_memory_traces.py --source blackbox \
        --jsonl cache/memory_multisession/probe_batch.jsonl \
        --recordings cache/black_box_recordings
    python scripts/analyze_memory_traces.py --source langfuse --gate
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent


def _load_env() -> None:
    """Populate LANGFUSE_* (and friends) from the repo-root ``.env`` if unset.

    The reused planning reader reads creds straight from ``os.environ`` but
    never loads ``.env`` — so a bare ``--source langfuse`` invocation silently
    fails every fetch with "keys required" and (because every row is then
    missing-trace) prints a FALSE "GATE PASSED". Mirror ``fetch_memory_trace``:
    load ``.env`` with ``setdefault`` (an already-exported var still wins).
    """
    env = AGENT_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_DEFAULT_JSONL = AGENT_ROOT / "cache" / "memory_multisession" / "probe_batch.jsonl"
_DEFAULT_RECORDINGS = AGENT_ROOT / "cache" / "black_box_recordings"
_CORPUS = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "memory_multisession_corpus.json"


def _planning_module():
    """Load the planning analyzer to REUSE its trace-source readers + coercers
    (single source of truth: the Langfuse fetch/backoff, blackbox reader, and
    _as_bool/_as_int never diverge between the two analyzers)."""
    path = SCRIPTS_DIR / "analyze_planning_traces.py"
    spec = importlib.util.spec_from_file_location("analyze_planning_traces", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_P = _planning_module()
_load_blackbox_events = _P._load_blackbox_events
_load_langfuse_events = _P._load_langfuse_events
_as_int = _P._as_int


# ── carrier extraction (source-agnostic) ──────────────────────────────────────


def _recall_carriers(events: list[dict]) -> list[dict]:
    return [
        e["details"]
        for e in events
        if (e.get("event_type") or "").endswith("memory_recalled")
        and isinstance(e.get("details"), dict)
    ]


def _store_carriers(events: list[dict]) -> list[dict]:
    return [
        e["details"]
        for e in events
        if (e.get("event_type") or "").endswith("memory_stored")
        and isinstance(e.get("details"), dict)
    ]


def _recall_count(events: list[dict]) -> int:
    """The recall hit count for the probe turn. Take the max across recall
    carriers (the probe lap is the one that queried; step-0 memoize records once)."""
    carriers = _recall_carriers(events)
    if not carriers:
        return 0
    return max(_as_int(c.get("count"), 0) for c in carriers)


def _recall_user_ids(events: list[dict]) -> set[str]:
    return {str(c.get("user_id")) for c in _recall_carriers(events) if c.get("user_id")}


def _answer_contains(response_text: str, needles: list[str]) -> bool:
    """Case-insensitive substring match (assert structure, not exact prose)."""
    hay = (response_text or "").lower()
    return all(n.lower() in hay for n in needles)


def _answer_contains_any(response_text: str, needles: list[str]) -> bool:
    hay = (response_text or "").lower()
    return any(n.lower() in hay for n in needles)


# Phrases that signal a fabricated "I remember…" on an abstention probe. The
# abstention answer should DISCLAIM memory ("I don't have / no record"); these
# are the affirmative-recall tells.
_FABRICATION_TELLS = (
    "i remember",
    "you told me",
    "you mentioned",
    "as you said",
    "your pet is",
    "you prefer",
    "you live in",
    "your birthday is",
)


def _claims_memory(response_text: str) -> bool:
    return _answer_contains_any(response_text, list(_FABRICATION_TELLS))


# ── scoring ────────────────────────────────────────────────────────────────────


def score_run(rows: list[dict], events_by_row: dict[str, list[dict]]) -> dict:
    """Score the whole probe batch per ability + the three hard-0 gates.

    ``rows`` are PROBE rows (one per probe turn). Each carries: case, ability,
    user_id, response_text, expect_substring?, stale_substring?,
    probe_recall_expected. ``events_by_row`` maps case -> the probe trace events.
    Returns a metrics dict (no side effects, deterministic)."""
    per_ability: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "hits": 0, "missing_trace": 0, "mismatches": []}
    )
    hard_zero = {
        "cross_user_leaks": 0,
        "stale_after_update": 0,
        "fabricated_memories": 0,
    }
    hard_zero_detail: list[str] = []

    for row in rows:
        ability = row["ability"]
        case = row["case"]
        events = events_by_row.get(case, [])
        bucket = per_ability[ability]
        bucket["n"] += 1

        if not events:
            bucket["missing_trace"] += 1
            bucket["mismatches"].append(f"MISSING-TRACE :: {case}")
            continue

        recall_count = _recall_count(events)
        recall_users = _recall_user_ids(events)
        response = row.get("response_text", "") or ""
        case_user = str(row.get("user_id", ""))

        if ability == "leak-control":
            # HARD-0: this user must recall NOTHING (the probed fact belongs to
            # another user). A recall carrier with count>=1, OR a recall carrier
            # naming a foreign user_id, is a cross-user leak.
            foreign = {u for u in recall_users if u and u != case_user}
            if recall_count >= 1 or foreign:
                hard_zero["cross_user_leaks"] += 1
                hard_zero_detail.append(
                    f"CROSS-USER-LEAK :: {case} (user={case_user} "
                    f"count={recall_count} foreign={sorted(foreign)})"
                )
                bucket["mismatches"].append(f"LEAK :: {case}")
            else:
                bucket["hits"] += 1

        elif ability == "abstention":
            # HARD-0: nothing was seeded -> recall count must be 0 AND the answer
            # must not claim a remembered fact.
            fabricated = recall_count >= 1 or _claims_memory(response)
            if fabricated:
                hard_zero["fabricated_memories"] += 1
                hard_zero_detail.append(
                    f"FABRICATED-MEMORY :: {case} (count={recall_count} "
                    f"claims={_claims_memory(response)})"
                )
                bucket["mismatches"].append(f"FABRICATED :: {case}")
            else:
                bucket["hits"] += 1

        elif ability == "knowledge-update":
            # Recall must return the CORRECTED value Y (expect_substring), not the
            # stale X (stale_substring). Carrying the stale value is HARD-0.
            expect = row.get("expect_substring", []) or []
            stale = row.get("stale_substring", []) or []
            has_corrected = _answer_contains(response, expect) if expect else True
            has_stale = _answer_contains_any(response, stale) if stale else False
            if has_stale and not has_corrected:
                hard_zero["stale_after_update"] += 1
                hard_zero_detail.append(
                    f"STALE-AFTER-UPDATE :: {case} (answer carries {stale}, "
                    f"not {expect})"
                )
                bucket["mismatches"].append(f"STALE :: {case}")
            elif has_corrected and recall_count >= 1:
                bucket["hits"] += 1
            else:
                bucket["mismatches"].append(
                    f"{case}: update miss (corrected={has_corrected} "
                    f"recall_count={recall_count})"
                )

        elif ability == "multi-session":
            # Both evidence facts must surface: recall count>=2 AND all expected
            # substrings present.
            expect = row.get("expect_substring", []) or []
            ok = recall_count >= 2 and (_answer_contains(response, expect) if expect else True)
            if ok:
                bucket["hits"] += 1
            else:
                bucket["mismatches"].append(
                    f"{case}: MISS (recall_count={recall_count} need>=2, "
                    f"substrings={_answer_contains(response, expect)})"
                )

        else:  # recall | temporal | persona-drift — single-fact recall + substring
            expect = row.get("expect_substring", []) or []
            recalled = recall_count >= 1
            has_fact = _answer_contains(response, expect) if expect else True
            if recalled and has_fact:
                bucket["hits"] += 1
            else:
                bucket["mismatches"].append(
                    f"{case}: MISS (recall_count={recall_count} "
                    f"has_fact={has_fact})"
                )

    # finalize per-ability rates
    abilities: dict[str, Any] = {}
    for ability, b in per_ability.items():
        scored = b["n"] - b["missing_trace"]
        rate = (b["hits"] / scored) if scored else 0.0
        abilities[ability] = {
            "n": b["n"],
            "scored": scored,
            "missing_trace": b["missing_trace"],
            "hits": b["hits"],
            "rate": round(rate, 3),
            "mismatches": b["mismatches"],
        }

    return {
        "abilities": abilities,
        "hard_zero": hard_zero,
        "hard_zero_detail": hard_zero_detail,
    }


def gate_failures(summary: dict) -> list[str]:
    """The three HARD-0 violations always fail the gate (privacy/honesty defects),
    regardless of calibration mode. Rate bars are calibration-only (recorded, not
    gated) until the first batch sets them — same discipline as the planning
    analyzer."""
    fails: list[str] = []
    hz = summary["hard_zero"]
    if hz["cross_user_leaks"]:
        fails.append(f"cross-user leaks: {hz['cross_user_leaks']} (PRIVACY — hard 0)")
    if hz["stale_after_update"]:
        fails.append(
            f"stale-after-update: {hz['stale_after_update']} (ADD-vs-UPDATE seam — hard 0)"
        )
    if hz["fabricated_memories"]:
        fails.append(
            f"fabricated memories: {hz['fabricated_memories']} (recall corrupt-success — hard 0)"
        )
    return fails


# ── driver ─────────────────────────────────────────────────────────────────────


def _merge_corpus_expectations(rows: list[dict]) -> list[dict]:
    """Backfill expect_substring / stale_substring onto each probe row from the
    corpus probe session. The spec writer echoes some, but the authoritative
    expectation is the corpus's. Join by case + (when present) probe session_idx.
    For knowledge-update, derive ``stale_substring`` from the FIRST seed session's
    distinguishing token vs the corrected value — but the corpus already encodes
    expect_substring as the corrected Y, so stale is read from the row if the spec
    emitted it; otherwise left absent (the analyzer treats absent stale as 'no
    stale check', so the operator can add it). Runtime values win."""
    try:
        corpus = json.loads(_CORPUS.read_text())
    except Exception:
        return rows
    by_case = {c.get("case"): c for c in corpus if isinstance(c, dict)}
    merged: list[dict] = []
    for row in rows:
        c = by_case.get(row.get("case"))
        if c:
            probe = None
            for s in c.get("sessions", []):
                if s.get("kind") == "probe":
                    probe = s  # last probe wins (matches the terminal probe)
            fill: dict[str, Any] = {"ability": c.get("ability"), "user_id": c.get("user_id")}
            if probe:
                if "expect_substring" in probe:
                    fill["expect_substring"] = probe["expect_substring"]
                if "probe_recall_expected" not in row and "want_recall" in probe:
                    fill["probe_recall_expected"] = probe["want_recall"]
            row = {**fill, **row}
        merged.append(row)
    return merged


def _mem_session_id(row: dict) -> str:
    """Reconstruct the ``mem:`` thread the spec installed as the Langfuse
    ``sessionId`` for this probe: ``mem:{mem_id}:s{idx}:{user_id}:{trace_id}``.

    This is the SAME string the blackbox branch uses as its workflow_id (the one
    source of truth for the probe→trace join) — see the spec's
    ``installMemThreadBridge``. Returns '' when any segment is missing."""
    mem_id = row.get("mem_id", "")
    sidx = row.get("session_idx")
    user_id = row.get("user_id", "")
    trace_id = row.get("probe_trace_id") or row.get("trace_id") or ""
    if not (mem_id and sidx is not None and user_id and trace_id):
        return ""
    return f"mem:{mem_id}:s{sidx}:{user_id}:{trace_id}"


def _resolve_langfuse_trace_id(session_id: str) -> str:
    """Map a probe's ``mem:`` sessionId to the backend-minted trace_id.

    The spec's ``probe_trace_id`` is a CLIENT-minted 32-hex; the backend never
    echoes it as a trace_id (FE-AP-7 forbids a client trace_id), so a direct
    ``/traces/{probe_trace_id}`` fetch 404s. The backend DOES set it as the
    trailing segment of the Langfuse ``sessionId`` — so query traces by
    sessionId and take the one carrying a memory.recalled observation (the probe
    lap). Returns '' when nothing resolves (caller records a missing-trace)."""
    if not session_id:
        return ""
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
    import urllib.error
    import urllib.parse
    import urllib.request

    url = f"{host}/api/public/traces?" + urllib.parse.urlencode(
        {"sessionId": session_id, "limit": 10}
    )
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    page = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                page = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 5:
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else (2.0 ** attempt)
                time.sleep(min(delay, 30.0))
                continue
            raise
    rows = (page or {}).get("data", []) if page else []
    if not rows:
        return ""
    # Prefer the trace that actually carries a memory.recalled carrier (the probe
    # lap). Fall back to the most recent trace in the session otherwise.
    for r in rows:
        events = _load_langfuse_events(r.get("id", ""))
        if _recall_carriers(events) or _store_carriers(events):
            return str(r.get("id", ""))
    return str(rows[0].get("id", ""))


def _build_events_by_row(rows: list[dict], args: argparse.Namespace) -> dict[str, list[dict]]:
    events_by_row: dict[str, list[dict]] = {}
    for row in rows:
        case = row["case"]
        # The probe trace_id is the join key (the spec writes probe_trace_id, and
        # the corpus pins a deterministic per-session trace_id as fallback).
        trace_id = row.get("probe_trace_id") or row.get("trace_id") or ""
        if args.source == "blackbox":
            wf_candidates = [
                _mem_session_id(row),
                trace_id,
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
                # The client-minted probe_trace_id is NOT a backend trace id;
                # resolve the real trace via the mem: sessionId join first, then
                # fall back to a direct fetch (e.g. a static corpus trace_id).
                session_id = _mem_session_id(row)
                resolved = _resolve_langfuse_trace_id(session_id) if session_id else ""
                events_by_row[case] = _load_langfuse_events(resolved or trace_id)
            except Exception as exc:
                print(f"  warn: langfuse fetch failed for {case}: {exc}")
                events_by_row[case] = []
            time.sleep(args.langfuse_delay)
    return events_by_row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, default=_DEFAULT_JSONL)
    parser.add_argument("--source", choices=["blackbox", "langfuse"], default="blackbox")
    parser.add_argument("--recordings", type=Path, default=_DEFAULT_RECORDINGS)
    parser.add_argument(
        "--gate",
        action="store_true",
        help="enforce bars (the 3 hard-0 gates ALWAYS enforce regardless of this flag)",
    )
    parser.add_argument("--langfuse-delay", type=float, default=0.5)
    args = parser.parse_args()

    if args.source == "langfuse":
        _load_env()

    if not args.jsonl.exists():
        print(f"no capture file at {args.jsonl} — run the memory stress spec first")
        return 2
    rows = [
        json.loads(line)
        for line in args.jsonl.read_text().strip().split("\n")
        if line
    ]
    if not rows:
        print(f"capture file {args.jsonl} is empty")
        return 2

    rows = _merge_corpus_expectations(rows)
    events_by_row = _build_events_by_row(rows, args)
    summary = score_run(rows, events_by_row)

    mode = "GATE" if args.gate else "CALIBRATION"
    print(f"memory multi-session analysis :: source={args.source} mode={mode}")
    print(f"  rows={len(rows)} jsonl={args.jsonl.name}")
    print()
    for ability in (
        "recall",
        "multi-session",
        "temporal",
        "knowledge-update",
        "abstention",
        "leak-control",
        "persona-drift",
    ):
        p = summary["abilities"].get(ability)
        if not p:
            continue
        print(
            f"  {ability:16s} hit-rate {p['rate']:.3f}  "
            f"({p['hits']}/{p['scored']} scored, {p['missing_trace']} missing-trace)"
        )
        for m in p["mismatches"]:
            print(f"      - {m}")
    print()
    hz = summary["hard_zero"]
    print("  HARD-0 gates (privacy / honesty — never calibrated away):")
    print(f"    cross-user leaks     {hz['cross_user_leaks']}")
    print(f"    stale-after-update   {hz['stale_after_update']}")
    print(f"    fabricated memories  {hz['fabricated_memories']}")
    for d in summary["hard_zero_detail"]:
        print(f"      ! {d}")
    print()
    print(
        "recall (misses-a-fact, cheap) and the hard-0 precision gates "
        "(leak/stale/fabrication) are reported separately — precision is the headline."
    )

    # A run where EVERY row failed to resolve a trace scored nothing — the
    # hard-0 gates are vacuously clean (no carrier was ever read). Treat that as
    # a broken run, not a pass: a silently-unjoined batch must never print
    # "GATE PASSED" (the false-pass that hid the probe_trace_id≠workflow_id gap).
    total = sum(p["n"] for p in summary["abilities"].values())
    scored = sum(p["scored"] for p in summary["abilities"].values())
    all_missing = total > 0 and scored == 0

    fails = gate_failures(summary)
    if fails:
        print("\nGATE FAILED (hard-0 violations always block):")
        for f in fails:
            print(f"  - {f}")
        return 1
    if all_missing:
        print(
            f"\nGATE INCONCLUSIVE: all {total} probe rows are missing-trace "
            "(no carrier scored). Check the probe→trace join / Langfuse creds; "
            "not treating a no-data run as a pass."
        )
        return 1
    if args.gate:
        print("\nGATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
