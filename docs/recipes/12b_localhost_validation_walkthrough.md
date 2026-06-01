# Recipe 12b — Localhost Validation Walkthrough (I2 / I6 / I8)

**Goal:** Manually validate the three fixes from
[Recipe 12](12_eval_judge_span_order_and_dedup.md) against the **local dev
middleware** (`python -m middleware`) using a real SearXNG backend and the
weather S2 task. Each step lists the exact command to run and the exact log /
artifact to capture and share.

- **I2** — `task.completed` reports a *meaningful* `goal_met` / `criteria_met`
  (task-adaptive LLM-as-judge), not the keyword-overlap constant `0.0`.
- **I6** — the Langfuse span tree shape is **stable across runs** (drain → close
  → flush teardown order).
- **I8** — **exactly one** `task.completed` / `step.executed` per `event_id`
  (per-trace exporter dedup + single-writer relay).

> **What "share the logs" means here:** after each run, paste back (a) the dev
> server terminal output, (b) the captured files this doc names, and (c) the
> `trace_id` printed by the send script. Those three are enough to judge
> pass/fail for all three defects.

---

## Step 0 — Dev-parity note (already applied)

The I6 teardown reorder and the I2 judge toggle originally shipped **only** in
`middleware/app_prod.py` (the Cloud Run entrypoint, which needs GCS + Postgres +
WorkOS). To make them reachable from the laptop server, three parity edits were
applied to `middleware/__main__.py`:

1. `emit_domain_event(..., release_on_finish=False)` on the stream — defer the
   eager `release_trace` (I6).
2. SSE `finally` reordered to **drain → `emit_run_finished(release=False)` →
   `release_trace` → `flush`** (I6).
3. `AgentConfig(..., goal_judge_enabled=<env GOAL_JUDGE_ENABLED>)` — an env
   toggle so the judge can be turned on locally (I2).

The I8 fixes (exporter `event_id` dedup, single-writer relay lock, atomic
offset) live in shared modules and need no entrypoint change.

Confirm the edits are present:

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
grep -n "release_on_finish=False" middleware/__main__.py
grep -n "release=False" middleware/__main__.py
grep -n "exporter.release_trace(trace_id_seen)" middleware/__main__.py
grep -n "goal_judge_enabled=os.environ" middleware/__main__.py
```

> **Capture:** the four grep lines (proves the dev server exercises the fixes).

---

## Step 1 — Baseline tests (offline, no server)

```bash
python -m pytest -p no:logfire \
  tests/components/test_goal_judge.py \
  tests/components/test_evaluator.py \
  tests/middleware/test_telemetry_bridge.py \
  tests/middleware/adapters/observability/test_langfuse_cloud_exporter.py \
  tests/middleware/sidecars/test_black_box_to_telemetry.py \
  tests/orchestration/test_no_progress.py \
  tests/architecture/ -q
```

> **Capture:** the final pytest summary line (e.g. `N passed`). Must be green
> before the live run is meaningful.

---

## Step 2 — Environment

Set the keys/flags for the run. SearXNG (real search) and the judge both need to
be on; Langfuse keys turn the relay from a no-op into a real exporter (required
to *see* I6/I8 in the UI).

```bash
export OPENAI_API_KEY=sk-...                      # live LLM (judge + agent)
export WEB_SEARCH_PROVIDER=searxng                # real web search (I2 evidence)
export SEARXNG_URL=http://localhost:8888
export GOAL_JUDGE_ENABLED=true                    # turn on the I2 judge
export BLACKBOX_RELAY_MODE=in_process             # in-process relay (default)
export LANGFUSE_ENABLED=true
export LANGFUSE_PUBLIC_KEY=pk-lf-...              # required for I6/I8 in the UI
export LANGFUSE_SECRET_KEY=sk-lf-...
export LANGFUSE_HOST=https://cloud.langfuse.com
```

> **No Langfuse keys?** You can still validate **I2** fully (local
> `trace.jsonl`) and the relay single-writer behavior for **I8**, but the
> exporter falls back to a no-op so the **span tree (I6)** and the Langfuse-side
> dedup (I8) cannot be seen in the UI. Note this in your results if so.

> **Capture:** `env | grep -E 'WEB_SEARCH|GOAL_JUDGE|BLACKBOX_RELAY|LANGFUSE_ENABLED'`
> (redact the key values).

---

## Step 3 — Start SearXNG

```bash
docker compose -f docker-compose.searxng.yml up -d
sleep 3
curl -s "http://localhost:8888/search?q=austin+weather&format=json" | head -c 300; echo
```

> **Capture:** the first ~300 chars of JSON (proves real results, not the stub).

---

## Step 4 — Start the dev middleware (pinned to port 8001)

The send script defaults to port **8001**; pin the server there so they match.
Run in its own terminal and **keep it visible** — its stderr is the primary I6/I8
evidence.

```bash
# fresh logs for this run
mkdir -p logs && : > logs/black_box.log; : > logs/evals.log; : > logs/tools.log

