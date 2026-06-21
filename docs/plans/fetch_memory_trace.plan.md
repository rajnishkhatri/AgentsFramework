---
type: plan
title: 'Fetch Memory Trace from Langfuse — plan'
description: 'Pull the most recent trace that emitted memory carriers (memory.recalled / memory.stored)'
tags: [plan]
---

# Fetch Memory Trace from Langfuse — plan

> **Status:** IMPLEMENTED 2026-06-18 — script at [`scripts/fetch_memory_trace.py`](../../scripts/fetch_memory_trace.py).
> Read-only helper for the governance-trace-audit workflow (memory layer verification step 4).

---

## Goal

Pull the most recent trace that emitted memory carriers (`memory.recalled` / `memory.stored`)
from Langfuse and dump its full observation array — the shape the
[`governance-trace-audit`](../../.claude/skills/governance-trace-audit/SKILL.md) skill consumes.

---

## Strategy (two tiers)

1. **Primary — query by observation name** (cheap, index-friendly)
   - Hit `GET /api/public/observations` with `name=memory.recalled` and `name=memory.stored`.
   - Optional `fromStartTime` filter via `--since`.
   - Pick the trace with the latest `startTime` / `timestamp` across both name queries.

2. **Fallback — scan recent traces** (slower, rate-limited)
   - If the name query returns nothing, list `GET /api/public/traces?limit=N&page=1`.
   - For each trace, fetch `GET /api/public/traces/{id}` and inspect observations.
   - Stop at the first trace where `_has_memory_carrier()` is true.
   - Sleep 0.3s between trace fetches; retry 429s with exponential backoff (2^attempt seconds).
   - If a trace fetch still returns 429 after retries, skip that trace and continue (do not abort the scan).

3. **Output**
   - Write the chosen trace's observation array to JSON (default `/tmp/memory_trace_{tid[:8]}.json`).
   - Print a one-line JSON summary to stdout: `{trace_id, out, n_obs, memory_carriers}`.

---

## Memory carrier names

Recognized in both dotted and legacy uppercase forms:

| Name | When emitted |
|---|---|
| `memory.recalled` | Step 0 recall seam (count + query_len, no content) |
| `memory.stored` | Run-end store seam (key + metadata, no content) |
| `MEMORY_RECALLED` | Legacy alias (substring match) |
| `MEMORY_STORED` | Legacy alias (substring match) |

Source of truth for dotted names: `services/governance/black_box_publisher.py`.

---

## Environment

Loaded from repo-root `.env` (no extra deps — stdlib only):

| Variable | Required | Default |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | yes | — |
| `LANGFUSE_SECRET_KEY` | yes | — |
| `LANGFUSE_HOST` | no | `https://cloud.langfuse.com` |

Auth: HTTP Basic (`public_key:secret_key` base64).

---

## CLI

```bash
.venv/bin/python scripts/fetch_memory_trace.py [--limit 40] [--trace-id ID] [--since ISO8601] [--out PATH]
```

| Flag | Purpose |
|---|---|
| `--trace-id` | Skip discovery; fetch this trace directly |
| `--since` | `fromStartTime` filter on the name query (e.g. `2026-06-18T09:55:00Z`) |
| `--limit` | Max traces to scan in fallback mode (default 40) |
| `--out` | Output path (default `/tmp/memory_trace_{first8}.json`) |

Exit codes: `0` success, `2` no memory carrier found.

---

## Workflow

```
Piece-C deploy (MEMORY_ENABLED=true, mem tag)
        │
        ▼
Authenticated run (remember + recall turns, same user_id)
        │
        ▼
scripts/fetch_memory_trace.py --since <deploy-time>
        │
        ▼
governance-trace-audit skill on observation JSON
        │
        ▼
Acceptance: memory.recalled (count, query_len) + memory.stored (key) present,
            content absent, four-pillar COMPLIANT, no carrier_gate memory alert
```

---

## Implementation

### HTTP helper with 429 backoff

```python
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
```

### Carrier detection

```python
_MEMORY_NAMES = ("memory.recalled", "memory.stored", "MEMORY_RECALLED", "MEMORY_STORED")


def _has_memory_carrier(observations: list[dict]) -> bool:
    return any(
        any(m in (o.get("name") or "") for m in _MEMORY_NAMES) for o in observations
    )
```

### Name-query discovery

```python
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
```

### Main orchestration

```python
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
            full = _get(host, f"/api/public/traces/{t}")
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
```

---

## Related docs

- Memory layer wiring plan — verification step 4: [`memory_layer_wiring.plan.md`](memory_layer_wiring.plan.md)
- Governance audit (first run, 0 carriers): [`docs/reviews/governance_audit_memory_on_2026-06-18.md`](../reviews/governance_audit_memory_on_2026-06-18.md)
- Calibration runbook (shadow trace export): [`docs/recipes/memory_extractor/04_calibration_runbook.md`](../recipes/memory_extractor/04_calibration_runbook.md)
