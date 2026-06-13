"""Drive the FULL 101-row goldset through the deployed BFF (Stage 2a ROUND 3).

R3 item 4: redeploy + full-101 drive on a fresh namespace
``shadow-2a-r3-{000..100}``, gate ≥96/101 (n=30 cannot resolve a 95% bar —
longterm-plan finding #5). Same mechanics as round 2's 30-row driver
(sequential, bounded, resumable on rerun) — only the task source (the whole
goldset CSV, not the /tmp 30-subset) and namespace differ.

Each task runs on its OWN fresh thread (shadow-2a-r3-NNN), so the staleness
fix's "no prior artifact" branch is exercised 101× — every row is a turn-1,
from-step-0 run. Reads BFF auth from frontend/e2e/.auth/state.json (refresh
the WorkOS session first — `access-token` is short-lived).
"""
import csv
import json
import time
import urllib.request

BASE = "https://agent-frontend-w65nrxwkiq-uc.a.run.app"
RUN_BOUND_S = 240
OUT = "/tmp/shadow_2a_r3_runs.jsonl"
GOLDSET = "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_combined_sheet.csv"

state = json.load(open("frontend/e2e/.auth/state.json"))
cookies = "; ".join(f"{c['name']}={c['value']}" for c in state.get("cookies", []))

with open(GOLDSET, encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
tasks = [r["task"].strip() for r in rows if r.get("task", "").strip()]
assert len(tasks) == 101, f"expected 101 goldset tasks, got {len(tasks)}"

done_threads = set()
try:
    for line in open(OUT):
        done_threads.add(json.loads(line)["thread_id"])
except FileNotFoundError:
    pass

for i, task in enumerate(tasks):
    thread_id = f"shadow-2a-r3-{i:03d}"
    if thread_id in done_threads:
        print(f"[{i:03d}] already done, skipping", flush=True)
        continue
    body = json.dumps({
        "thread_id": thread_id,
        "input": {"messages": [{"role": "user", "content": task}]},
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/api/run/stream", data=body, method="POST",
        headers={
            "content-type": "application/json",
            "accept": "text/event-stream",
            "cookie": cookies,
        },
    )
    rec = {"case_idx": i, "thread_id": thread_id, "task_head": task[:80]}
    t0 = time.time()
    trace_id = None
    status = "timeout"
    try:
        with urllib.request.urlopen(req, timeout=RUN_BOUND_S) as resp:
            for raw in resp:
                if time.time() - t0 > RUN_BOUND_S:
                    status = "bounded_out"
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(line[5:])
                except Exception:
                    continue
                t = evt.get("type")
                if t == "RUN_STARTED" and trace_id is None:
                    trace_id = (evt.get("raw_event") or {}).get("trace_id") or evt.get("trace_id")
                if t == "RUN_FINISHED":
                    status = "finished"
                    break
                if t == "RUN_ERROR":
                    status = "run_error"
                    break
    except Exception as exc:
        status = f"transport_error:{type(exc).__name__}"
    rec.update(trace_id=trace_id, status=status, secs=round(time.time() - t0, 1))
    with open(OUT, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(f"[{i:03d}] {status} {rec['secs']}s trace={trace_id}", flush=True)
    time.sleep(2)

print("BATCH COMPLETE", flush=True)
