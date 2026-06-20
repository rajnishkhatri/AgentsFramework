#!/usr/bin/env python3
"""Fetch the most recent MEMORY_ENABLED trace from Langfuse for the
governance-trace-audit.

Read-only. Strategy:
  1. Query the /api/public/observations endpoint by name (memory.recalled /
     memory.stored) — far cheaper than scanning every trace.
  2. Take the trace_id of the most recent memory carrier.
  3. Dump that trace's full observation array (the shape the
     governance-trace-audit skill consumes) to a file.

Falls back to scanning recent traces (with backoff) if the name query yields
nothing.

Env (from .env): LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST.

Usage:
    .venv/bin/python scripts/fetch_memory_trace.py [--limit 40] [--trace-id ID] [--since ISO] [--out PATH]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlencode


def _load_env() -> None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _auth_header() -> str:
    pk = os.environ["LANGFUSE_PUBLIC_KEY"]
    sk = os.environ["LANGFUSE_SECRET_KEY"]
    raw = f"{pk}:{sk}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _get(host: str, path: str, params: dict | None = None, *, retries: int = 5) -> dict:
    url = host.rstrip("/") + path
    if params:
        url += "?" + urlencode(params)
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"Authorization": _auth_header()})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = 2 ** attempt
                sys.stderr.write(f"  429 — backing off {wait}s\n")
                time.sleep(wait)
                continue
            sys.stderr.write(f"HTTP {e.code} on {path}: {e.read().decode()[:300]}\n")
            raise
    raise last_err  # type: ignore[misc]


_MEMORY_NAMES = (
    "memory.recalled",
    "memory.stored",
    "memory.suppressed",
    "MEMORY_RECALLED",
    "MEMORY_STORED",
    "MEMORY_SUPPRESSED",
)


def _has_memory_carrier(observations: list[dict]) -> bool:
    return any(
        any(m in (o.get("name") or "") for m in _MEMORY_NAMES) for o in observations
    )


def _find_by_name(host: str, since: str | None) -> str | None:
    """Query observations by each memory name; return most-recent trace_id."""
    best_ts = ""
    best_tid = None
    for name in ("memory.recalled", "memory.stored"):
        params: dict = {"name": name, "limit": 20}
        if since:
            params["fromStartTime"] = since
        try:
            page = _get(host, "/api/public/observations", params)
        except urllib.error.HTTPError:
            continue
        rows = page.get("data", [])
        sys.stderr.write(f"  observations name={name}: {len(rows)} found\n")
        for r in rows:
            ts = r.get("startTime") or r.get("timestamp") or ""
            if ts > best_ts and r.get("traceId"):
                best_ts = ts
                best_tid = r["traceId"]
    return best_tid


def main() -> int:
    _load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--trace-id", default=None)
    ap.add_argument("--since", default=None, help="ISO8601 fromStartTime filter")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    tid = args.trace_id
    if tid is None:
        sys.stderr.write("Querying observations by memory carrier name...\n")
        tid = _find_by_name(host, args.since)

    if tid is None:
        sys.stderr.write(
            "\nNo memory carrier found via name query. Falling back to "
            "scanning recent traces (slower, rate-limited)...\n"
        )
        page = _get(host, "/api/public/traces", {"limit": args.limit, "page": 1})
        rows = page.get("data", [])
        for r in rows:
            t = r["id"]
            try:
                full = _get(host, f"/api/public/traces/{t}")
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    sys.stderr.write(f"  429 on trace {t[:8]}… — skipping\n")
                    time.sleep(1.0)
                    continue
                raise
            obs = full.get("observations", [])
            if _has_memory_carrier(obs):
                tid = t
                break
            time.sleep(0.3)

    if tid is None:
        sys.stderr.write(
            "\nNo trace with a memory carrier found. Either no memory-ON run "
            "has emitted carriers yet, or the carrier name differs.\n"
        )
        return 2

    full = _get(host, f"/api/public/traces/{tid}")
    obs = full.get("observations", [])
    out_path = args.out or f"/tmp/memory_trace_{tid[:8]}.json"
    Path(out_path).write_text(json.dumps(obs, indent=2, default=str))
    mem_names = sorted(
        {o.get("name") for o in obs if any(m in (o.get("name") or "") for m in _MEMORY_NAMES)}
    )
    sys.stderr.write(
        f"\nCHOSEN trace {tid}\n  observations: {len(obs)}\n"
        f"  memory carriers: {mem_names}\n  written to: {out_path}\n"
    )
    print(json.dumps({"trace_id": tid, "out": out_path, "n_obs": len(obs),
                      "memory_carriers": mem_names}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
