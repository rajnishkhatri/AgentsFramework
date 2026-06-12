"""Drive the 30-task stage-2a ROUND-2 shadow sample through the deployed BFF.

Identical mechanics to round 1 (sequential, 240s bound, resumable on rerun),
but a FRESH thread namespace shadow-2a-r2-{00..29} and its own run-log so the
round-2 corpus never collides with round-1 threads.
"""
import json
import time
import urllib.request

BASE = "https://agent-frontend-w65nrxwkiq-uc.a.run.app"
RUN_BOUND_S = 240
OUT = "/tmp/shadow_2a_r2_runs.jsonl"

state = json.load(open("frontend/e2e/.auth/state.json"))
cookies = "; ".join(f"{c['name']}={c['value']}" for c in state.get("cookies", []))
tasks = json.load(open("/tmp/shadow_2a_r2_tasks.json"))

done_threads = set()
try:
    for line in open(OUT):
        done_threads.add(json.loads(line)["thread_id"])
except FileNotFoundError:
    pass

for i, task in enumerate(tasks):
    thread_id = f"shadow-2a-r2-{i:02d}"
    if thread_id in done_threads:
        print(f"[{i:02d}] already done, skipping", flush=True)
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
    print(f"[{i:02d}] {status} {rec['secs']}s trace={trace_id}", flush=True)
    time.sleep(2)

print("BATCH COMPLETE", flush=True)