PORT=8001 PORT_STRICT=1 python -m middleware 2>&1 | tee logs/dev_server.log
```

Wait for `Application startup complete` and
`BlackBox→Langfuse relay started (in-process)`.

> **Capture:** the startup lines, including the relay-started line and whether it
> says `Langfuse telemetry enabled for dev` (real exporter) vs
> `dev telemetry disabled` (no-op).

---

## Step 5 — Send the S2 weather task

In a second terminal (same env not required — the script just POSTs):

```bash
python scripts/_dbg_d9c823_send.py            # defaults to --port 8001
```

> **Capture:** the full script output, especially the `trace_id:` line at the
> bottom. Set `export TRACE=<that-trace-id>` for the steps below.

---

## Step 6 — I2: meaningful goal verdict

The local BlackBox recording is the source of truth (independent of Langfuse).

```bash
# The TASK_COMPLETED event with the overlaid judge verdict
python - "$TRACE" <<'PY'
import json, sys
trace = sys.argv[1]
path = f"cache/black_box_recordings/{trace}/trace.jsonl"
for line in open(path):
    evt = json.loads(line)
    if evt.get("event_type") == "task_completed":
        d = evt.get("details", {})
        print(json.dumps({
            "outcome": d.get("outcome"),
            "goal_met": d.get("goal_met"),
            "criteria_met": d.get("criteria_met"),
            "unmet_conditions": d.get("unmet_conditions"),
            "termination_reason": d.get("termination_reason"),
        }, indent=2))
PY

# Confirm the judge ran (and did NOT silently fall back to the heuristic).
# eval_capture logs a bare "AI Response" line (the formatter drops the target
# field), so the reliable signals are the verdict values above + the ABSENCE of
# this fallback warning in the server log:
grep -n "goal_judge failed; falling back to heuristic" logs/dev_server.log || echo "no judge fallback (good)"
# Sanity: at least one eval_capture record was written this run.
grep -c "AI Response" logs/evals.log
```

**PASS criteria (I2):**
- `outcome` = `"success"` (deterministic floor — judge never changes this).
- `goal_met` = `true` on this genuinely-good run (was `false` before the fix).
- `criteria_met` > `0.0` (was always `0.0` before).
- `unmet_conditions` is **not** the two fixed generic strings
  ("All planned branches…", "Final answer is concise…") — it is empty or a
  task-specific phrase. *(These two together prove the judge ran, not the
  keyword heuristic — the heuristic always returns `criteria_met=0.0` and those
  two exact strings.)*
- **No** `goal_judge failed; falling back to heuristic` line in the server log.

> **Capture:** the printed JSON, the fallback-grep result, and the
> `AI Response` count.

---

## Step 7 — I6: stable span tree across runs

Send the **same** task a second time, then compare the two trees in Langfuse.

```bash
python scripts/_dbg_d9c823_send.py            # second run -> note TRACE2
```

In the Langfuse UI (`https://cloud.langfuse.com/trace/<trace_id>`), open **both**
traces and compare the observation tree:

**PASS criteria (I6):**
- Both traces show the **same nesting shape** under `step.N` (e.g. `tool.called`
  / `llm.*` nested under their step span in *both* runs — not flat in one and
  nested in the other).
- There is **exactly one** `step.N` span per logical step in each trace (no
  duplicate `step.2` / `step.3` from a recreated span).

