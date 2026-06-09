#!/usr/bin/env python3
"""
verify_run.py — reconcile a Playwright full-stack capture artifact with the
backend's view of the run.

A green DOM assertion only proves the frontend rendered something. For an agentic
system you also want to know: did the harness drive N cases, did the backend
actually run them (logs/traces), and how many runs surfaced a *real* answer in the
DOM vs. only a status feed.

This is intentionally dependency-light (stdlib only) so it runs anywhere. It does
NOT hit your cloud provider; it prints the query for you to run and counts what
you pass back in.

Capture artifact = JSONL, one row per case. Expected-ish fields (override names
via flags if yours differ):
    case_id, trace_id, response_text, base_url

Usage:
    python verify_run.py --jsonl cache/eval/ui_batch.jsonl
    python verify_run.py --jsonl ui_batch.jsonl --status-prefix "Using tools:" \
        --expect-cases 22 --id-namespace dns --log-marker-count 22
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections import Counter


def load_rows(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def strip_status_prefix(text: str, prefix: str) -> str:
    """Remove leading status-feed segments so a fully-answered run isn't miscounted.

    A streamed answer's captured text often begins with a progressively-replaced
    status feed, e.g. 'Using tools: file_io, web_search…'. Fully-answered runs
    ALSO start with that prefix, so a naive `startswith(prefix)` or `len>0` check
    flips the headline number. We strip one-or-more leading
    '<prefix> ... <ellipsis>' segments, then measure what remains.
    """
    if not text:
        return ""
    esc = re.escape(prefix)
    # Match repeated "<prefix> <stuff up to an ellipsis>" runs at the start.
    pattern = re.compile(rf"^(?:\s*{esc}[^…]*…)+", re.IGNORECASE)
    return pattern.sub("", text).strip()


def derive_id(case_id: str, namespace: str) -> str:
    ns = {
        "dns": uuid.NAMESPACE_DNS,
        "url": uuid.NAMESPACE_URL,
        "oid": uuid.NAMESPACE_OID,
        "x500": uuid.NAMESPACE_X500,
    }.get(namespace.lower(), uuid.NAMESPACE_DNS)
    return uuid.uuid5(ns, case_id).hex


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jsonl", required=True, help="path to the capture JSONL")
    ap.add_argument("--id-field", default="case_id")
    ap.add_argument("--trace-field", default="trace_id")
    ap.add_argument("--text-field", default="response_text")
    ap.add_argument("--status-prefix", default="Using tools:",
                    help="leading status-feed prefix to strip before measuring a 'real' answer")
    ap.add_argument("--dedupe", action="store_true",
                    help="last-write-wins per case id before computing the split "
                         "(an append-only artifact accumulates re-runs; raw rows then mislead)")
    ap.add_argument("--expect-cases", type=int, default=None,
                    help="assert exactly this many rows (e.g. your registry subset size)")
    ap.add_argument("--id-namespace", default=None,
                    help="if set (dns|url|oid|x500), check trace_id == uuid5(ns, case_id)")
    ap.add_argument("--log-marker-count", type=int, default=None,
                    help="deduped backend marker-line count you observed (logs); compared to row count")
    ap.add_argument("--trace-count", type=int, default=None,
                    help="trace count you observed in the tracing backend; compared to row count")
    args = ap.parse_args()

    try:
        rows = load_rows(args.jsonl)
    except FileNotFoundError:
        print(f"ERROR: no such file: {args.jsonl}", file=sys.stderr)
        return 2

    raw_n = len(rows)
    raw_ids = [r.get(args.id_field, "") for r in rows]
    dup_ids = [cid for cid, c in Counter(raw_ids).items() if c > 1 and cid]

    if args.dedupe:
        latest: dict[str, dict] = {}
        for r in rows:
            latest[r.get(args.id_field, "")] = r  # last occurrence wins
        rows = list(latest.values())

    n = len(rows)
    ids = [r.get(args.id_field, "") for r in rows]

    rendered, status_only = [], []
    for r in rows:
        cid = r.get(args.id_field, "?")
        text = r.get(args.text_field, "") or ""
        if strip_status_prefix(text, args.status_prefix):
            rendered.append(cid)
        else:
            status_only.append(cid)

    print("=" * 64)
    print(f"capture: {args.jsonl}")
    print(f"rows in file:                  {raw_n}"
          + (f"   ⚠ duplicate ids: {sorted(dup_ids)}" if dup_ids else ""))
    if args.dedupe and dup_ids:
        print(f"after last-write dedupe:       {n} distinct cases")
    elif dup_ids:
        print("  (re-runs present — pass --dedupe so the split reflects distinct cases)")
    print(f"distinct case ids:             {len(set(ids))}")
    print("-" * 64)
    print(f"rendered a real answer:        {len(rendered)}/{n}")
    print(f"status-feed only (UI gap):     {len(status_only)}/{n}")
    if status_only:
        print(f"  status-only ids: {sorted(status_only)}")
    print("-" * 64)

    ok = True

    if args.expect_cases is not None:
        good = n == args.expect_cases
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] expected {args.expect_cases} cases, got {n}")

    if args.id_namespace:
        mismatches = []
        for r in rows:
            cid = r.get(args.id_field, "")
            want = derive_id(cid, args.id_namespace)
            got = r.get(args.trace_field, "")
            if got and got != want:
                mismatches.append((cid, got, want))
        good = not mismatches
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] trace_id == uuid5({args.id_namespace}, case_id)"
              + (f"  ⚠ {len(mismatches)} mismatch(es)" if mismatches else ""))
        for cid, got, want in mismatches[:5]:
            print(f"     {cid}: got {got[:12]}… want {want[:12]}…")

    if args.log_marker_count is not None:
        good = args.log_marker_count == n
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] backend marker lines {args.log_marker_count} == rows {n}"
              + ("" if good else "  ⚠ backend ran a different count than the harness drove"))

    if args.trace_count is not None:
        good = args.trace_count == n
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] traces {args.trace_count} == rows {n}")

    print("-" * 64)
    print("Reminder — query the logs yourself (creds not assumed). Example (GCP):")
    print("  gcloud logging read \\")
    print("    'resource.type=\"cloud_run_revision\"")
    print("     AND resource.labels.service_name=\"<service>\"")
    print("     AND jsonPayload.message=~\"<marker>\"' \\")
    print("    --project=<project> --freshness=1h \\")
    print("    --format='value(timestamp, jsonPayload.message)' --limit=200")
    print("  # NOTE: structured logs land in jsonPayload.message, NOT textPayload.")
    print("  # Dedupe by a per-run id before counting (retries/replicas duplicate lines).")
    print("=" * 64)

    if not ok:
        print("RESULT: discrepancies found ✗")
        return 1
    print("RESULT: all requested checks passed ✓"
          + (f" — but {len(status_only)} run(s) showed a UI render gap" if status_only else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