Local corroboration from the server terminal (`logs/dev_server.log`): for each
run, the `stream_ended ... trace=<id>` line should appear, and any
`Relay published N event(s)` lines for that trace should appear **before** the
trace is released/flushed (drain-before-close ordering).

```bash
grep -nE "stream_ended|Relay published|release" logs/dev_server.log | tail -30
```

> **Capture:** both `trace_id`s, two screenshots (or the observation lists) of
> the trees, and the grepped ordering lines.

---

## Step 8 — I8: no duplicate terminal events

**Local check** (per-trace recording — there must be one terminal event id):

```bash
python - "$TRACE" <<'PY'
import json, sys, collections
trace = sys.argv[1]
path = f"cache/black_box_recordings/{trace}/trace.jsonl"
counts = collections.Counter()
ids = collections.Counter()
for line in open(path):
    evt = json.loads(line)
    et = evt.get("event_type")
    counts[et] += 1
    ids[(et, evt.get("event_id"))] += 1
print("task_completed count:", counts.get("task_completed"))
print("step_executed count:", counts.get("step_executed"))
dupes = {k: v for k, v in ids.items() if v > 1}
print("duplicate (event_type,event_id):", dupes or "none")
PY

# relay offset advanced (atomic) and no error spam
ls -l "cache/black_box_recordings/$TRACE/" 2>/dev/null
grep -nE "run_once iteration failed|export.*fail" logs/dev_server.log | tail -20
```

**Langfuse check:** open the trace and confirm there is **exactly one**
`task.completed` observation (and one `step.executed` per step) — no twin with an
identical `event_id` in metadata.

**PASS criteria (I8):**
- `TASK_COMPLETED count` = `1`; no `duplicate (event_type,event_id)`.
- Langfuse shows a single `task.completed` observation.
- No `run_once iteration failed` / export-failure spam in the server log.

> **Capture:** the printed counts, the offset-file listing, and the Langfuse
> `task.completed` observation count.

---

## Step 9 — Tear down

```bash
# Ctrl-C the dev server, then:
docker compose -f docker-compose.searxng.yml down
```

---

## Results table (fill in and share)

| Defect | Check | Expected | Observed | Result |
|--------|-------|----------|----------|--------|
| I2 | `outcome` on TASK_COMPLETED | `success` | | |
| I2 | `goal_met` | `true` | | |
| I2 | `criteria_met` | `> 0.0` | | |
| I2 | `unmet_conditions` | not the 2 fixed strings | | |
| I2 | judge fallback warning | absent | | |
| I6 | span tree shape run 1 vs run 2 | identical | | |
| I6 | `step.N` spans per step | exactly 1 | | |
| I8 | TASK_COMPLETED count (local) | 1 | | |
| I8 | duplicate (type,event_id) | none | | |
| I8 | `task.completed` in Langfuse | exactly 1 | | |

**Result values:** **PASS** (all green) · **SOFT** (Langfuse keys absent, so I6
and the Langfuse-side I8 unverified, but local I2 + I8 green) · **FAIL** (any
local check red).

---

## Troubleshooting

- **`Connection failed` from the send script** — the server isn't on 8001. Start
  it with `PORT=8001 PORT_STRICT=1 python -m middleware`, or send with
  `python scripts/_dbg_d9c823_send.py --port <actual-port>`.
- **`goal_met` still `false` / no `goal_judge` in evals.log** — `GOAL_JUDGE_ENABLED`
  wasn't `true` in the **server's** environment, or `OPENAI_API_KEY` is missing
  (the judge fell back to the keyword heuristic). Re-export and restart the server.
- **Stub sentence in the answer** — `WEB_SEARCH_PROVIDER=searxng` wasn't set in
  the server env, or SearXNG isn't up on 8888.
- **No Langfuse trace** — server log says `dev telemetry disabled`: keys missing
  or `LANGFUSE_ENABLED=false`. I2 + local I8 still validate; mark I6 as SOFT.
- **`cache/black_box_recordings/<trace>/` missing** — `BLACKBOX_RELAY_MODE` is
  not `in_process`, or `BLACKBOX_STORAGE_DIR` was overridden. Check the env and
  the relay-started log line.
